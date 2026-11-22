import math
from backend.emg_core import FS, Pipeline


def test_separate_comfortable_calibration():
    p = Pipeline(simulated=False)
    p.start_calibration()
    while p.cal_stage >= 0:
        stage = p.calibration_state()['phase']
        amplitudes = (40, 0) if stage == 'left' else (0, 65) if stage == 'right' else (0, 0)
        t = p.sample / FS
        raw = [1000 + math.sqrt(2) * a * math.sin(2 * math.pi * 83 * t) for a in amplitudes]
        p.feed(raw)
    assert p.calibration.valid
    assert 35 < p.calibration.mvc[0] < 45
    assert 60 < p.calibration.mvc[1] < 70
