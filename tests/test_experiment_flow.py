"""One short study run against the installed respyra/PsychoPy APIs."""

import copy
import importlib.util
import json
import time
from pathlib import Path

import pytest

from mpi.condition import ConditionDef
from mpi.event_markers import MarkerOutlet
from mpi.lsl_polar import LSLPolarSource
from mpi.validation_study_jenny import CONFIG
from respyra.core.target_generator import SegmentDef


class Window:
    def __init__(self):
        self.callbacks = []
        self.closed = False

    def callOnFlip(self, callback, *args, **kwargs):
        self.callbacks.append((callback, args, kwargs))

    def flip(self):
        callbacks, self.callbacks = self.callbacks, []
        for callback, args, kwargs in callbacks:
            callback(*args, **kwargs)
        time.sleep(0.001)

    def close(self):
        self.closed = True


class Stimulus:
    text = ""
    y_min = 0
    y_max = 10

    def draw(self, *_args):
        pass


class Force:
    def __init__(self):
        self.n = 0
        self.stopped = False
        self.produce = True
        self.source_id = "polar-stream-vernier-raw-test"
        self.stream_name = "Synthetic-VernierRaw"
        self.force_index = 1

    def get_all(self):
        self.n += 1
        if not self.produce:
            return []
        return [(float(self.n), 5.0 + (self.n % 3) * 0.5)]

    def stop(self):
        self.stopped = True


class Polar(LSLPolarSource):
    contract_id = "respyra-polar-pca/1"
    source_id = "polar-h10-Synthetic_adrPcaWaveform"
    stream_name = "Synthetic_adrPcaWaveform"
    force_index = 0

    def __init__(self):
        self.n = 0
        self.stopped = False

    def get_all(self):
        self.n += 1
        return [(float(self.n) + i / 100, 0.01 + i * 0.002) for i in range(6)]

    def calibrate(self, center, amplitude, _run_id):
        self.center, self.amplitude = center, amplitude

    def stop(self):
        self.stopped = True


