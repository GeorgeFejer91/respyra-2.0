"""Exercise the real startup dialog with deterministic LSL discovery workers."""

import threading
import time
from types import SimpleNamespace

import pytest

from mpi import lsl_setup
from mpi.event_markers import CATALOG
from mpi.lsl_force import ForceStreamCandidate, LSLForceError, LSLForceSource


class Collector:
    def __init__(self):
        self.events = []

    def emit(self, name, **fields):
        assert name in CATALOG["events"]
        assert set(CATALOG["events"][name]["fields"]) <= fields.keys()
        self.events.append((name, fields))

    @property
    def names(self):
        return [name for name, _fields in self.events]


def live_source():
    class Inlet:
        closed = False
        failed = False

        def pull_chunk(self, **_kwargs):
            if self.failed:
                raise RuntimeError("synthetic source disappeared")
            return [[5.0]], [time.monotonic()]

        def close_stream(self):
            self.closed = True

    return LSLForceSource(Inlet(), 0, "polar-stream-vernier-raw-test", "Test Force")


@pytest.fixture
def dialog_driver(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.delenv("RESPYRA_LSL_SOURCE_ID", raising=False)
    monkeypatch.setattr(lsl_setup, "load_force_selection", lambda: None)
    from PyQt6 import QtCore, QtWidgets
    from psychopy import gui
    original = gui.DlgFromDict

    def run(interact, markers):
        failures = []
        timers = []

        def make_dialog(*args, **kwargs):
            dialog = original(*args, **kwargs)
            deadline = time.monotonic() + 5

            def tick():
                try:
                    assert time.monotonic() < deadline, "Setup UI stalled"
                    buttons = {button.text(): button for button in dialog.findChildren(QtWidgets.QPushButton)}
                    table = dialog.findChild(QtWidgets.QTableWidget)
                    interact(dialog, buttons, table)
                except Exception as exc:
                    failures.append(exc)
                    dialog.reject()

            timer = QtCore.QTimer(dialog)
            timer.timeout.connect(tick)
            timer.start(10)
            timers.append(timer)
            return dialog

        monkeypatch.setattr(gui, "DlgFromDict", make_dialog)
        try:
            result = lsl_setup.run_source_setup(SimpleNamespace(name="Test Study"), markers)
        finally:
            for timer in timers:
                timer.stop()
        if failures:
            raise failures[0]
        return result

    return run


@pytest.mark.parametrize("saved_state", ["none", "missing", "corrupt"])
def test_add_stream_validates_selection_and_remembers_only_accepted_source(monkeypatch, dialog_driver, saved_state):
    from PyQt6 import QtTest
    markers = Collector()
    source = live_source()
    remembered = []
    good = SimpleNamespace(name=lambda: "Force", type=lambda: "VernierRaw", source_id=lambda: source.source_id)
    bad = SimpleNamespace(name=lambda: "Normalized", type=lambda: "Respiration", source_id=lambda: "processed")
    monkeypatch.setattr(lsl_setup, "scan_force_streams", lambda: [
        ForceStreamCandidate(bad, None, "Requires Force in N"),
        ForceStreamCandidate(good, 0, "Compatible: raw Force (N)"),
    ])
    monkeypatch.setattr(lsl_setup, "open_force_source", lambda info: source if info is good else pytest.fail("wrong input"))
    monkeypatch.setattr(lsl_setup, "save_force_selection", lambda value: remembered.append(value.source_id))
    if saved_state == "missing":
        monkeypatch.setattr(lsl_setup, "load_force_selection", lambda: {
            "source_id": "polar-stream-vernier-raw-missing", "stream_name": "Absent",
        })
        def missing(source_id):
            assert source_id == "polar-stream-vernier-raw-missing"
            raise LSLForceError("Saved stream is absent")
        monkeypatch.setattr(lsl_setup, "connect_force_source", missing)
    elif saved_state == "corrupt":
        def corrupt(): raise LSLForceError("Saved LSL selection is invalid")
        monkeypatch.setattr(lsl_setup, "load_force_selection", corrupt)
    stage = 0

    def interact(dialog, buttons, table):
        nonlocal stage
        add = buttons["Add LSL Stream…"]
        use = buttons["Use Selected Stream"]
        if stage == 0 and add.isEnabled():
            QtTest.QTest.keyClicks(dialog.inputFields[0], "test")
            assert not dialog.okBtn.isEnabled()  # typing cannot bypass input validation
            assert remembered == []
            add.click()
            stage = 1
        elif stage == 1 and table.rowCount() == 2:
            table.selectRow(0)
            assert not use.isEnabled()
            table.selectRow(1)
            assert use.isEnabled()
            use.click()
            stage = 2
        elif stage == 2 and dialog.okBtn.isEnabled():
            assert remembered == [source.source_id]
            dialog.okBtn.click()
            stage = 3

    values, result = dialog_driver(interact, markers)
    assert values == {"participant": "test", "session": "001"} and result is source
    names = markers.names
    assert names.index("source.scan.started") < names.index("source.scan.completed")
    assert names.index("source.ui.use.clicked") < names.index("source.connected") < names.index("participant.dialog.accepted")
    assert "source.memory.saved" in names
    if saved_state == "missing":
        assert "source.memory.loaded" in names and "source.connection.failed" in names
    if saved_state == "corrupt":
        assert "source.memory.invalid" in names
    assert not source.inlet.closed
    source.stop()


@pytest.mark.parametrize("lose_source", [False, True])
def test_remembered_stream_reconnects_automatically_and_loss_disables_start(monkeypatch, dialog_driver, lose_source):
    from PyQt6 import QtTest
    markers = Collector()
    source = live_source()
    monkeypatch.setattr(lsl_setup, "load_force_selection", lambda: {
        "source_id": source.source_id, "stream_name": source.stream_name,
    })
    connected = []
    def reconnect(source_id):
        connected.append(source_id)
        return source
    monkeypatch.setattr(lsl_setup, "connect_force_source", reconnect)
    monkeypatch.setattr(lsl_setup, "save_force_selection", lambda _source: pytest.fail("Reconnect rewrote settings"))
    stage = 0

    def interact(dialog, _buttons, _table):
        nonlocal stage
        if stage == 0:
            QtTest.QTest.keyClicks(dialog.inputFields[0], "repeat")
            stage = 1
        if stage == 1 and dialog.okBtn.isEnabled():
            if lose_source:
                source.inlet.failed = True
                stage = 2
            else:
                dialog.okBtn.click()
        elif stage == 2 and "source.lost" in markers.names:
            assert not dialog.okBtn.isEnabled()
            dialog.cancelBtn.click()

    values, result = dialog_driver(interact, markers)
    assert connected == [source.source_id]
    assert "source.scan.started" not in markers.names
    assert "source.connection.accepted" in markers.names
    if lose_source:
        assert values is None and result is None and source.inlet.closed
    else:
        assert values["participant"] == "repeat" and result is source
        source.stop()


def test_cancel_pending_connection_closes_result_without_saving(monkeypatch, dialog_driver):
    markers = Collector()
    source = live_source()
    gate = threading.Event()
    started = threading.Event()
    info = SimpleNamespace(name=lambda: "Force", type=lambda: "VernierRaw", source_id=lambda: source.source_id)
    monkeypatch.setattr(lsl_setup, "scan_force_streams", lambda: [ForceStreamCandidate(info, 0, "Compatible")])
    def open_source(_info):
        started.set()
        assert gate.wait(3)
        return source
    monkeypatch.setattr(lsl_setup, "open_force_source", open_source)
    monkeypatch.setattr(lsl_setup, "save_force_selection", lambda _source: pytest.fail("Cancelled source saved"))
    stage = 0
    def interact(dialog, buttons, table):
        nonlocal stage
        if stage == 0:
            buttons["Add LSL Stream…"].click()
            stage = 1
        elif stage == 1 and table.rowCount():
            table.selectRow(0)
            buttons["Use Selected Stream"].click()
            stage = 2
        elif stage == 2 and started.is_set():
            dialog.cancelBtn.click()
            gate.set()
    assert dialog_driver(interact, markers) == (None, None)
    assert source.inlet.closed and "source.memory.saved" not in markers.names
    assert "source.connection.cancelled" in markers.names


def test_marker_failure_during_memory_load_never_shows_dialog(monkeypatch, dialog_driver):
    source = live_source()
    monkeypatch.setattr(lsl_setup, "load_force_selection", lambda: {
        "source_id": source.source_id, "stream_name": source.stream_name,
    })
    monkeypatch.setattr(lsl_setup, "connect_force_source", lambda **_kwargs: source)
    class FailedMarkers(Collector):
        def emit(self, name, **fields):
            if name == "source.memory.loaded":
                raise RuntimeError("marker recorder disappeared")
            super().emit(name, **fields)
    markers = FailedMarkers()
    with pytest.raises(RuntimeError, match="marker recorder disappeared"):
        dialog_driver(lambda *_args: pytest.fail("Dialog shown without recorder"), markers)
    assert "participant.dialog.shown" not in markers.names


@pytest.mark.parametrize("failure_at", ["scan", "connect", "save"])
def test_setup_failures_allow_retry_without_accepting_or_saving_failed_input(monkeypatch, dialog_driver, failure_at):
    markers = Collector()
    source = live_source()
    abandoned = live_source()
    info = SimpleNamespace(name=lambda: "Force", type=lambda: "VernierRaw", source_id=lambda: source.source_id)
    calls = {"scan": 0, "connect": 0, "save": 0}
    saved = []
    def may_fail(kind):
        calls[kind] += 1
        if kind == failure_at and calls[kind] == 1:
            raise LSLForceError("synthetic " + kind + " failure")
    def scan():
        may_fail("scan")
        return [ForceStreamCandidate(info, 0, "Compatible")]
    def connect(_info):
        may_fail("connect")
        return abandoned if failure_at == "save" and calls["connect"] == 1 else source
    def save(value):
        may_fail("save")
        saved.append(value.source_id)
    monkeypatch.setattr(lsl_setup, "scan_force_streams", scan)
    monkeypatch.setattr(lsl_setup, "open_force_source", connect)
    monkeypatch.setattr(lsl_setup, "save_force_selection", save)
    stage = "scan"
    failures_seen = 0
    def interact(dialog, buttons, table):
        nonlocal stage, failures_seen
        failed = sum(name in ("source.scan.failed", "source.connection.failed") for name in markers.names)
        if failed > failures_seen:
            assert saved == [] and not dialog.okBtn.isEnabled()
            assert "source.connected" not in markers.names
            failures_seen = failed
            stage = "scan" if failure_at == "scan" else "use"
        if stage == "scan" and buttons["Add LSL Stream…"].isEnabled():
            buttons["Add LSL Stream…"].click()
            stage = "use"
        elif stage == "use" and table.rowCount():
            table.selectRow(0)
            if buttons["Use Selected Stream"].isEnabled():
                buttons["Use Selected Stream"].click()
                stage = "start"
        elif stage == "start" and dialog.okBtn.isEnabled():
            dialog.okBtn.click()
    _values, result = dialog_driver(interact, markers)
    assert failures_seen == 1 and result is source and saved == [source.source_id]
    if failure_at == "save":
        assert abandoned.inlet.closed
    source.stop()
