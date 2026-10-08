import io
import json

import pytest

from mpi.desktop_bridge import DesktopBridge, DesktopCancelled, ExperimentStopped, PREFIX, validate_action


def action(seq=1, **fields):
    return {"action": "shown", "ui_seq": seq, "ui_time_ms": 5.0, **fields}


@pytest.mark.parametrize("fields", [
    {"action": "shell"}, {"ui_seq": True}, {"ui_time_ms": float("nan")},
    {"path": "anything"}, {"action": "field_edit", "field": "other", "value": "v"},
    {"action": "field_edit", "field": "participant", "value": "v" * 129},
    {"action": "prompt_control", "prompt_id": "run:1", "control": "shell"},
    {"action": "prompt_control", "prompt_id": "bad/path", "control": "continue"},
    {"action": "prompt_control", "prompt_id": "x" * 97, "control": "continue"},
    {"action": "prompt_control", "prompt_id": "run:1", "control": []},
])
def test_closed_action_contract_rejects_malformed_input(fields):
    with pytest.raises(ValueError): validate_action(action(**fields))


def test_record_stream_accepts_lsl_uid_only():
    assert validate_action(action(action="record_stream", uid="abc-123", enabled=False))["uid"] == "abc-123"
    for uid in ["", "a' or true()", "x" * 129]:
        with pytest.raises(ValueError):
            validate_action(action(action="record_stream", uid=uid, enabled=False))


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


def test_progress_retains_only_latest_public_metadata_without_flip_io():
    writer = io.StringIO()
    bridge = DesktopBridge(io.StringIO('{"action":"shutdown","reason":"window_closed"}\n'), writer)
    assert bridge.closed.wait(1)
    payload = {"event": "tracking.started", "seq": 1, "lsl_time": 123.5,
               "trial": 2, "condition": "normal", "phase": "tracking", "screen": None,
               "participant": "private", "value": "private"}
    bridge.note_marker(payload)
    assert writer.getvalue() == ""
    bridge.note_marker({**payload, "seq": 100})
    assert bridge._progress == {"phase": "progress", "experiment_phase": "tracking",
                               **{key: value for key, value in payload.items()
                                   if key in {"event", "lsl_time", "trial", "condition", "screen"}}, "seq": 100,
                               "recent": [{"event":"tracking.started","seq":n,"lsl_time":123.5} for n in (1,100)]}
    for n in range(101,130): bridge.note_marker({**payload,"seq":n})
    assert len(bridge._progress["recent"]) == 12
    assert bridge._progress["recent"][0]["seq"] == 118
    assert 'private' not in json.dumps(bridge._progress)


def test_stop_waits_for_cleanup_receipt_without_closing_control_pipe():
    writer = io.StringIO()
    bridge = DesktopBridge(io.StringIO(""), writer)
    assert bridge.closed.wait(1)
    bridge.closed.clear()  # Simulate an open reader without a blocking test thread.
    bridge.experiment = True
    bridge.actions.put({"action":"abort","ui_seq":1,"ui_time_ms":42.0,
                        "ui_origin":"remote","ui_client_seq":3})
    with pytest.raises(ExperimentStopped):
        bridge.check_cancel()
    assert writer.getvalue() == ""  # Request receipt is not completed cleanup.
    bridge.finish_stop()
    reply = json.loads(writer.getvalue().removeprefix(PREFIX))
    assert reply["ok"] and reply["ui_seq"] == 1
    assert not bridge.closed.is_set() and not bridge.experiment


def test_prompt_commands_are_fenced_to_visible_instance_and_ack_after_consumption():
    from types import SimpleNamespace
    events = []
    bridge = DesktopBridge(io.StringIO(""), io.StringIO())
    assert bridge.closed.wait(1)
    bridge.closed.clear()
    bridge.experiment = True
    bridge.markers = SimpleNamespace(run_id="run", sequence=1,
                                    emit=lambda name, **fields: events.append((name, fields)))
    def command(seq, prompt_id="run:1", control="continue"):
        return validate_action(action(seq, action="prompt_control", prompt_id=prompt_id,
                                      control=control, ui_origin="remote", ui_client_seq=seq))
    # Nothing can advance before the actual visible flip.
    bridge.actions.put(command(1))
    bridge.check_cancel()
    assert events[-1][1]["reason"] == "stale_prompt"
    bridge.open_prompt("instructions", ["space", "escape"])
    bridge.actions.put(command(2))
    bridge.check_cancel()
    assert len(events) == 1  # Admission is neither an effect nor an acknowledgement.
    bridge.actions.put(command(3))
    bridge.check_cancel()
    assert events[-1][1]["reason"] == "prompt_busy"
    key, accepted = bridge.take_prompt_control(["space", "escape"])
    assert key == "space" and accepted["ui_seq"] == 2
    bridge.finish_prompt_control(accepted)
    assert events[-1][1]["accepted"] is True
    assert events[-1][1]["ui_origin"] == "remote"
    bridge.close_prompt()
    bridge.markers.sequence = 20
    bridge.open_prompt("calibration_ready", ["space", "escape"])
    bridge.actions.put(command(4))  # Delayed double tap on the previous screen.
    bridge.check_cancel()
    assert bridge.take_prompt_control(["space"]) is None
    assert events[-1][1]["reason"] == "stale_prompt"
    bridge.actions.put(command(5, "run:20", "retry"))
    bridge.check_cancel()
    assert events[-1][1]["reason"] == "unavailable_control"
    bridge.open_prompt("accuracy", ["1", "2", "space"])
    assert bridge.prompt is None  # Questionnaire responses remain local.
    replies = [json.loads(line.removeprefix(PREFIX)) for line in bridge.writer.getvalue().splitlines()]
    assert [(r["ui_seq"], r["ok"]) for r in replies] == [(1, False), (3, False), (2, True), (4, False), (5, False)]


def test_pending_prompt_is_rejected_on_local_dismissal_or_stop():
    from types import SimpleNamespace
    events = []
    bridge = DesktopBridge(io.StringIO(""), io.StringIO())
    assert bridge.closed.wait(1)
    bridge.closed.clear()
    bridge.experiment = True
    bridge.markers = SimpleNamespace(run_id="run", sequence=1,
                                    emit=lambda name, **fields: events.append(fields))
    bridge.open_prompt("calibration_result", ["space", "r", "escape"])
    bridge.actions.put(action(action="prompt_control", prompt_id="run:1", control="retry"))
    bridge.check_cancel()
    bridge.actions.put(action(2, action="abort"))
    with pytest.raises(ExperimentStopped): bridge.check_cancel()
    bridge.close_prompt()
    assert bridge.take_prompt_control(["r"]) is None
    assert events[-1]["accepted"] is False and events[-1]["reason"] == "stale_prompt"
    bridge.finish_stop()
    assert not bridge.closed.is_set()


def test_late_prompt_after_stop_is_marked_and_closed_pipe_needs_no_reply():
    from types import SimpleNamespace
    events = []
    bridge = DesktopBridge(io.StringIO(''), io.StringIO())
    assert bridge.closed.wait(1)
    bridge.closed.clear()
    bridge.markers = SimpleNamespace(emit=lambda name, **fields: events.append(fields))
    request = action(action='prompt_control', prompt_id='old-run:1', control='continue')
    bridge.actions.put(request)
    assert bridge.receive() is None
    assert events[-1]['reason'] == 'stale_prompt' and not events[-1]['accepted']
    bridge.closed.set()
    bridge.writer.close()
    bridge.finish_prompt_control(request, False, 'prompt_interrupted')
    assert events[-1]['reason'] == 'prompt_interrupted'
