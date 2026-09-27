"""Private, bounded JSON control pipe between the desktop shell and Python.

Only this thread's consumer publishes markers. The reader never touches LSL.
"""

from __future__ import annotations

import json
import math
import os
import queue
import threading


PREFIX = "RESPYRA/1 "
FIELDS = {"participant", "session"}
ACTION_FIELDS = {
    "shown": set(), "field_key": {"field", "key"},
    "field_edit": {"field", "value"}, "scan": set(), "select": {"row"},
    "use": set(), "start": set(), "cancel": set(), "abort": set(),
}


class DesktopCancelled(Exception):
    """The owning desktop window closed or its control pipe disappeared."""


class ExperimentStopped(DesktopCancelled):
    """An experimenter requested cleanup without closing the control window."""


def isolate_control_input(reader):
    """Keep the pipe private; library subprocesses inherit null stdin.

    Windows Git can block on an inherited pipe another thread is reading.
    Duplicating the pipe and replacing fd 0 also prevents child tools from
    accidentally consuming desktop commands.
    """
    control = os.fdopen(os.dup(reader.fileno()), "r", encoding="utf-8")
    with open(os.devnull, "r") as null:
        os.dup2(null.fileno(), reader.fileno())
    return control


def validate_action(action):
    if not isinstance(action, dict) or action.get("action") not in ACTION_FIELDS:
        raise ValueError("Unknown desktop action")
    expected = ACTION_FIELDS[action["action"]] | {"action", "ui_seq", "ui_time_ms"}
    metadata = {"ui_origin", "ui_client_seq"}
    if action.keys() not in (expected, expected | metadata):
        raise ValueError("Unexpected desktop action fields")
    if "ui_origin" in action and (
        action["ui_origin"] not in {"local", "remote"}
        or type(action["ui_client_seq"]) is not int or action["ui_client_seq"] < 1
    ):
        raise ValueError("Invalid UI origin")
    if type(action["ui_seq"]) is not int or action["ui_seq"] < 1:
        raise ValueError("Invalid UI sequence")
    timestamp = action["ui_time_ms"]
    if type(timestamp) not in (int, float) or not math.isfinite(timestamp) or timestamp < 0:
        raise ValueError("Invalid UI timestamp")
    if "field" in action and action["field"] not in FIELDS:
        raise ValueError("Unknown participant field")
    for key in ("key", "value"):
        if key in action and (not isinstance(action[key], str) or len(action[key]) > 128):
            raise ValueError("Invalid participant input")
    if "row" in action and (type(action["row"]) is not int or action["row"] < 0):
        raise ValueError("Invalid stream row")
    return action


class DesktopBridge:
    def __init__(self, reader, writer):
        self.writer = writer
        self.actions = queue.Queue(maxsize=128)
        self.closed = threading.Event()
        self.error = None
        self.sequence = 0
        self.close_reason = "window_closed"
        self.close_marked = False
        self._write_lock = threading.Lock()
        self._progress = None
        self.source = None
        self.experiment = False
        self.stop_action = None
        self.stopped = False
        threading.Thread(target=self._read, args=(reader,), daemon=True,
                         name="respyra-desktop-control").start()

    def _read(self, reader):
        try:
            while True:
                line = reader.readline(16385)
                if not line:
                    break
                if len(line) > 16384 or not line.endswith("\n"):
                    raise ValueError("Oversized or incomplete desktop command")
                action = json.loads(line)
                if isinstance(action, dict) and action.get("action") == "shutdown":
                    if action.keys() != {"action", "reason"} or action["reason"] not in {
                        "close_button", "window_closed", "protocol_failure", "engine_failed",
                    }:
                        raise ValueError("Invalid desktop shutdown")
                    self.close_reason = action["reason"]
                    break
                self.actions.put_nowait(validate_action(action))
        except Exception as exc:
            self.error = exc
        finally:
            self.closed.set()

    def check_cancel(self):
        if self.error is not None:
            raise RuntimeError("Desktop control protocol failed") from self.error
        if self.closed.is_set():
            raise DesktopCancelled("Desktop window closed")
        if self.experiment:
            try:
                action = self.actions.get_nowait()
            except queue.Empty:
                return
            self._accept_sequence(action)
            if action["action"] == "abort":
                self.stop_action = action
                self.stopped = True
                raise ExperimentStopped("Stopped by experimenter")
            self.reply(action, False, "Setup is no longer available")

    def _accept_sequence(self, action):
        if action["ui_seq"] != self.sequence + 1:
            raise ValueError("Desktop actions arrived out of order")
        self.sequence = action["ui_seq"]

    def receive(self, timeout=0.025):
        if self.error is not None:
            self.check_cancel()
        try:
            action = self.actions.get(timeout=timeout)
        except queue.Empty:
            self.check_cancel()
            return None
        self._accept_sequence(action)
        return action

    def reply(self, action, ok=True, message=None):
        self.send({"phase": "action_result", "ui_seq": action["ui_seq"],
                   "ok": ok, "message": message})

    def finish_stop(self, error=None):
        self.experiment = False
        if self.stop_action is not None:
            action, self.stop_action = self.stop_action, None
            self.reply(action, error is None, str(error) if error else None)

    def send(self, snapshot):
        line = json.dumps(snapshot, separators=(",", ":"), allow_nan=False)
        if len(line.encode("utf-8")) > 1_000_000:
            raise ValueError("Oversized desktop state")
        with self._write_lock:
            self.writer.write(PREFIX + line + "\n")
            self.writer.flush()

    def note_marker(self, payload):
        """Replace the observer projection; no pipe/network I/O on a display flip."""
        latest = {
            key: payload[key] for key in
            ("event", "seq", "lsl_time", "trial", "condition", "screen")
        }
        latest.update(phase="progress", experiment_phase=payload["phase"])
        self._progress = latest

    def start_progress(self):
        def publish():
            while not self.closed.wait(0.25):
                if self._progress is None:
                    continue  # Preserve the recorder readiness gate.
                latest = dict(self._progress)
                latest["health"] = (self.source.health_snapshot() if self.source else
                                    {"signal": "not_selected", "sample_age_ms": None,
                                     "battery_percent": None})
                try:
                    self.send(latest)
                except Exception as exc:
                    self.error = exc
                    self.closed.set()
        threading.Thread(target=publish, daemon=True,
                         name="respyra-viewer-projection").start()

    def mark_close(self, markers):
        if not self.close_marked:
            self.close_marked = True
            if self.close_reason == "close_button":
                markers.emit("ui.wrapper.close_button.clicked")
            markers.emit("ui.wrapper.closed", reason=self.close_reason)
