"""Native LabRecorder supervision; Python owns the experiment/recording lifecycle."""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import threading
import time
from uuid import uuid4
import xml.etree.ElementTree as ET


class RecordingError(RuntimeError):
    pass


def _integer(handle):
    width = handle.read(1)
    if width not in (b"\x01", b"\x04", b"\x08"):
        raise RecordingError("Invalid XDF length")
    data = handle.read(width[0])
    if len(data) != width[0]:
        raise RecordingError("Truncated XDF length")
    return int.from_bytes(data, "little")


def inspect_xdf(path, required=()):
    """Verify chunk boundaries, headers, actual sample counts and closed footers.

    Samples stay on disk. This is a completion check, not an XDF importer/writer.
    """
    streams = {}
    size = Path(path).stat().st_size
    with Path(path).open("rb") as handle:
        if handle.read(4) != b"XDF:":
            raise RecordingError("Recording has no XDF header")
        while handle.tell() < size:
            length = _integer(handle)
            end = handle.tell() + length
            if length < 2 or end > size:
                raise RecordingError("Truncated XDF chunk")
            tag = int.from_bytes(handle.read(2), "little")
            if tag in (2, 3, 4, 6):
                if length < 6:
                    raise RecordingError("Invalid XDF stream chunk")
                stream_id = int.from_bytes(handle.read(4), "little")
                if tag == 2:
                    if length > 1_000_000 or stream_id in streams:
                        raise RecordingError("Invalid XDF stream header")
                    info = ET.fromstring(handle.read(end - handle.tell()))
                    streams[stream_id] = {"source_id": info.findtext("source_id", ""),
                        "name": info.findtext("name", ""), "sample_count": 0,
                        "clock_offsets": 0, "footer": None}
                elif stream_id not in streams:
                    raise RecordingError("XDF data precedes its stream header")
                elif tag == 3:
                    streams[stream_id]["sample_count"] += _integer(handle)
                elif tag == 4:
                    streams[stream_id]["clock_offsets"] += 1
                else:
                    if length > 1_000_000 or streams[stream_id]["footer"] is not None:
                        raise RecordingError("Invalid XDF footer")
                    info = ET.fromstring(handle.read(end - handle.tell()))
                    streams[stream_id]["footer"] = int(info.findtext("sample_count", "-1"))
            if handle.tell() > end:
                raise RecordingError("Invalid XDF sample count")
            handle.seek(end)
    if not streams or any(s["footer"] != s["sample_count"] for s in streams.values()):
        raise RecordingError("Recording is incomplete: missing or inconsistent XDF footer")
    for identity in required:
        matches = [s for s in streams.values() if s["source_id"] == identity]
        if len(matches) != 1 or not matches[0]["sample_count"]:
            raise RecordingError("Recording is missing required stream data")
    return list(streams.values())