@pytest.mark.parametrize("scenario", [
    "complete", "polar_complete", "ready_escape", "tracking_error", "no_force",
])
@pytest.mark.parametrize("save_csv", [False, True])
def test_short_study_emits_complete_timeline(monkeypatch, scenario, save_csv, tmp_path):
    from psychopy import core, event
    from respyra.core import display, runner
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_experiment.py"
    spec = importlib.util.spec_from_file_location("study_run_experiment", script_path)
    study = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(study)

    class Outlet:
        samples = []

        def have_consumers(self):
            return True

        def wait_for_consumers(self, _timeout):
            return True

        def push_sample(self, sample, timestamp):
            self.samples.append((json.loads(sample[0]), timestamp))

    marker = MarkerOutlet.__new__(MarkerOutlet)
    marker._outlet = Outlet()
    marker._clock = lambda: time.perf_counter()
    marker.run_id = "test-run"
    marker.sequence = 0
    marker.trial_num = marker.condition = marker.phase = marker.screen = None
    marker.state = None
    marker.observer = None
    marker.calibration_attempt_open = False
    force = Polar() if scenario == "polar_complete" else Force()
    force.produce = scenario != "no_force"
    win = Window()
    stimuli = {name: Stimulus() for name in (
        "phase_title", "status_text", "trace_border", "trace", "target_dot",
        "countdown_text",
    )}
    key = "space"

    def show(window, text, key_list=None, color="white"):
        nonlocal key
        if text.startswith("On a scale of 1"):
            key = "1"
        elif text.startswith("Did you feel"):
            key = "n"
        elif scenario == "ready_escape" and text.startswith("Trial ") and " of " in text:
            key = "escape"
        else:
            key = "space"
        event.clearEvents()
        window.flip()
        return event.waitKeys(keyList=key_list)[0]

    monkeypatch.setattr(study, "MarkerOutlet", lambda: marker)
    monkeypatch.setattr(study, "run_source_setup", lambda _cfg, _markers: ({
        "participant": "test", "session": "001", "save_csv": save_csv,
    }, force))
    monkeypatch.setattr(runner, "setup_display", lambda _cfg: (win, stimuli))
    monkeypatch.setattr(display, "show_text_and_wait", show)
    monkeypatch.setattr(event, "waitKeys", lambda **_kwargs: [key])
    monkeypatch.setattr(event, "clearEvents", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(event, "getKeys", lambda **_kwargs: [])
    monkeypatch.setattr(core, "quit", lambda: None)
    if scenario == "tracking_error":
        def fail_tracking(state, *_args):
            state.win.flip()  # tracking really reached its first visible frame
            raise RuntimeError("synthetic tracking failure")

        monkeypatch.setattr(study, "run_tracking", fail_tracking)

    cfg = copy.deepcopy(CONFIG)
    cfg.output_dir = str(tmp_path)
    cfg.trial.build_conditions = lambda _session: [
        ConditionDef("normal", [SegmentDef(0.1, 1)]),
    ]
    cfg.timing.range_cal_duration_sec = 0.01
    cfg.timing.baseline_duration_sec = 0.01
    cfg.timing.countdown_duration_sec = 0.01
    cfg.timing.tracking_duration_sec = 0.01
    if scenario == "tracking_error":
        with pytest.raises(RuntimeError, match="synthetic tracking failure"):
            study.run_experiment(cfg)
    elif scenario == "no_force":
        with pytest.raises(study.LSLForceError, match="no Force samples"):
            study.run_experiment(cfg)
    else:
        study.run_experiment(cfg)

    payloads = [row for row, _timestamp in marker._outlet.samples]
    names = [row["event"] for row in payloads]
    for expected in ("run.started", "calibration.attempt.started",
                     "calibration.attempt.ended", "source.disconnected", "display.closed"):
        assert expected in names
    if scenario == "no_force":
        assert "calibration.completed" not in names
        assert "source.lost" in names and "run.failed" in names
        attempt_end = next(row for row in payloads if row["event"] == "calibration.attempt.ended")
        assert attempt_end["outcome"] == "no_data_fallback"
    else:
        assert "calibration.completed" in names
    if scenario == "ready_escape":
        assert "trial.aborted" in names and "run.aborted" in names
        assert "trial.started" not in names and "run.completed" not in names
    elif scenario == "tracking_error":
        assert "tracking.started" in names and "tracking.ended" in names
        assert "run.failed" in names and "run.completed" not in names
        ended = next(row for row in payloads if row["event"] == "tracking.ended")
        assert ended["outcome"] == "error" and ended["sample_count"] is None
    elif scenario in {"complete", "polar_complete"}:
        for expected in (
            "trial.started", "baseline.started", "baseline.ended",
            "countdown.started", "countdown.tick", "countdown.ended",
            "tracking.started", "tracking.ended", "assessment.accuracy",
            "assessment.breathing_judgment", "assessment.confidence",
            "ui.trial_feedback.shown", "ui.trial_feedback.dismissed",
            "trial.ended", "run.completed",
        ):
            assert expected in names
        assert names.index("baseline.started") < names.index("baseline.ended")
        assert names.index("tracking.started") < names.index("tracking.ended")
    assert [row["seq"] for row in payloads] == list(range(1, len(payloads) + 1))
    assert force.stopped and win.closed
    if scenario == "polar_complete":
        calibrated = next(row for row in payloads if row["event"] == "calibration.completed")
        assert calibrated["center_n"] is None and calibrated["signal_unit"] == "g"
        assert calibrated["input_polarity"] == 1
        assert calibrated["amplitude_value"] > 0
    files = list(tmp_path.glob("*.csv"))
    if not save_csv:
        assert not files
    else:
        import csv
        assert len(files) == 2
        samples = next(f for f in files if not f.name.endswith("-self-assessment.csv"))
        ratings = next(f for f in files if f.name.endswith("-self-assessment.csv"))
        with samples.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        expected_columns = ([{"force_n": "signal_g", "target_force": "target_signal_g",
                              "error": "error_g", "compensated_error": "compensated_error_g"}.get(name, name)
                             for name in cfg.data_columns] if scenario == "polar_complete" else list(cfg.data_columns))
        assert list(rows[0]) == expected_columns if rows else samples.read_text().splitlines()[0].split(',') == expected_columns
        if scenario in {"complete", "polar_complete"}:
            assert {row["phase"] for row in rows} >= {"range_cal", "baseline", "countdown", "tracking"}
            with ratings.open(newline="", encoding="utf-8") as f:
                answers = list(csv.DictReader(f))
            assert answers == [{"trial_num":"1","condition":"normal","self_condition":"n","confidence":"1","self_accuracy":"1"}]
