"""Setup authority checks use the same controller driven by the HTML form."""
import threading
import time
from types import SimpleNamespace

import pytest

from mpi import lsl_setup
from mpi.event_markers import CATALOG
from mpi.lsl_force import ForceStreamCandidate, LSLForceError, LSLForceSource


class Collector:
    name = "Respyra-Events"
    def __init__(self): self.events = []
    def emit(self, name, **fields):
        assert name in CATALOG["events"]
        assert set(CATALOG["events"][name]["fields"]) <= fields.keys()
        self.events.append((name, fields))
    @property
    def names(self): return [name for name, _ in self.events]


def live_source():
    class Inlet:
        closed = failed = False
        def pull_chunk(self, **_kwargs):
            if self.failed: raise RuntimeError("synthetic source disappeared")
            return [[5.0]], [time.monotonic()]
        def close_stream(self): self.closed = True
    return LSLForceSource(Inlet(), 0, "polar-stream-vernier-raw-test", "Test Force")


def send(setup, kind, **fields):
    setup.command({"action": kind, "ui_seq": setup.sequence + 1,
                   "ui_time_ms": float(setup.sequence), **fields})


def finish(setup):
    deadline = time.monotonic() + 3
    while setup.pending:
        assert time.monotonic() < deadline
        setup.poll()
        time.sleep(0.001)


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.delenv("RESPYRA_LSL_SOURCE_ID", raising=False)
    monkeypatch.setattr(lsl_setup, "load_force_selection", lambda: None)
    controller = lsl_setup.SourceSetup(SimpleNamespace(name="Test Study"), Collector())
    yield controller
    controller.close()


@pytest.mark.parametrize("saved_state", ["none", "missing", "corrupt"])
def test_scan_rejects_wrong_units_and_remembers_only_live_selection(monkeypatch, setup, saved_state):
    source, saved = live_source(), []
    good = SimpleNamespace(name=lambda: "Force", type=lambda: "VernierRaw", source_id=lambda: source.source_id)
    bad = SimpleNamespace(name=lambda: "Normalized", type=lambda: "Respiration", source_id=lambda: "processed")
    monkeypatch.setattr(lsl_setup, "scan_force_streams", lambda: [
        ForceStreamCandidate(bad, None, "Requires Force in N"), ForceStreamCandidate(good, 0, "Compatible")])
    monkeypatch.setattr(lsl_setup, "open_force_source", lambda info: source if info is good else pytest.fail("wrong source"))
    monkeypatch.setattr(lsl_setup, "save_force_selection", lambda value: saved.append(value.source_id))
    if saved_state == "missing":
        monkeypatch.setattr(lsl_setup, "load_force_selection", lambda: {"source_id": "absent", "stream_name": "Absent"})
        def missing(**_kwargs): raise LSLForceError("Saved stream is absent")
        monkeypatch.setattr(lsl_setup, "connect_force_source", missing)
    elif saved_state == "corrupt":
        def corrupt(): raise LSLForceError("Saved selection is invalid")
        monkeypatch.setattr(lsl_setup, "load_force_selection", corrupt)
    setup.restore()
    finish(setup)
    send(setup, "shown")
    send(setup, "field_edit", field="participant", value="test")
    assert not setup.snapshot()["can_start"] and not saved
    send(setup, "scan")
    finish(setup)
    send(setup, "select", row=0)
    assert not setup.snapshot()["can_use"]
    with pytest.raises(ValueError, match="compatible"): send(setup, "use")
    send(setup, "select", row=1)
    send(setup, "use")
    finish(setup)
    assert saved == [source.source_id] and setup.snapshot()["can_start"]
    send(setup, "start")
    assert setup.accepted and setup.values == {"participant": "test", "session": "001"}
    names = setup.markers.names
    assert names.index("source.scan.started") < names.index("source.scan.completed")
    assert names.index("source.ui.use.clicked") < names.index("source.connected") < names.index("participant.dialog.accepted")
    if saved_state == "missing": assert "source.connection.failed" in names
    if saved_state == "corrupt": assert "source.memory.invalid" in names
    setup.close()
    assert not source.inlet.closed
    source.stop()


