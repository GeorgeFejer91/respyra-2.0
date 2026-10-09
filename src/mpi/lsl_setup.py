"""HTML startup controls; Python owns source validation and all LSL markers."""

from __future__ import annotations

import os
import json
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from mpi.desktop_bridge import DesktopCancelled, validate_action
from mpi import diagnostics
from mpi.recording import RecordingError, participant_number, recorded_participant_numbers
from mpi.lsl_force import (
    LSLForceError, LSLForceSource, connect_force_source, load_force_selection,
    open_force_source, save_force_selection, scan_force_streams,
)

class SetupRejected(ValueError):
    """A valid command no longer meets the current setup preconditions."""


def fields_path():
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / ".config")) / "Respyra" / "experiment-fields.json"


def recording_folder_path():
    return fields_path().with_name("recording-folder.json")


def load_recording_folder():
    path = recording_folder_path()
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        folder = value["folder"]
        if value["version"] != 1 or not isinstance(folder, str) or not Path(folder).is_absolute():
            raise ValueError("Invalid recording folder")
        return Path(folder)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SetupRejected("Saved recording folder is invalid; choose a folder again") from exc


def save_recording_folder(folder):
    path = recording_folder_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix="recording-folder-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump({"version": 1, "folder": str(folder)}, handle, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def valid_variables(variables):
    return (isinstance(variables, list) and len(variables) <= 6
            and all(isinstance(row, dict) and row.keys() == {"label", "value"}
                    and all(isinstance(row[key], str) and len(row[key]) <= 128 for key in ("label", "value"))
                    for row in variables))


