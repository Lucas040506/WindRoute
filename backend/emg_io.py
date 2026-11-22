"""
emg_io.py —— sEMG 设备数据采集层

包含：
  FrameParser    协议帧解析（AA BB + 4 x int16 小端，无校验）
  RingBuffer     线程安全的环形缓冲区
  RateMeter      实时帧率统计
  SerialSource   真实设备（USB 接收器串口）数据源
  ReplaySource   回放数据源：把录好的 CSV 重新编码成字节流，按真实速度送入解析器
  Acquisition    把"数据源 → 解析器 → 缓冲区/统计/录制"串起来

协议（来自厂家 SerialPlot 配置 EMG-CH2.ini）：
  115200 8N1，帧 = AA BB | CH1 | CH2 | CH3 | CH4，每通道 int16 小端，共 10 字节
  CH1 = 传感器1 原始信号，CH2 = 传感器1 包络
  CH3 = 传感器2 原始信号，CH4 = 传感器2 包络
"""
from __future__ import annotations

import csv
import struct
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

# ---------------------------------------------------------------- 协议常量
HEADER = b"\xAA\xBB"
N_CH = 4
PAYLOAD = N_CH * 2            # 8 字节
FRAME_LEN = len(HEADER) + PAYLOAD   # 10 字节
BAUD = 115200
NOMINAL_FS = 500.0            # 实测约 500 Hz（以 RateMeter 实测为准）
CH_NAMES = ["S1_raw", "S1_env", "S2_raw", "S2_env"]
_UNPACK = struct.Struct("<4h")


# ---------------------------------------------------------------- 帧解析
@dataclass
class ParserStats:
    frames: int = 0           # 成功解析的帧数
    resyncs: int = 0          # 发生重新同步的次数（丢弃了字节）
    dropped_bytes: int = 0    # 因错位被丢弃的字节数
    rejected: int = 0         # 通过帧头但未通过校验（前瞻 / 合理性）的次数


class FrameParser:
    """
    流式帧解析器。由于协议没有校验位，用两道检查防止错位：
      1) 前瞻：当前帧之后紧跟的两个字节也必须是 AA BB；
      2) 合理性：包络通道（CH2/CH4）不应为负数。
    前瞻意味着每一帧要等到下一帧的帧头到达后才输出，只增加约 2 ms 延迟。
    """

    def __init__(self, lookahead: bool = True, check_envelope: bool = True):
        self.buf = bytearray()
        self.lookahead = lookahead
        self.check_envelope = check_envelope
        self.stats = ParserStats()

    def _drop(self, n: int):
        if n > 0:
            del self.buf[:n]
            self.stats.dropped_bytes += n
            self.stats.resyncs += 1

    def feed(self, data: bytes) -> np.ndarray:
        """送入任意长度字节，返回解析出的帧 (N, 4) int16。"""
        self.buf.extend(data)
        out = []
        need = FRAME_LEN + (len(HEADER) if self.lookahead else 0)
        while True:
            idx = self.buf.find(HEADER)
            if idx < 0:
                # 保留可能是半个帧头的最后一个字节
                keep = 1 if self.buf[-1:] == HEADER[:1] else 0
                self._drop(len(self.buf) - keep)
                break
            if idx > 0:
                self._drop(idx)
            if len(self.buf) < need:
                break
            if self.lookahead and self.buf[FRAME_LEN:FRAME_LEN + 2] != HEADER:
                # 下一帧帧头没有紧跟在后面：要么当前 AA BB 是数据里恰好出现的字节（假帧头），
                # 要么当前帧后面混入了杂字节（无线干扰）。
                # 若本帧 10 字节范围内还藏着另一个 AA BB，说明对齐可疑 → 跳过 1 字节重找；
                # 否则认为本帧有效，杂字节留给下一轮丢弃。
                if self.buf.find(HEADER, 1, FRAME_LEN + 1) >= 0:
                    self.stats.rejected += 1
                    self._drop(1)
                    continue
            vals = _UNPACK.unpack_from(self.buf, len(HEADER))
            if self.check_envelope and (vals[1] < 0 or vals[3] < 0):
                self.stats.rejected += 1
                self._drop(1)
                continue
            out.append(vals)
            del self.buf[:FRAME_LEN]
            self.stats.frames += 1
        if not out:
            return np.empty((0, N_CH), dtype=np.int16)
        return np.asarray(out, dtype=np.int16)