@pytest.mark.parametrize("lose_source", [False, True])
def test_saved_identity_reconnects_without_resaving_and_loss_gates_start(monkeypatch, setup, lose_source):
    source = live_source()
    monkeypatch.setattr(lsl_setup, "load_force_selection", lambda: {"source_id": source.source_id, "stream_name": source.stream_name})
    calls = []
    def connect(source_id):
        calls.append(source_id)
        return source
    monkeypatch.setattr(lsl_setup, "connect_force_source", connect)
    monkeypatch.setattr(lsl_setup, "save_force_selection", lambda _: pytest.fail("Memory was rewritten"))
    setup.restore()
    finish(setup)
    send(setup, "shown")
    assert not setup.snapshot()["can_start"]
    send(setup, "field_edit", field="participant", value="repeat")
    assert setup.snapshot()["can_start"]
    if lose_source:
        source.inlet.failed = True
        setup.poll()
        assert not setup.snapshot()["can_start"] and source.inlet.closed
        assert "source.lost" in setup.markers.names
        send(setup, "cancel")
    else:
        send(setup, "start")
        source.stop()
    assert calls == [source.source_id] and "source.scan.started" not in setup.markers.names


def test_cancel_pending_connection_closes_result_without_saving(monkeypatch, setup):
    source, gate, entered = live_source(), threading.Event(), threading.Event()
    info = SimpleNamespace(name=lambda: "Force", type=lambda: "VernierRaw", source_id=lambda: source.source_id)
    monkeypatch.setattr(lsl_setup, "scan_force_streams", lambda: [ForceStreamCandidate(info, 0, "Compatible")])
    def connect(_info):
        entered.set()
        assert gate.wait(3)
        return source
    monkeypatch.setattr(lsl_setup, "open_force_source", connect)
    monkeypatch.setattr(lsl_setup, "save_force_selection", lambda _: pytest.fail("Cancelled input saved"))
    send(setup, "shown")
    send(setup, "scan")
    finish(setup)
    send(setup, "select", row=0)
    send(setup, "use")
    assert entered.wait(1)
    send(setup, "cancel")
    gate.set()
    setup.close()
    assert source.inlet.closed and "source.connection.cancelled" in setup.markers.names


@pytest.mark.parametrize("failure_at", ["scan", "connect", "save"])
def test_recoverable_failures_leave_retry_available(monkeypatch, setup, failure_at):
    source, abandoned, saved = live_source(), live_source(), []
    calls = {"scan": 0, "connect": 0, "save": 0}
    info = SimpleNamespace(name=lambda: "Force", type=lambda: "VernierRaw", source_id=lambda: source.source_id)
    def may_fail(kind):
        calls[kind] += 1
        if kind == failure_at and calls[kind] == 1: raise LSLForceError("synthetic failure")
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
    send(setup, "shown")
    for _ in range(2):
        send(setup, "scan")
        finish(setup)
        if setup.candidates:
            send(setup, "select", row=0)
            send(setup, "use")
            finish(setup)
        if saved: break
        assert not setup.snapshot()["can_start"] and "source.connected" not in setup.markers.names
    assert saved == [source.source_id] and setup.source is source
    if failure_at == "save": assert abandoned.inlet.closed


def test_marker_failure_does_not_leak_handed_off_source(monkeypatch, setup):
    source = live_source()
    setup.source = source
    send(setup, "shown")
    send(setup, "field_edit", field="participant", value="p")
    original = setup.markers.emit
    def failing(name, **fields):
        if name == "participant.dialog.accepted": raise RuntimeError("Recorder disconnected")
        original(name, **fields)
    monkeypatch.setattr(setup.markers, "emit", failing)
    with pytest.raises(RuntimeError, match="Recorder"): send(setup, "start")
    setup.close()
    assert source.inlet.closed and not setup.accepted