def save_fields(values, variables):
    path = fields_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix="experiment-fields-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump({"version": 1, "values": values, "variables": variables}, handle, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_fields():
    path = fields_path()
    if not path.exists():
        return None
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        values = saved["values"]
        if (saved["version"] != 1 or not isinstance(values, dict)
                or values.keys() != {"participant", "session"}
                or any(not isinstance(value, str) or len(value) > 128 for value in values.values())
                or not valid_variables(saved["variables"])):
            raise ValueError("Invalid experiment fields")
        return values, saved["variables"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SetupRejected("Saved experiment fields are invalid; edit them again") from exc


class SourceSetup:
    def __init__(self, cfg, markers, recorder=None, cancel_check=lambda: None):
        self.cfg, self.markers = cfg, markers
        self.recorder, self.cancel_check = recorder, cancel_check
        self.values = {"participant": "", "session": "001"}
        self.recorded_participants = []
        self.variables = []
        self.save_csv = True
        self.record_keyboard = self.record_mouse = False
        self.compare_inputs = True
        self.troubleshooting = diagnostics.enabled()
        self.polar_inverted = self.polar_direction_set = False
        self.excluded_streams = set()
        self.automatic = False
        self.identity = None
        self.next_scan = 0
        self.source = self.pending = None
        self.candidates = []
        self.row = None
        self.sequence = 0
        self.shown = self.done = self.accepted = False
        self.message = "Waiting for a live Vernier Force or Polar breathing waveform."
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="respyra-lsl-setup")

    def restore(self):
        self.automatic = True
        if self.recorder is not None and hasattr(self.recorder, "output"):
            try:
                saved_folder = load_recording_folder()
                if saved_folder is not None:
                    self.recorder.output = saved_folder
                self.recorded_participants = recorded_participant_numbers(self.recorder.output)
            except (RecordingError, SetupRejected) as exc:
                self.recorded_participants = None
                self.message = str(exc)
        try:
            saved_fields = load_fields()
            if saved_fields:
                self.values, self.variables = saved_fields
                self.values["session"] = "001"
        except SetupRejected as exc:
            self.message = str(exc)
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
            contract = saved.get("contract_id") if saved and not os.environ.get("RESPYRA_LSL_SOURCE_ID") else None
            self._submit(origin, lambda: connect_force_source(source_id=identity, **({"contract_id": contract} if contract else {})), identity)

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
                "recorded_participants": self.recorded_participants,
                "variables": [row.copy() for row in self.variables],
                "marker_name": self.markers.name, "save_csv": self.save_csv,
                "output_folder": str(getattr(self.recorder, "output", "")),
                "record_keyboard": self.record_keyboard, "record_mouse": self.record_mouse,
                "compare_inputs": self.compare_inputs,
                "troubleshooting": self.troubleshooting,
                "polar_inverted": self.polar_inverted,
                "polar_direction_set": self.polar_direction_set,
                "excluded_streams": sorted(self.excluded_streams),
                "message": self.message, "busy": self.pending is not None,
                "can_start": bool(self.source and self.recorded_participants is not None and not self.pending and
                                  (not getattr(self.source, "contract_id", None) or self.polar_direction_set) and
                                  participant_number(self.values["participant"]) is not None and
                                  all(row["label"].strip() and row["value"].strip() for row in self.variables) and
                                  len({row["label"].strip().casefold() for row in self.variables}) == len(self.variables)),
                "can_use": bool(selected and selected.force_index is not None and not self.pending),
                "selected_row": self.row, "streams": self.rows(),
                "source": ({"source_id": self.source.source_id,
                            "stream_name": self.source.stream_name,
                            "contract_id": getattr(self.source, "contract_id", "vernier-force/1")} if self.source else None)}

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
                if action["field"] == "participant" and action["value"] and participant_number(action["value"]) is None:
                    raise SetupRejected("Choose a participant number from 0 to 100")
                if action["field"] == "variables":
                    try:
                        variables = json.loads(action["value"])
                    except ValueError as exc:
                        raise SetupRejected("Invalid custom variables") from exc
                    if not valid_variables(variables):
                        raise SetupRejected("Use at most six custom variables with labels and values up to 128 characters")
                    try:
                        save_fields(self.values, variables)
                    except OSError as exc:
                        raise SetupRejected("Experiment fields could not be saved") from exc
                    self.variables = variables
                else:
                    values = {**self.values, action["field"]: action["value"]}
                    try:
                        save_fields(values, self.variables)
                    except OSError as exc:
                        raise SetupRejected("Experiment fields could not be saved") from exc
                    self.values = values
            emit("participant.field.edited", field=action["field"], value=action["value"], **ui)
        elif kind == "option":
            if action["field"] == "troubleshooting":
                if action.get("ui_origin") == "remote":
                    raise SetupRejected("Troubleshooting mode is a local preference")
                try:
                    diagnostics.save_enabled(action["enabled"])
                except OSError as exc:
                    raise SetupRejected("Troubleshooting preference could not be saved") from exc
            if action["field"] == "save_csv":
                raise SetupRejected("CSV is saved automatically with every recording")
            if action["field"] == "polar_inverted":
                if self.source is None or not getattr(self.source, "contract_id", None):
                    raise SetupRejected("Choose a Polar breathing input before setting inhale direction")
                self.polar_direction_set = True
                self.source.polarity = -1 if action["enabled"] else 1
            setattr(self, action["field"], action["enabled"])
            emit("source.polarity.set" if action["field"] == "polar_inverted" else "recording.option.changed",
                 field=action["field"], enabled=action["enabled"], **ui)
        elif kind == "recording_folder":
            if self.recorder is None or self.recorder.process is not None or action.get("ui_origin") != "local":
                raise SetupRejected("Recording folder can only be changed from the local setup window")
            folder = Path(action["path"])
            if not folder.is_absolute() or not folder.is_dir():
                raise SetupRejected("Choose an existing recording folder")
            try:
                with tempfile.NamedTemporaryFile(dir=folder, prefix="respyra-write-check-", delete=True):
                    pass
                participants = recorded_participant_numbers(folder)
                save_recording_folder(folder)
            except (OSError, RecordingError) as exc:
                raise SetupRejected("Recording folder is unavailable or not writable") from exc
            self.recorder.output = folder
            self.recorded_participants = participants
            self.message = "Recording folder updated."
        elif kind == "record_stream":
            if action["enabled"]:
                self.excluded_streams.discard(action["uid"])
            elif len(self.excluded_streams) < 128:
                self.excluded_streams.add(action["uid"])
            else:
                raise SetupRejected("Too many excluded LSL streams")
            emit("recording.stream.changed", uid=action["uid"], enabled=action["enabled"], **ui)
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
            self.message = "Checking source metadata and live breathing samples…"
            self._submit("selection", lambda: open_force_source(candidate.info), identity)
        elif kind == "start":
            emit("participant.button.ok.clicked", **ui)
            self.poll()
            if not self.snapshot()["can_start"]:
                raise SetupRejected("Participant, session and a calibrated-ready breathing input are required")
            if self.recorder is not None:
                try:
                    self.source.start_derived(self.markers.run_id)
                    if self.compare_inputs and isinstance(self.source, LSLForceSource):
                        from mpi.parallel_inputs import ParallelInputs
                        self.source.comparisons = ParallelInputs.discover(
                            self.source, self.markers, self.excluded_streams)
                    self.recorder.start({**self.values, "variables": self.variables}, self.source, self.markers,
                                        self.cancel_check, self.excluded_streams)
                except (RecordingError, LSLForceError, OSError) as exc:
                    comparisons = getattr(self.source, "comparisons", None)
                    if comparisons is not None:
                        comparisons.close()
                        self.source.comparisons = None
                    self.message = ("Recording could not start. Check the local recording view."
                                    if isinstance(exc, OSError) else str(exc))
                    raise SetupRejected(self.message) from exc
                self.poll()  # Drain setup samples and recheck input after recorder startup.
                if not self.snapshot()["can_start"]:
                    self.recorder.stop()
                    raise SetupRejected("Breathing input was lost while starting the recorder")
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
                            if eligible else "No compatible breathing input. Start a Mini streamer and select an eligible output.")
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
                    self.message = ("Several breathing inputs are available. Choose one in the LSL streams panel."
                                    if len(eligible) > 1 else "Waiting for a compatible Vernier Force or Polar waveform outlet.")
        else:
            previous, self.source = self.source, result
            self.polar_direction_set = False
            self.polar_inverted = False
            if previous is not None:
                previous.stop()
                emit("source.disconnected")
            self.message = "Ready for this experiment."
            emit("source.connected", source_id=result.source_id, stream_name=result.stream_name,
                 force_channel_index=(None if getattr(result, "contract_id", None) else result.force_index),
                 input_contract=getattr(result, "contract_id", "vernier-force/1"))
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
            bridge.troubleshooting = setup.troubleshooting
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
                    bridge.troubleshooting = setup.troubleshooting
                    bridge.send(setup.snapshot())
                    bridge.reply(action)
        return ({**setup.values, "variables": setup.variables, "save_csv": setup.save_csv,
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