def encode_frames(frames: np.ndarray) -> bytes:
    """把 (N,4) 数组编码成设备协议的字节流（用于回放和测试）。"""
    frames = np.asarray(frames, dtype="<i2").reshape(-1, N_CH)
    out = bytearray()
    for row in frames:
        out += HEADER + row.tobytes()
    return bytes(out)


# ---------------------------------------------------------------- 缓冲区
class RingBuffer:
    """固定容量环形缓冲区，保存最近 capacity 个样本；total 记录累计样本数（即样本序号）。"""

    def __init__(self, capacity: int, n_ch: int = N_CH):
        self.data = np.zeros((capacity, n_ch), dtype=np.float32)
        self.cap = capacity
        self.total = 0
        self.lock = threading.Lock()

    def append(self, frames: np.ndarray):
        n = len(frames)
        if n == 0:
            return
        with self.lock:
            if n > self.cap:
                self.total += n - self.cap
                frames = frames[-self.cap:]
                n = self.cap
            start = self.total % self.cap
            end = start + n
            if end <= self.cap:
                self.data[start:end] = frames
            else:
                k = self.cap - start
                self.data[start:] = frames[:k]
                self.data[:n - k] = frames[k:]
            self.total += n

    def latest(self, n: int) -> tuple[np.ndarray, int]:
        """返回最近 n 个样本（按时间顺序）以及第一个样本的序号。"""
        with self.lock:
            n = min(n, self.total, self.cap)
            end = self.total % self.cap
            start = end - n
            if start >= 0:
                arr = self.data[start:end].copy()
            else:
                arr = np.concatenate([self.data[start:], self.data[:end]])
            return arr, self.total - n


# ---------------------------------------------------------------- 帧率统计
class RateMeter:
    """以电脑时钟统计最近 window 秒内的平均帧率。"""

    def __init__(self, window: float = 2.0):
        self.window = window
        self.events: deque[tuple[float, int]] = deque()
        self.lock = threading.Lock()
        self.t0: Optional[float] = None
        self.count = 0

    def add(self, n: int, t: Optional[float] = None):
        t = time.monotonic() if t is None else t
        with self.lock:
            if self.t0 is None:
                self.t0 = t
            self.count += n
            self.events.append((t, n))
            while self.events and t - self.events[0][0] > self.window:
                self.events.popleft()

    def rate(self) -> float:
        with self.lock:
            if len(self.events) < 2:
                return 0.0
            span = self.events[-1][0] - self.events[0][0]
            n = sum(e[1] for e in list(self.events)[1:])
            return n / span if span > 0 else 0.0

    def overall(self) -> float:
        with self.lock:
            if self.t0 is None or not self.events:
                return 0.0
            span = self.events[-1][0] - self.t0
            return self.count / span if span > 0 else 0.0


