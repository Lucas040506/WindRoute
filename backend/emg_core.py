"""Sample-clock EMG processing. All detector durations use samples, never UI frames.

Default calibration belongs ONLY to the known-amplitude simulator. Real devices
must complete their own independent left/right calibration before a training run.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math

FS = 500


@dataclass
class Channel:
    on: float = 10.0
    hi: float = 50.0
    active: bool = False
    used: bool = False
    above: int = 0
    below: int = 0
    onset: float = 0.0

    def update(self, value: float, t: float) -> bool:
        rising = False
        if not self.active:
            self.above = self.above + 1 if value >= self.on else 0
            if self.above >= 8:  # 16 ms at 500 Hz
                self.active = True
                self.onset = t - 7 / FS
                self.below = 0
                rising = True
        else:
            self.below = self.below + 1 if value < .7 * self.on else 0
            if self.below >= 30:
                self.active = False
                self.used = False
                self.above = 0
        return rising


class Commands:
    def __init__(self):
        self.channels = [Channel(), Channel()]
        self.reset()

    def reset(self):
        self.state = "IDLE"
        self.first = 0
        self.start = 0.0
        self.both_start = 0.0
        self.peak = [0.0, 0.0]
        self.level_sum = [0.0, 0.0]
        self.hold_n = 0
        for c in self.channels:
            c.active = c.used = False
            c.above = c.below = 0

    def feed(self, levels: list[float], t: float) -> list[dict]:
        for c, value in zip(self.channels, levels):
            c.update(value, t)
        out = []

        def emit(name: str, **data):
            event = {"type": "command", "command": name, "t": t,
                     "onset_t": self.start,
                     "latency_ms": round(max(0, t - self.start) * 1000, 1),
                     "levels": [round(v, 2) for v in levels], **data}
            out.append(event)

        fresh = [c.active and not c.used for c in self.channels]
        if self.state == "LOCKED":
            if not any(c.active for c in self.channels):
                self.state = "IDLE"
            return out
        if self.state == "IDLE" and any(fresh):
            self.first = 0 if fresh[0] else 1
            self.start = self.channels[self.first].onset
            self.state = "PENDING"
        if self.state == "PENDING":
            other = 1 - self.first
            first_c, other_c = self.channels[self.first], self.channels[other]
            if fresh[other] and abs(other_c.onset - self.start) <= .080 + 1e-8:
                self.both_start = max(c.onset for c in self.channels)
                self.peak = list(levels)
                self.level_sum = [0.0, 0.0]
                self.hold_n = 0
                self.state = "BOTH"
            elif not first_c.active:
                self.state = "IDLE"
            elif t - self.start >= .080 - 1e-8:
                name = "left" if self.first == 0 else "right"
                emit(name, side=name, sensor=self.first)
                first_c.used = True
                self.state = "IDLE"
        if self.state == "BOTH":
            self.peak = [max(a, b) for a, b in zip(self.peak, levels)]
            ratios = [v / c.hi for v, c in zip(levels, self.channels)]
            if sum(ratios) / 2 >= 1:
                emit("jump")
                self.state = "LOCKED"
                for c in self.channels:
                    c.used = True
            elif not all(c.active for c in self.channels):
                peak_ratio = sum(v / c.hi for v, c in zip(self.peak, self.channels)) / 2
                emit("jump" if peak_ratio >= .75 else "unclear")
                self.state = "LOCKED"
                for c in self.channels:
                    c.used = True
            elif t - self.both_start >= .200 - 1e-8:
                emit("hold_start")
                self.state = "HOLDING"
                for c in self.channels:
                    c.used = True
        if self.state == "HOLDING":
            self.hold_n += 1
            self.level_sum = [a + b for a, b in zip(self.level_sum, levels)]
            if not all(c.active for c in self.channels):
                # Includes the recognition wait; report physical contraction duration.
                emit("hold_end", duration_s=round(max(0, t - .060 - self.both_start), 3),
                     mean_levels=[round(v / max(1, self.hold_n), 2) for v in self.level_sum])
                self.state = "LOCKED"
        return out


class Menus:
    """Mutually exclusive with Commands. Pausing during running uses Escape."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.start = [None, None]
        self.done = [False, False]
        self.pending = None
        self.both_since = None
        self.cool_until = 0.0
        self.progress = 0.0

    def feed(self, levels, thresholds, t):
        out = []
        active = [v >= q for v, q in zip(levels, thresholds)]
        self.progress = 0.0
        if self.pending is not None and t - self.pending >= .5:
            out.append({"type": "gesture", "gesture": "tap", "t": t})
            self.pending = None
            self.cool_until = t + .4
        for i, on in enumerate(active):
            if on and self.start[i] is None:
                self.start[i], self.done[i] = t, False
        if all(active):
            if self.both_since is None:
                self.both_since = t
            self.progress = min(1.0, (t - self.both_since) / 1.0)
            if self.progress >= 1 and not any(self.done) and t >= self.cool_until:
                out.append({"type": "gesture", "gesture": "both_hold", "t": t})
                self.done = [True, True]
                self.pending = None
                self.cool_until = t + .4
        else:
            self.both_since = None
        for i, on in enumerate(active):
            start = self.start[i]
            if start is None:
                continue
            duration = t - start
            if on and not all(active) and not self.done[i] and t >= self.cool_until:
                self.progress = max(self.progress, min(1.0, duration / 1.5))
                if duration >= 1.5:
                    out.append({"type": "gesture", "gesture": "hold", "t": t})
                    self.done[i] = True
                    self.pending = None
                    self.cool_until = t + .4
            if not on:
                if not self.done[i] and t >= self.cool_until:
                    if .08 <= duration <= .5:
                        if self.pending is not None and t - self.pending < .5:
                            out.append({"type": "gesture", "gesture": "double", "t": t})
                            self.pending = None
                            self.cool_until = t + .4
                        else:
                            self.pending = t
                    elif duration > .5:
                        out.append({"type": "gesture", "gesture": "hold_cancel", "t": t})
                self.start[i] = None
        return out