class NativeRecording:
    def __init__(self, runtime, output):
        self.runtime, self.output = Path(runtime), Path(output)
        self.process = None
        self.path = None
        self.phase = "idle"
        self.error = None
        self.streams = {}
        self.data_sources = set()
        self.required = ()
        self.summary = []
        self._lock = threading.Lock()
        self._reader = None

    def snapshot(self):
        with self._lock:
            try:
                size = self.path.stat().st_size if self.path else 0
            except OSError:
                size = 0
            return {"phase": self.phase, "error": self.error,
                    "output_file": str(self.path) if self.path else None,
                    "bytes_written": size,
                    "streams": [{"source_id": identity, "name": name} for identity, name in self.streams.items()],
                    "data_sources": sorted(self.data_sources),
                    "summary": list(self.summary)}

    def check_health(self):
        with self._lock:
            if self.process is not None and self.phase in {"preparing", "recording"} and self.process.poll() is not None:
                self.error = "Native recorder exited before the recording was finalized."
                self.phase = "error"
            if self.error:
                raise RecordingError(self.error)

    def _read(self):
        while True:
            raw = self.process.stderr.readline(16385)
            if not raw:
                break
            if len(raw) > 16384:
                with self._lock:
                    self.error = "Oversized native recorder message."
                    self.phase = "error"
                return
            line = raw.decode("utf-8", errors="replace").strip()
            with self._lock:
                if line.startswith("RESPIRA_RECORDER/1 "):
                    try:
                        identity, name = (bytes.fromhex(s).decode("utf-8") for s in line.split()[1:])
                        if len(self.streams) >= 512 and identity not in self.streams:
                            raise ValueError("Too many streams")
                        self.streams[identity] = name
                    except (ValueError, UnicodeError):
                        self.error = "Invalid native recorder readiness message."
                elif line.startswith("RESPIRA_RECORDER_DATA/1 "):
                    try:
                        self.data_sources.add(bytes.fromhex(line.split()[1]).decode("utf-8"))
                    except (ValueError, UnicodeError, IndexError):
                        self.error = "Invalid native recorder data message."
                elif "RESPIRA_RECORDER_ERROR" in line:
                    self.error = "Native recording failed; the partial XDF has been preserved."
                if self.error:
                    self.phase = "error"

    def start(self, values, source, markers, cancel_check=lambda: None):
        if self.process is not None:
            raise RecordingError("A native recording is already active")
        self.path = None
        self.phase, self.error, self.streams, self.summary = "preparing", None, {}, []
        self.data_sources = set()
        try:
            executable = self.runtime / "respyrecorder.exe"
            if not executable.is_file() or not (self.runtime / "lsl.dll").is_file():
                raise RecordingError("Native recorder is missing. Reinstall Respira or run pnpm prepare:recorder.")
            self.output.mkdir(parents=True, exist_ok=True)
            safe = lambda value: re.sub(r"[^A-Za-z0-9_-]", "-", value)[:32] or "session"
            self.path = self.output / f"respyra-{safe(values['participant'])}-{safe(values['session'])}-{uuid4().hex}.xdf.partial"
            self.required = (source.source_id, markers.health_snapshot()["source_id"])
            self.process = subprocess.Popen([str(executable), str(self.path.resolve())],
                cwd=self.runtime, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            self._reader = threading.Thread(target=self._read, daemon=True, name="respyrecorder")
            self._reader.start()
            deadline = time.monotonic() + 8
            while True:
                cancel_check()
                self.check_health()
                with self._lock:
                    ready = all(identity in self.streams for identity in self.required) and source.source_id in self.data_sources
                if ready:
                    self.phase = "recording"
                    markers.name_locked = True
                    markers.emit("recording.started", source_ids=list(self.required), policy="all_visible_and_late")
                    self.wait_for_data(self.required[1], cancel_check=cancel_check)
                    return
                if time.monotonic() >= deadline:
                    raise RecordingError("Recorder could not subscribe to Force and markers; experiment has not started.")
                time.sleep(0.025)
        except BaseException as exc:
            if self.process is not None:
                try:
                    self.stop()
                except RecordingError:
                    pass
            else:
                self.phase, self.error = "error", str(exc)
            raise

    def wait_for_data(self, identity, poll=lambda: None, cancel_check=lambda: None):
        deadline = time.monotonic() + 8
        while True:
            cancel_check()
            self.check_health()
            poll()
            with self._lock:
                if identity in self.data_sources:
                    if identity not in self.required:
                        self.required = (*self.required, identity)
                    return
            if time.monotonic() >= deadline:
                raise RecordingError("Recorder has received no samples from a required LSL stream")
            time.sleep(.025)

    def stop(self):
        process = self.process
        if process is None:
            return
        self.phase = "finalizing"
        try:
            if process.poll() is None:
                # Allow the native chunk reader to receive the last cleanup markers.
                time.sleep(0.6)
                process.stdin.write(b"\n")
                process.stdin.flush()
                process.stdin.close()
            code = process.wait(timeout=10)
            if self._reader:
                self._reader.join(timeout=1)
            if code or self.error:
                raise RecordingError(self.error or "Native recorder failed to close its XDF file")
            self.summary = inspect_xdf(self.path, self.required)
            final = self.path.with_suffix("")
            if final.exists():
                raise RecordingError("Recording destination already exists")
            self.path.rename(final)
            self.path = final
            self.phase = "complete"
        except (OSError, ValueError, ET.ParseError, RecordingError, subprocess.TimeoutExpired) as exc:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)
            self.phase = "error"
            self.error = f"{exc}. Partial recording preserved."
            raise RecordingError(self.error) from exc
        finally:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            if self._reader:
                self._reader.join(timeout=1)
            process.stderr.close()
            self.process = None
