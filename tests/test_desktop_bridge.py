import io
import json

import pytest

from mpi.desktop_bridge import DesktopBridge, DesktopCancelled, PREFIX, validate_action


def action(seq=1, **fields):
    return {"action": "shown", "ui_seq": seq, "ui_time_ms": 5.0, **fields}


@pytest.mark.parametrize("fields", [
    {"action": "shell"}, {"ui_seq": True}, {"ui_time_ms": float("nan")},
    {"path": "anything"}, {"action": "field_edit", "field": "other", "value": "v"},
    {"action": "field_edit", "field": "participant", "value": "v" * 129},
])
def test_closed_action_contract_rejects_malformed_input(fields):
    with pytest.raises(ValueError): validate_action(action(**fields))


def test_pipe_preserves_order_then_reports_close():
    bridge = DesktopBridge(io.StringIO("\n".join(json.dumps(action(n)) for n in [1, 2]) + "\n"), io.StringIO())
    assert bridge.closed.wait(1)
    assert bridge.receive()["ui_seq"] == 1
    assert bridge.receive()["ui_seq"] == 2
    with pytest.raises(DesktopCancelled): bridge.receive(timeout=0)


def test_sequence_gap_and_queue_overload_fail_visibly():
    bridge = DesktopBridge(io.StringIO(json.dumps(action(2)) + "\n"), io.StringIO())
    assert bridge.closed.wait(1)
    with pytest.raises(ValueError, match="order"): bridge.receive()
    bridge = DesktopBridge(io.StringIO("\n".join(json.dumps(action(n)) for n in range(1, 131)) + "\n"), io.StringIO())
    assert bridge.closed.wait(1)
    with pytest.raises(RuntimeError, match="protocol"): bridge.receive()


def test_snapshots_are_framed_and_no_generic_commands_are_accepted():
    writer = io.StringIO()
    bridge = DesktopBridge(io.StringIO('{"action":"shutdown","reason":"window_closed"}\n'), writer)
    assert bridge.closed.wait(1)
    with pytest.raises(DesktopCancelled): bridge.check_cancel()
    bridge.send({"phase": "setup", "message": "Ready"})
    assert json.loads(writer.getvalue().removeprefix(PREFIX)) == {"phase": "setup", "message": "Ready"}
