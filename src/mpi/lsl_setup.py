"""HTML startup controls; Python owns source validation and all LSL markers."""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from mpi.desktop_bridge import DesktopCancelled, validate_action
from mpi.recording import RecordingError
from mpi.lsl_force import (
    LSLForceError, LSLForceSource, connect_force_source, load_force_selection,
    open_force_source, save_force_selection, scan_force_streams,
)

class SetupRejected(ValueError):
    """A valid command no longer meets the current setup preconditions."""


class SourceSetup:
    def __init__(self, cfg, markers, recorder=None, cancel_check=lambda: None):
        self.cfg, self.markers = cfg, markers
        self.recorder, self.cancel_check = recorder, cancel_check
        self.values = {"participant": "", "session": "001"}
        self.save_csv = False
        self.record_keyboard = self.record_mouse = False
        self.automatic = False
        self.identity = None
        self.next_scan = 0
        self.source = self.pending = None
        self.candidates = []
        self.row = None
        self.sequence = 0
        self.shown = self.done = self.accepted = False
        self.message = "Waiting for a live VernierRaw Force stream."
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="respyra-lsl-setup")

    def restore(self):
        self.automatic = True
        try:
            saved = load_force_selection()
        except LSLForceError as exc:
            saved = None
            self.message = str(exc)
            self.markers.emit("source.memory.invalid", message=str(exc))
        if saved:
            self.markers.emit("source.memory.loaded", **saved)
        identity = os.environ.get("RESPYRA_LSL_SOURCE_ID") or (saved["source_id"] if saved else None)
        self.identity = identity
        if identity:
            origin = "environment" if os.environ.get("RESPYRA_LSL_SOURCE_ID") else "memory"
            self.message = "Reconnecting the previously configured LSL source…"
            self.markers.emit("source.connection.started", source_id=identity, origin=origin)
            self._submit(origin, lambda: connect_force_source(source_id=identity), identity)

    def _submit(self, kind, work, identity=None):
        self.pending = (self.executor.submit(work), kind, identity)

    def rows(self):
        return [{"source_id": c.info.source_id(), "stream_name": c.info.name(),
                 "stream_type": c.info.type(), "compatible": c.force_index is not None,
                 "reason": c.reason, "force_channel_index": c.force_index}
                for c in self.candidates]

    def snapshot(self):
        selected = self.candidates[self.row] if self.row is not None else None
        return {"phase": "setup", "ui_seq": self.sequence, "study_name": self.cfg.name, "values": self.values.copy(),
                "marker_name": self.markers.name, "save_csv": self.save_csv,
                "record_keyboard": self.record_keyboard, "record_mouse": self.record_mouse,
                "message": self.message, "busy": self.pending is not None,
                "can_start": bool(self.source and not self.pending and
                                  all(v.strip() for v in self.values.values())),
                "can_use": bool(selected and selected.force_index is not None and not self.pending),
                "selected_row": self.row, "streams": self.rows(),
                "source": ({"source_id": self.source.source_id,
                            "stream_name": self.source.stream_name} if self.source else None)}

    def command(self, action):
        validate_action(action)
        if self.done or action["ui_seq"] != self.sequence + 1:
            raise ValueError("Invalid setup action sequence")
        self.sequence = action["ui_seq"]
        kind = action["action"]
        ui = {key: action[key] for key in
              ("ui_seq", "ui_time_ms", "ui_origin", "ui_client_seq") if key in action}
        emit = self.markers.emit
        if kind == "shown":
            if self.shown:
                raise SetupRejected("Startup form was already shown")
            self.shown = True
            emit("participant.dialog.shown", **ui)
        elif not self.shown:
            raise SetupRejected("Setup input preceded the startup form")
        elif kind == "field_key":
            emit("participant.field.key", field=action["field"], key=action["key"], **ui)
        elif kind == "field_edit":
            if action["field"] == "marker_name":
                try:
                    self.markers.rename(action["value"])
                except ValueError as exc:
                    raise SetupRejected(str(exc)) from exc
            else:
                self.values[action["field"]] = action["value"]
            emit("participant.field.edited", field=action["field"], value=action["value"], **ui)
        elif kind == "option":
            setattr(self, action["field"], action["enabled"])
            emit("recording.option.changed", field=action["field"], enabled=action["enabled"], **ui)
        elif kind == "scan":
            if self.pending:
                raise SetupRejected("Source operation is already in progress")
            emit("source.ui.add.clicked", **ui)
            emit("source.scan.started")
            self.message = "Scanning available LSL streams…"
            self._submit("scan", scan_force_streams)
        elif kind == "select":
            if self.pending or action["row"] >= len(self.candidates):
                raise SetupRejected("Stream row is unavailable")
            self.row = action["row"]
            candidate = self.candidates[self.row]
            emit("source.ui.selection.changed", source_id=candidate.info.source_id(),
                 stream_name=candidate.info.name(), compatible=candidate.force_index is not None, **ui)
        elif kind == "use":
            if not self.snapshot()["can_use"]:
                raise SetupRejected("No compatible stream selected")
            candidate = self.candidates[self.row]
            identity = candidate.info.source_id()
            emit("source.ui.use.clicked", source_id=identity, stream_name=candidate.info.name(), **ui)
            emit("source.connection.started", source_id=identity, origin="selection")
            self.message = "Checking channel metadata and live Force samples…"
            self._submit("selection", lambda: open_force_source(candidate.info), identity)
        elif kind == "start":
            emit("participant.button.ok.clicked", **ui)
            self.poll()
            if not self.snapshot()["can_start"]:
                raise SetupRejected("Participant, session and live Force input are required")
            if self.recorder is not None:
                try:
                    self.recorder.start(self.values, self.source, self.markers, self.cancel_check)
                except (RecordingError, OSError) as exc:
                    self.message = ("Recording could not start. Check the local recording view."
                                    if isinstance(exc, OSError) else str(exc))
                    raise SetupRejected(self.message) from exc
                self.poll()  # Drain setup samples and recheck input after recorder startup.
                if not self.snapshot()["can_start"]:
                    self.recorder.stop()
                    raise SetupRejected("Force input was lost while starting the recorder")
            self.markers.name_locked = True
            emit("participant.dialog.accepted")
            emit("participant.dialog.hidden")
            self.accepted = True
            self.done = True
        elif kind == "cancel":
            emit("participant.button.cancel.clicked", **ui)
            self.reject()
        else:
            raise SetupRejected("Stop is only available during the experiment")

    def reject(self):
        if not self.done:
            self.done = True
            self.markers.emit("participant.dialog.rejected")
            if self.shown:
                self.markers.emit("participant.dialog.hidden")

    def poll(self):
        emit = self.markers.emit
        if self.source is not None:
            try:
                self.source.get_all()
            except LSLForceError as exc:
                source, self.source = self.source, None
                source.stop()
                self.row = None
                emit("source.lost", message=str(exc))
                emit("source.disconnected")
                self.message = f"{exc}\nReconnecting automatically…"
        if self.automatic and not self.done and self.source is None and self.row is None and self.pending is None and time.monotonic() >= self.next_scan:
            self.next_scan = time.monotonic() + 3
            emit("source.scan.started")
            self._submit("automatic_scan", scan_force_streams)
        if self.pending is None or not self.pending[0].done():
            return
        future, kind, identity = self.pending
        self.pending = None
        try:
            result = future.result()
            if kind in {"selection", "automatic"}:
                try:
                    save_force_selection(result)
                except Exception:
                    result.stop()
                    raise
        except Exception as exc:
            if kind in {"automatic", "memory", "environment"}:
                self.row = None
            self.message = (f"{exc}\nRetrying automatically." if self.automatic and self.row is None
                            else f"{exc}\nUse stream to retry." if kind == "selection" else str(exc))
            if kind in {"scan", "automatic_scan"}:
                emit("source.scan.failed", message=str(exc))
            else:
                emit("source.connection.failed", source_id=identity, origin=kind, message=str(exc))
            return
        if kind in {"scan", "automatic_scan"}:
            self.candidates, self.row = result, None
            eligible = sum(c.force_index is not None for c in result)
            self.message = (f"Found {len(result)} streams; {eligible} compatible. Select a row and use it."
                            if eligible else "No compatible raw Force (N) stream. Start Vernier Stream Mini, then scan again.")
            emit("source.scan.completed", streams=[{k: v for k, v in row.items() if k != "force_channel_index"}
                                                   for row in self.rows()])
            if kind == "automatic_scan":
                eligible = [i for i, candidate in enumerate(result) if candidate.force_index is not None
                            and (not self.identity or candidate.info.source_id() == self.identity)]
                if len(eligible) == 1:
                    self.row = eligible[0]
                    candidate = result[self.row]
                    emit("source.connection.started", source_id=candidate.info.source_id(), origin="automatic")
                    self._submit("memory" if self.identity else "automatic", lambda: open_force_source(candidate.info), candidate.info.source_id())
                    self.message = "Checking live breathing samples…"
                else:
                    self.message = ("Several breathing belts are available. Choose the study belt in Settings."
                                    if len(eligible) > 1 else "Waiting for Vernier Stream Mini’s raw Force stream (Separate Streams mode).")
        else:
            previous, self.source = self.source, result
            if previous is not None:
                previous.stop()
                emit("source.disconnected")
            self.message = "Ready for this experiment."
            emit("source.connected", source_id=result.source_id, stream_name=result.stream_name,
                 force_channel_index=result.force_index)
            emit("source.connection.accepted", source_id=result.source_id, origin=kind)
            self.identity = result.source_id
            if kind in {"selection", "automatic"}:
                emit("source.memory.saved", source_id=result.source_id, stream_name=result.stream_name)

    def close(self):
        self.executor.shutdown(wait=True, cancel_futures=True)
        resources, events = [], []
        if self.pending is not None:
            future, kind, identity = self.pending
            self.pending = None
            if not future.cancelled() and future.exception() is None and isinstance(future.result(), LSLForceSource):
                resources.append(future.result())
            events.append(("source.scan.cancelled", {}) if kind in {"scan", "automatic_scan"} else (
                "source.connection.cancelled", {"source_id": identity, "origin": kind}))
        if not self.accepted and self.source is not None:
            resources.append(self.source)
            self.source = None
            events.append(("source.disconnected", {}))
        error = None
        for resource in resources:
            try:
                resource.stop()
            except Exception as exc:
                error = error or exc
        for name, fields in events:
            try:
                self.markers.emit(name, **fields)
            except Exception as exc:
                error = error or exc
        if error:
            raise error