class RMS:
    def __init__(self, n):
        self.values = deque(maxlen=n)
        self.total = 0.0

    def feed(self, value):
        square = value * value
        if len(self.values) == self.values.maxlen:
            self.total -= self.values[0]
        self.values.append(square)
        self.total += square
        return math.sqrt(max(0, self.total) / self.values.maxlen)


@dataclass
class Calibration:
    noise: list[float] = field(default_factory=lambda: [.5, .5])
    noise_sd: list[float] = field(default_factory=lambda: [.1, .1])
    mvc: list[float] = field(default_factory=lambda: [100.0, 100.0])
    valid: bool = False


class Pipeline:
    CAL_STEPS = [("rest", 3.0, "双侧放松"), ("prep_left", 2.0, "准备左侧收缩"),
                 ("left", 4.0, "仅左侧舒适收缩并保持"), ("prep_right", 2.0, "放松并准备右侧收缩"),
                 ("right", 4.0, "仅右侧舒适收缩并保持"), ("release", 1.0, "双侧放松")]

    def __init__(self, simulated=True):
        self.simulated = simulated
        self.calibration = Calibration(valid=simulated)
        self.commands = Commands()
        self.menus = Menus()
        self.mode = "menu"
        self.sample = 0
        self.dc = [None, None]
        self.fast = [RMS(25), RMS(25)]
        self.slow = [RMS(125), RMS(125)]
        self.fast_levels = [0.0, 0.0]
        self.slow_levels = [0.0, 0.0]
        self.rms_counts = [0.0, 0.0]  # Uncalibrated AC RMS in device counts, left/right order.
        self.cal_stage = -1
        self.cal_count = 0
        self.cal_data = {"rest": [[], []], "left": [[], []], "right": [[], []]}
        self.status = "模拟信号" if simulated else "等待校准"
        self.armed = False
        self.arming_count = 0

    def set_mode(self, mode):
        self.mode = mode
        self.commands.reset()
        self.menus.reset()
        # Entering a new screen while still holding the previous contraction
        # must not create a fresh action. Require a real release first.
        self.armed = False
        self.arming_count = 0

    def start_calibration(self):
        self.calibration.valid = False
        self.cal_stage, self.cal_count = 0, 0
        self.cal_data = {"rest": [[], []], "left": [[], []], "right": [[], []]}
        self.commands.reset()
        self.menus.reset()

    def calibration_state(self):
        if self.cal_stage < 0:
            return None
        key, duration, text = self.CAL_STEPS[self.cal_stage]
        return {"phase": key, "text": text, "progress": self.cal_count / (duration * FS),
                "step": self.cal_stage + 1, "steps": len(self.CAL_STEPS)}

    def thresholds(self):
        cal = self.calibration
        on_level = [max(5, 3 * sd / max(mvc, 1e-6) * 100)
                    for sd, mvc in zip(cal.noise_sd, cal.mvc)]
        return [max(10, 2 * v) for v in on_level]

    def feed(self, raw, host_s=None):
        self.sample += 1
        t = self.sample / FS
        fast, slow = [], []
        for i, x in enumerate(raw):
            if self.dc[i] is None:
                self.dc[i] = float(x)
            self.dc[i] += (float(x) - self.dc[i]) / (FS * 2.0)
            ac = float(x) - self.dc[i]
            fast.append(self.fast[i].feed(ac))
            slow.append(self.slow[i].feed(ac))
        self.rms_counts = slow
        events = []
        if self.cal_stage >= 0:
            key, seconds, _ = self.CAL_STEPS[self.cal_stage]
            if key in self.cal_data:
                for i in range(2):
                    self.cal_data[key][i].append(slow[i])
            self.cal_count += 1
            if self.cal_count >= int(seconds * FS):
                self.cal_stage += 1
                self.cal_count = 0
                if self.cal_stage == len(self.CAL_STEPS):
                    import numpy as np
                    noise = [float(np.median(x[FS // 2:])) for x in self.cal_data["rest"]]
                    sd = [float(np.std(x[FS // 2:])) for x in self.cal_data["rest"]]
                    mvc_raw = [float(np.convolve(self.cal_data[side][i], np.ones(FS) / FS, mode="valid").max())
                               for i, side in enumerate(("left", "right"))]
                    valid = all(m > 4 * max(n, 1e-6) for m, n in zip(mvc_raw, noise))
                    mvc = [math.sqrt(max(m * m - n * n, 1e-6)) for m, n in zip(mvc_raw, noise)]
                    self.calibration = Calibration(noise, sd, mvc, valid)
                    self.cal_stage = -1
                    self.status = "校准完成" if valid else "校准失败：检查两侧电极并重试"
                    events.append({"type": "calibrated", "ok": valid, "mvc": mvc, "noise": noise})
                    self.commands.reset()
                    self.menus.reset()
        cal = self.calibration
        self.fast_levels = [math.sqrt(max(v * v - n * n, 0)) / max(m, 1e-6) * 100
                            for v, n, m in zip(fast, cal.noise, cal.mvc)]
        self.slow_levels = [math.sqrt(max(v * v - n * n, 0)) / max(m, 1e-6) * 100
                            for v, n, m in zip(slow, cal.noise, cal.mvc)]
        if self.cal_stage < 0 and cal.valid:
            thresholds = self.thresholds()
            for c, on in zip(self.commands.channels, thresholds):
                c.on, c.hi = on, max(50, 2 * on)
            if not self.armed:
                relaxed = all(v < .7 * q for v, q in zip(self.fast_levels, thresholds))
                self.arming_count = self.arming_count + 1 if relaxed else 0
                self.armed = self.arming_count >= 30
            elif self.mode in ("play", "practice"):
                events += self.commands.feed(self.fast_levels, t)
            elif self.mode == "menu":
                events += self.menus.feed(self.fast_levels, [max(20, v) for v in thresholds], t)
        if host_s is not None:
            for event in events:
                event["server_time_s"] = host_s
                event["onset_server_s"] = host_s - event.get("latency_ms", 0) / 1000
                event["source"] = "simulated_emg" if self.simulated else "device_emg"
        return events

    def snapshot(self):
        return {"type": "state", "levels": self.fast_levels, "slow_levels": self.slow_levels,
                "rms_counts": self.rms_counts,
                "cmd_on": self.thresholds(), "cmd_hi": [c.hi for c in self.commands.channels],
                "calibrated": self.calibration.valid, "calibration": self.calibration_state(),
                "status": self.status, "simulated": self.simulated, "sample_t": self.sample / FS,
                "hold_progress": self.menus.progress, "input_ready": self.armed}
