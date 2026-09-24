import ast
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

from mpi.event_markers import CATALOG, MarkerOutlet, NullSampleLogger, prompt_name


class Window:
    def __init__(self):
        self.callbacks = []
        self.flip_count = 0

    def callOnFlip(self, callback, *args, **kwargs):
        self.callbacks.append((callback, args, kwargs))

    def flip(self):
        self.flip_count += 1
        callbacks, self.callbacks = self.callbacks, []
        for callback, args, kwargs in callbacks:
            callback(*args, **kwargs)


@pytest.fixture
def marker():
    class Info:
        def __init__(self, *_args):
            pass

        def desc(self):
            return self

        def append_child_value(self, *_args):
            pass

    class Outlet:
        def __init__(self, _info):
            self.samples = []
            self.connected = True

        def wait_for_consumers(self, _timeout):
            return self.connected

        def have_consumers(self):
            return self.connected

        def push_sample(self, sample, timestamp):
            self.samples.append((json.loads(sample[0]), timestamp))

    pylsl = types.SimpleNamespace(
        StreamInfo=Info, StreamOutlet=Outlet, cf_string="string", local_clock=lambda: 123.5,
    )
    with patch.dict(sys.modules, {"pylsl": pylsl}):
        yield MarkerOutlet()


def test_marker_payload_and_recorder_failure(marker):
    marker.wait_for_recorder()
    marker.emit("run.started", participant="p1", session="001")
    payload, timestamp = marker._outlet.samples[-1]
    assert payload["event"] == "run.started"
    assert payload["seq"] == 1
    assert payload["run_id"] == marker.run_id
    assert payload["lsl_time"] == timestamp == 123.5
    with pytest.raises(ValueError, match="Undocumented"):
        marker.emit("unknown")
    with pytest.raises(ValueError, match="missing marker fields"):
        marker.emit("run.completed")
    marker._outlet.connected = False
    with pytest.raises(RuntimeError, match="no LSL recorder"):
        marker.emit("run.completed", trials_completed=1)
    assert len(marker._outlet.samples) == 1


def test_prompt_identity_and_key_timing(marker):
    assert prompt_name("Breathing Range Calibration\nPress SPACE") == "calibration_ready"
    with pytest.raises(ValueError, match="Undocumented experiment screen"):
        prompt_name("Unexpected prompt")

    event = types.ModuleType("psychopy.event")
    waits = iter([[('x', 1.0)], [('space', 2.0)]])
    event.waitKeys = lambda **_kwargs: next(waits)
    event.clearEvents = lambda *_args, **_kwargs: None
    event.getKeys = lambda **_kwargs: []
    display = types.ModuleType("respyra.core.display")
    events = types.ModuleType("respyra.core.events")
    events.check_keys = lambda _keys=None, _clock=None: []

    def show(win, text, key_list=None, prepare_flip=None, key_clock=None, **_kwargs):
        assert text.startswith("Breathing Range Calibration")
        if prepare_flip:
            prepare_flip(win)
        win.flip()
        return event.waitKeys(keyList=key_list, timeStamped=key_clock)[0]

    display.show_text_and_wait = show
    psychopy = types.ModuleType("psychopy")
    psychopy.event = event
    core = types.ModuleType("respyra.core")
    core.display, core.events = display, events
    with patch.dict(sys.modules, {
        "psychopy": psychopy, "psychopy.event": event,
        "respyra.core": core, "respyra.core.display": display,
        "respyra.core.events": events,
    }):
        win = Window()
        original = display.show_text_and_wait
        with marker.observe_inputs_and_screens() as observed_show:
            result = observed_show(
                win, "Breathing Range Calibration\nPress SPACE",
                key_list=["space"], prepare_flip=lambda _win: None, key_clock=object(),
            )
            assert result == ("space", 2.0)
            win.flip()  # first calibration frame
        assert display.show_text_and_wait is original

    names = [sample[0]["event"] for sample in marker._outlet.samples]
    assert names == [
        "ui.calibration_ready.shown", "input.key", "input.key",
        "ui.calibration_ready.dismissed", "calibration.attempt.started",
    ]
    assert marker._outlet.samples[1][0]["accepted"] is False
    assert marker._outlet.samples[2][0]["psychopy_time"] == 2.0


def test_flip_aligned_phase_and_countdown(marker):
    win = Window()
    stimulus = types.SimpleNamespace(text="3")
    with marker.phase_scope("countdown", win):
        with marker.countdown_ticks(win, stimulus):
            win.flip()
            win.flip()
            stimulus.text = "2"
            win.flip()
    names = [sample[0]["event"] for sample in marker._outlet.samples]
    assert names == [
        "countdown.started", "countdown.tick", "countdown.tick", "countdown.ended",
    ]
    assert [sample[0].get("number") for sample in marker._outlet.samples[1:3]] == [3, 2]
    assert not win.callbacks


def test_calibration_attempt_closes_without_result_screen(marker):
    marker.state = types.SimpleNamespace(
        range_center=5.0, global_amplitude=2.0, y_min=0.0, y_max=10.0,
    )
    marker.start_calibration_attempt()
    marker.end_calibration_attempt("no_data_fallback")
    marker.end_calibration_attempt("escaped")
    rows = [sample[0] for sample in marker._outlet.samples]
    assert [row["event"] for row in rows] == [
        "calibration.attempt.started", "calibration.attempt.ended",
    ]
    assert rows[-1]["outcome"] == "no_data_fallback"


def test_catalog_has_pairs_and_logger_has_no_output():
    events = CATALOG["events"]
    for name in events:
        if name.startswith("ui.") and name.endswith(".shown"):
            assert name[:-5] + "dismissed" in events
    assert {field for event in events.values() for field in event["fields"]} == set(
        CATALOG["event_field_definitions"]
    )
    logger = NullSampleLogger()
    logger.log_row(force_n=10)
    logger.flush()

    runner = Path(__file__).resolve().parents[1] / "scripts" / "run_experiment.py"
    tree = ast.parse(runner.read_text(encoding="utf-8"))
    literal_events = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "emit"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    assert literal_events <= events.keys()
    assert "create_session_file" not in runner.read_text(encoding="utf-8")