def run_source_setup(cfg, markers, bridge=None):
    """Return participant values and the same accepted inlet used during setup."""
    if bridge is None:
        raise RuntimeError("Participant setup requires the HTML desktop launcher")
    setup = SourceSetup(cfg, markers, getattr(bridge, "recorder", None), bridge.check_cancel)
    previous = None
    try:
        setup.restore()
        while not setup.done:
            setup.poll()
            bridge.source = setup.source
            snapshot = setup.snapshot()
            if snapshot != previous:
                bridge.send(snapshot)
                previous = snapshot
            action = bridge.receive()
            if action is not None:
                # A stale local/remote precondition is a rejected command, not
                # a failed study. Malformed pipe input still fails closed.
                try:
                    setup.command(action)
                except SetupRejected as exc:
                    bridge.send(setup.snapshot())
                    bridge.reply(action, False, str(exc))
                else:
                    bridge.send(setup.snapshot())
                    bridge.reply(action)
        return ({**setup.values, "save_csv": setup.save_csv,
                 "record_keyboard": setup.record_keyboard, "record_mouse": setup.record_mouse}, setup.source) if setup.accepted else (None, None)
    except DesktopCancelled:
        setup.reject()
        raise
    except Exception as exc:
        markers.emit("source.setup.failed", message=str(exc))
        setup.reject()
        raise
    finally:
        active_error = sys.exc_info()[1]
        try:
            setup.close()
        except Exception:
            if active_error is None:
                raise
