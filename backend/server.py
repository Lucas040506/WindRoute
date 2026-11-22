"""Local-only device bridge: websocket :8876, development HTTP API :8877."""
from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import queue
import signal
import sys
import threading
import time

import numpy as np
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from .emg_core import FS, Pipeline

ROOT = Path(__file__).resolve().parents[1]
# Local copy of the previously inspected device protocol and sources.
from .emg_io import FrameParser, ReplaySource, SerialSource, list_serial_ports


class Bridge:
    def __init__(self, port=8876, data_root=None, swap_device_channels=False):
        self.port = port
        self.swap_device_channels = swap_device_channels
        self.data_root = Path(data_root) if data_root else ROOT
        self.clients = set()
        self.pipeline = Pipeline(simulated=True)
        self.amplitudes = [0.0, 0.0]
        self.source = None
        self.source_name = "模拟信号"
        self.parser = FrameParser()
        self.frames = queue.Queue()
        self.loop = None
        self.running = True
        self.last_sample = time.monotonic()
        self.lost_reported = False
        self.record_dir = None
        self.raw_file = self.event_file = None
        self.raw_writer = None
        self.record_index = 0
        self.report_path = ""

    def ports(self):
        return [{"device": dev, "description": desc} for dev, desc in list_serial_ports()]

    def state(self):
        return {**self.pipeline.snapshot(), "server_time_s": time.monotonic(),
                "source_name": self.source_name, "record_path": str(self.record_dir or ""),
                "report_path": self.report_path,
                "signal_ok": self.source is None or (not self.source.error and time.monotonic() - self.last_sample < 1)}

    async def broadcast(self, message):
        if self.event_file and message.get("type") in ("command", "gesture", "calibrated", "marker"):
            self.event_file.write(json.dumps(message, ensure_ascii=False) + "\n")
            self.event_file.flush()
        if self.clients:
            data = json.dumps(message, ensure_ascii=False)
            await asyncio.gather(*(c.send(data) for c in tuple(self.clients)), return_exceptions=True)

    def close_recording(self, report=None):
        if self.record_dir and report is not None:
            path = self.record_dir / "summary.json"
            report["emg_source"] = self.source_name
            report["calibration"] = self.pipeline.calibration.__dict__
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            self.report_path = str(path)
        for f in (self.raw_file, self.event_file):
            if f:
                f.close()
        self.raw_file = self.event_file = self.raw_writer = None
        self.record_dir = None

    def start_recording(self):
        self.close_recording()
        self.record_dir = self.data_root / "sessions" / datetime.now().strftime("run_%Y%m%d_%H%M%S_%f")
        self.record_dir.mkdir(parents=True)
        self.raw_file = (self.record_dir / "raw.csv").open("w", newline="", encoding="utf-8")
        self.raw_writer = csv.writer(self.raw_file)
        self.raw_writer.writerow(["sample_index", "t_s", "host_monotonic_s", "S1_raw", "S1_env", "S2_raw", "S2_env"])
        self.event_file = (self.record_dir / "events.jsonl").open("w", encoding="utf-8")
        self.record_index = 0

    async def change_source(self, name="simulate", path=None):
        # Validate before replacing a working source. Never substitute generated
        # samples for a failed physical device connection.
        if name == "device" and path not in {p["device"] for p in self.ports()}:
            raise ValueError("串口不存在，请刷新设备列表")
        if name == "replay":
            recording = Path(path).expanduser().resolve()
            if not recording.is_file() or recording.suffix.lower() != ".csv":
                raise ValueError("请选择存在的原始录制 CSV")
        if name not in ("device", "replay", "simulate"):
            raise ValueError("未知输入源")
        if self.source:
            self.source.stop()
        self.source = None
        while not self.frames.empty():
            self.frames.get_nowait()
        old_mode = self.pipeline.mode
        self.pipeline = Pipeline(simulated=name == "simulate")
        self.pipeline.set_mode(old_mode)
        self.amplitudes = [0.0, 0.0]
        self.parser = FrameParser()
        self.lost_reported = False
        self.last_sample = time.monotonic()
        if name == "device":
            available = {p["device"] for p in self.ports()}
            if path not in available:
                raise ValueError("串口不存在，请刷新设备列表")
            self.source = SerialSource(path)
            self.source_name = "设备 · " + path
        elif name == "replay":
            recording = Path(path).expanduser().resolve()
            if not recording.is_file() or recording.suffix.lower() != ".csv":
                raise ValueError("请选择存在的原始录制 CSV")
            self.source = ReplaySource(recording, loop=True, chunk_ms=10)
            self.source_name = "回放 · " + recording.name
        elif name == "simulate":
            self.source_name = "模拟信号"
        else:
            raise ValueError("未知输入源")
        if self.source:
            def on_bytes(data):
                frames = self.parser.feed(data)
                if len(frames):
                    self.frames.put((frames, time.monotonic()))
            self.source.start(on_bytes)
        await self.broadcast({"type": "source_changed", "source_name": self.source_name})

    async def control(self, msg):
        kind = msg.get("type", "")
        if kind == "sim":
            if "levels" in msg:
                levels = msg["levels"]
                if len(levels) != 2:
                    raise ValueError("levels 需要左右两个数值")
                self.amplitudes = [max(0, min(120, float(v))) for v in levels]
            else:
                i = int(msg.get("sensor", 0))
                if i not in (0, 1):
                    raise ValueError("sensor 必须是 0 或 1")
                self.amplitudes[i] = max(0, min(120, float(msg.get("amp", 0))))
        elif kind == "source":
            await self.change_source(msg.get("source", "simulate"), msg.get("path"))
        elif kind == "mode":
            mode = msg.get("mode", "menu")
            if mode not in ("menu", "play", "practice", "paused"):
                raise ValueError("未知模式")
            self.pipeline.set_mode(mode)
        elif kind == "calibrate":
            self.pipeline.start_calibration()
        elif kind == "record_start":
            self.start_recording()
        elif kind == "finish":
            self.close_recording(msg.get("report", {}))
        elif kind == "marker":
            await self.broadcast({**msg, "server_time_s": time.monotonic()})
        elif kind == "simulate":
            await self.change_source("simulate")
        elif kind == "cancel_calibration":
            self.pipeline.cal_stage = -1
            self.pipeline.status = "校准已取消，请重新校准"
        elif kind == "shutdown":
            self.running = False
        else:
            raise ValueError("未知消息类型")
        return {"ok": True, "state": self.state()}

    async def client(self, ws):
        self.clients.add(ws)
        await ws.send(json.dumps({**self.state(), "type": "hello", "ports": self.ports()}, ensure_ascii=False))
        try:
            async for data in ws:
                try:
                    msg = json.loads(data)
                    if not isinstance(msg, dict):
                        raise ValueError("消息必须是 JSON 对象")
                    if msg.get("type") == "ping":
                        reply = {"type": "pong", "client_ms": msg.get("client_ms", 0), "server_time_s": time.monotonic()}
                    elif msg.get("type") == "ports":
                        reply = {"type": "ports", "ports": self.ports()}
                    else:
                        result = await self.control(msg)
                        reply = {"type": "ack", "request": msg.get("type"), **result}
                    await ws.send(json.dumps(reply, ensure_ascii=False))
                except (ValueError, KeyError, TypeError, OSError) as exc:
                    await ws.send(json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False))
        except ConnectionClosed:
            pass
        finally:
            self.clients.discard(ws)
            # A disconnected UI cannot leave a simulated muscle held indefinitely.
            if not self.clients:
                self.amplitudes = [0.0, 0.0]
                self.pipeline.set_mode("menu")
                self.close_recording({"aborted": True, "reason": "game_disconnected"})

    async def process_frames(self, frames, end_s):
        self.last_sample = time.monotonic()
        for i, row in enumerate(frames):
            host_s = end_s - (len(frames) - 1 - i) / FS
            # Simulator amplitudes already use left/right order. Swap only real or replayed device frames.
            left_right = [row[2], row[0]] if self.swap_device_channels and not self.pipeline.simulated else [row[0], row[2]]
            for event in self.pipeline.feed(left_right, host_s):
                await self.broadcast(event)
            if self.raw_writer:
                self.raw_writer.writerow([self.record_index, f"{self.record_index / FS:.4f}",
                                          f"{host_s:.6f}", *[int(x) for x in row]])
                self.record_index += 1

    async def tick(self):
        next_tick = time.monotonic()
        last_state = 0.0
        sample = 0
        rng = np.random.default_rng(5230)
        while self.running:
            now = time.monotonic()
            if self.source is None:
                amps = self.amplitudes
                cal = self.pipeline.calibration_state()
                if cal:
                    amps = [60, 0] if cal["phase"] == "left" else [0, 60] if cal["phase"] == "right" else [0, 0]
                rows = []
                for _ in range(5):
                    t = sample / FS
                    raw = [round(1000 + math.sqrt(2) * a * math.sin(2 * math.pi * f * t) + rng.normal(0, .5))
                           for a, f in zip(amps, (83, 97))]
                    rows.append([raw[0], 0, raw[1], 0])
                    sample += 1
                await self.process_frames(rows, now)
            else:
                while not self.frames.empty():
                    frames, end_s = self.frames.get_nowait()
                    await self.process_frames(frames, end_s)
                error = self.source.error
                if (error or now - self.last_sample > 1) and not self.lost_reported:
                    self.lost_reported = True
                    self.pipeline.set_mode("paused")
                    self.pipeline.status = "信号中断，请检查接收器"
                    await self.broadcast({"type": "device_lost", "message": error or "一秒内未收到样本"})
            if now - last_state >= 1 / 30:
                await self.broadcast(self.state())
                last_state = now
            next_tick += .010
            if now - next_tick > .1:
                next_tick = now
            await asyncio.sleep(max(0, next_tick - time.monotonic()))

    async def run(self, source="simulate", path=None):
        self.loop = asyncio.get_running_loop()
        if source != "simulate":
            await self.change_source(source, path)
        bridge = self

        class API(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                self.reply({"ok": True, "ports": bridge.ports(), "state": bridge.state()})

            def do_POST(self):
                routes = {"/api/sim": "sim", "/api/simulate": "simulate", "/api/calibrate": "calibrate",
                          "/api/mode": "mode", "/api/source": "source"}
                try:
                    if self.path not in routes:
                        return self.reply({"ok": False, "error": "unknown route"}, 404)
                    length = int(self.headers.get("Content-Length", "0"))
                    if length > 65536:
                        return self.reply({"ok": False, "error": "body too large"}, 413)
                    msg = json.loads(self.rfile.read(length) or b"{}")
                    msg["type"] = routes[self.path]
                    future = asyncio.run_coroutine_threadsafe(bridge.control(msg), bridge.loop)
                    self.reply(future.result(timeout=5))
                except Exception as exc:
                    self.reply({"ok": False, "error": str(exc)}, 400)

            def reply(self, obj, code=200):
                data = json.dumps(obj, ensure_ascii=False).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        httpd = ThreadingHTTPServer(("127.0.0.1", self.port + 1), API)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            async with serve(self.client, "127.0.0.1", self.port, max_size=65536):
                print(f"EMG bridge ws://127.0.0.1:{self.port} | HTTP :{self.port + 1}", flush=True)
                await self.tick()
        finally:
            self.close_recording({"aborted": True, "reason": "bridge_shutdown"})
            if self.source:
                self.source.stop()
            httpd.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ws-port", type=int, default=8876)
    parser.add_argument("--port", help="device serial port")
    parser.add_argument("--replay", help="recorded CSV")
    parser.add_argument("--data-root", help="directory for persistent session files")
    parser.add_argument("--swap-device-channels", action="store_true", help="map physical sensor 2 to left and sensor 1 to right")
    args = parser.parse_args()
    bridge = Bridge(args.ws_port, args.data_root, args.swap_device_channels)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: setattr(bridge, "running", False))
    asyncio.run(bridge.run("device" if args.port else "replay" if args.replay else "simulate", args.port or args.replay))


if __name__ == "__main__":
    main()
