import ast
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

from mpi.event_markers import CATALOG, MarkerOutlet, NullSampleLogger, prompt_name
from mpi.desktop_bridge import DesktopCancelled


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


def test_marker_payload_does_not_depend_on_recorder(marker):
    observed = []
    marker.observer = observed.append
    marker.emit("run.started", participant="p1", session="001")
    payload, timestamp = marker._outlet.samples[-1]
    assert payload["event"] == "run.started"
    assert payload["seq"] == 1
    assert payload["run_id"] == marker.run_id
    assert payload["lsl_time"] == timestamp == 123.5
    assert observed == [payload]
    with pytest.raises(ValueError, match="Undocumented"):
        marker.emit("unknown")
    with pytest.raises(ValueError, match="missing marker fields"):
        marker.emit("run.completed")
    marker._outlet.connected = False
    marker.emit("run.completed", trials_completed=1)
    assert len(marker._outlet.samples) == 2


def test_recording_start_carries_setup_markers_in_order(marker):
    marker.emit("participant.dialog.shown")
    marker.emit("source.polarity.set", field="polar_inverted", enabled=False,
                ui_seq=1, ui_time_ms=2)
    marker.emit("recording.started", source_ids=["input", "markers", "derived"],
                subject="001", session="001", task="respyra", variables=[],
                policy="visible_and_late_except_excluded", excluded_uids=[])
    start = marker._outlet.samples[-1][0]
    assert [event["seq"] for event in start["pre_recording_events"]] == [1, 2]
    assert [event["event"] for event in start["pre_recording_events"]] == [
        "participant.dialog.shown", "source.polarity.set"]
    marker.emit("run.started", participant="p1", session="001")
    assert len(start["pre_recording_events"]) == 2

def test_name_can_change_before_subscription_but_not_during_run(marker):
    marker._outlet.connected = False
    marker.rename("Lab breathing markers")
    assert marker.name == "Lab breathing markers"
    with pytest.raises(ValueError, match="locked"):
        marker.rename("Another name")
    marker._outlet.connected = False
    marker.name_locked = True
    with pytest.raises(ValueError, match="locked"):
        marker.rename("Another name")


def test_marker_health_reports_own_output_not_recording(marker):
    marker._outlet.connected = False
    marker.emit("run.started", participant="p", session="001")
    assert marker.health_snapshot() == {"name":"Respyra-Events",
        "source_id":"respyra-events-" + marker.run_id, "online":True,
        "emitted":1}


@pytest.mark.parametrize("cancel_only", [False, True])
def test_prompt_identity_and_key_timing(marker, cancel_only):
    assert prompt_name("Breathing Range Calibration\nPress SPACE") == "calibration_ready"
    with pytest.raises(ValueError, match="Undocumented experiment screen"):
        prompt_name("Unexpected prompt")

    event = types.ModuleType("psychopy.event")
    waits = iter([[('x', 1.0)], [('space', 2.0)]])
    bounded_waits = []
    def wait(**kwargs):
        if cancel_only:
            assert kwargs["maxWait"] <= 0.1
            bounded_waits.append(kwargs["maxWait"])
        return next(waits)
    event.waitKeys = wait
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
        with marker.observe_inputs_and_screens(cancel_check=(lambda: None) if cancel_only else None) as observed_show:
            result = observed_show(
                win, "Breathing Range Calibration\nPress SPACE",
                key_list=["space"], prepare_flip=lambda _win: None, key_clock=object(),
            )
            assert result == ("space", 2.0)
            win.flip()  # first calibration frame
        assert display.show_text_and_wait is original
    if cancel_only:
        assert len(bounded_waits) == 2

    names = [sample[0]["event"] for sample in marker._outlet.samples]
    assert names == [
        "ui.calibration_ready.shown", "input.key", "input.key",
        "ui.calibration_ready.dismissed", "calibration.attempt.started",
    ]
    assert marker._outlet.samples[1][0]["accepted"] is False
    assert marker._outlet.samples[2][0]["psychopy_time"] == 2.0


@pytest.mark.parametrize("key", ["space", "escape"])
def test_key_on_prompt_flip_survives_wait_start(marker, key):
    """The visible prompt owns new keys; only pre-prompt input is stale."""
    buffer = ["stale"]
    event = types.ModuleType("psychopy.event")
    event.getKeys = lambda **_kwargs: [(value, 2.0) for value in buffer]
    event.clearEvents = lambda *_args, **_kwargs: buffer.clear()

    def wait(**kwargs):
        if kwargs.get("clearEvents", True):
            event.clearEvents("keyboard")
        assert buffer, "The key pressed on the visible flip was cleared"
        keys = buffer[:]
        buffer.clear()
        return keys

    event.waitKeys = wait
    display = types.ModuleType("respyra.core.display")
    events = types.ModuleType("respyra.core.events")
    events.check_keys = lambda *_args: []

    def show(win, text, key_list=None):
        event.clearEvents()
        win.callOnFlip(buffer.append, key)
        win.flip()
        return event.waitKeys(keyList=key_list)[0]

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
        with marker.observe_inputs_and_screens(cancel_check=lambda: None) as show_prompt:
            assert show_prompt(Window(), "Press SPACE to begin.",
                               key_list=["space", "escape"]) == key
    keys = [sample[0] for sample in marker._outlet.samples if sample[0]["event"] == "input.key"]
    assert [(item["key"], item["accepted"]) for item in keys] == [("stale", False), (key, True)]


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
    required = {field for event in events.values() for field in event["fields"]}
    assert set(CATALOG["event_field_definitions"]) - required == {"ui_origin", "ui_client_seq"}
    logger = NullSampleLogger()
    logger.log_row(force_n=10)
    logger.flush()

    runner = Path(__file__).resolve().parents[1] / "scripts" / "run_experiment.py"
    root = runner.parent.parent
    tree = ast.parse("\n".join(path.read_text(encoding="utf-8") for path in (
        runner, root / "src/mpi/lsl_setup.py", root / "src/mpi/event_markers/__init__.py",
        root / "src/mpi/desktop_bridge.py",
    )))
    literal_events = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ((isinstance(node.func, ast.Attribute) and node.func.attr == "emit")
             or (isinstance(node.func, ast.Name) and node.func.id in {"publish", "emit"}))
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    assert literal_events <= events.keys()