# ---------------------------------------------------------------- 数据源
class _ThreadSource:
    """数据源基类：后台线程不断读取字节，交给 on_bytes 回调。"""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.on_bytes: Optional[Callable[[bytes], None]] = None
        self.error: Optional[str] = None
        self.finished = threading.Event()

    def start(self, on_bytes: Callable[[bytes], None]):
        self.on_bytes = on_bytes
        self._stop.clear()
        self.finished.clear()
        self._thread = threading.Thread(target=self._run_wrapper, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run_wrapper(self):
        try:
            self._run()
        except Exception as e:  # 把异常留给上层显示
            self.error = f"{type(e).__name__}: {e}"
        finally:
            self.finished.set()

    def _run(self):
        raise NotImplementedError


def list_serial_ports() -> list[tuple[str, str]]:
    """列出串口 [(设备名, 描述)]，CH340 接收器排在最前面。"""
    from serial.tools import list_ports
    ports = []
    for p in list_ports.comports():
        dev = p.device
        # Mac 上只用 /dev/cu.*，/dev/tty.* 打开时可能卡住
        if dev.startswith("/dev/tty."):
            continue
        is_ch340 = (p.vid == 0x1A86) or "usbserial" in dev or "wchusbserial" in dev
        ports.append((0 if is_ch340 else 1, dev, p.description or ""))
    ports.sort()
    return [(d, desc) for _, d, desc in ports]


def find_default_port() -> Optional[str]:
    ports = list_serial_ports()
    for dev, _ in ports:
        if "usbserial" in dev or "wchusbserial" in dev:
            return dev
    return ports[0][0] if ports else None


class SerialSource(_ThreadSource):
    def __init__(self, port: str, baud: int = BAUD):
        super().__init__()
        self.port = port
        self.baud = baud

    def _run(self):
        import serial
        with serial.Serial(self.port, self.baud, bytesize=8, parity="N",
                           stopbits=1, timeout=0.02) as ser:
            ser.reset_input_buffer()
            while not self._stop.is_set():
                data = ser.read(max(1, ser.in_waiting))
                if data and self.on_bytes:
                    self.on_bytes(data)


def load_recording(path: str | Path) -> np.ndarray:
    """
    读取录制文件，返回 (N,4) 数组。支持：
      - 本程序录制的 CSV（列 S1_raw,S1_env,S2_raw,S2_env）
      - SerialPlot 导出的 CSV / xlsx（timestamp,Channel1..Channel 4）
    """
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        import pandas as pd
        df = pd.read_excel(path)
        cols = [c for c in df.columns if str(c).lower().replace(" ", "").startswith("channel")]
        return df[cols[:N_CH]].to_numpy(dtype=np.float64)
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        norm = [h.strip().lower().replace(" ", "") for h in header]
        if all(n.lower() in norm for n in [c.lower() for c in CH_NAMES]):
            idx = [norm.index(c.lower()) for c in CH_NAMES]
        else:
            idx = [i for i, h in enumerate(norm) if h.startswith("channel")][:N_CH]
        rows = [[float(r[i]) for i in idx] for r in reader if r]
    return np.asarray(rows)


class ReplaySource(_ThreadSource):
    """
    回放：把录好的数据编码成和设备一模一样的字节流，按 fs*speed 的速度送出。
    这样回放模式也完整经过 FrameParser，可用来调试整条处理链。
    """

    def __init__(self, path: str | Path, fs: float = NOMINAL_FS, speed: float = 1.0,
                 loop: bool = False, chunk_ms: float = 20.0):
        super().__init__()
        self.frames = np.round(load_recording(path)).astype(np.int16)
        self.fs = fs
        self.speed = speed
        self.loop = loop
        self.chunk = max(1, int(fs * chunk_ms / 1000))

    def _run(self):
        n = len(self.frames)
        interval = self.chunk / (self.fs * self.speed)
        next_t = time.monotonic()
        i = 0
        while not self._stop.is_set():
            if i >= n:
                if not self.loop:
                    break
                i = 0
            data = encode_frames(self.frames[i:i + self.chunk])
            i += self.chunk
            if self.on_bytes:
                self.on_bytes(data)
            next_t += interval
            delay = next_t - time.monotonic()
            if delay > 0:
                time.sleep(delay)
        # 补一个帧头，让解析器把最后一帧也输出（前瞻需要）
        if self.on_bytes:
            self.on_bytes(HEADER)


# ---------------------------------------------------------------- 采集总控
class Recorder:
    """把解析出的帧写入 CSV：sample_index, t_s(按名义采样率), host_time, 4 通道。"""

    def __init__(self, path: str | Path, fs: float = NOMINAL_FS):
        self.path = Path(path)
        self.fs = fs
        self.f = open(self.path, "w", newline="", encoding="utf-8")
        self.w = csv.writer(self.f)
        self.w.writerow(["sample_index", "t_s", "host_time"] + CH_NAMES)
        self.n = 0
        self.lock = threading.Lock()

    def write(self, frames: np.ndarray, host_time: float):
        with self.lock:
            for row in frames:
                self.w.writerow([self.n, f"{self.n / self.fs:.4f}", f"{host_time:.3f}", *row.tolist()])
                self.n += 1

    def close(self):
        with self.lock:
            self.f.close()


class Acquisition:
    """数据源 → 解析器 → 环形缓冲区 + 帧率统计 + （可选）录制。"""

    def __init__(self, source: _ThreadSource, buffer_seconds: float = 60, fs: float = NOMINAL_FS):
        self.source = source
        self.parser = FrameParser()
        self.ring = RingBuffer(int(buffer_seconds * fs))
        self.rate = RateMeter()
        self.recorder: Optional[Recorder] = None
        self.fs = fs
        self.listeners: list[Callable[[np.ndarray], None]] = []
        self._lock = threading.Lock()

    def _on_bytes(self, data: bytes):
        with self._lock:
            frames = self.parser.feed(data)
        if len(frames) == 0:
            return
        now = time.monotonic()
        self.ring.append(frames)
        self.rate.add(len(frames), now)
        if self.recorder:
            self.recorder.write(frames, time.time())
        for cb in self.listeners:
            cb(frames)

    def start_recording(self, path: str | Path):
        self.recorder = Recorder(path, self.fs)

    def stop_recording(self):
        if self.recorder:
            self.recorder.close()
            self.recorder = None

    def start(self):
        self.source.start(self._on_bytes)

    def stop(self):
        self.source.stop()
        self.stop_recording()
