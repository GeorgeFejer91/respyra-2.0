"""Read the Vernier Stream Mini raw Force channel from LSL."""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree


class LSLForceError(RuntimeError):
    """The required raw force stream is missing or unusable."""


def force_channel_index(xml: str, channel_count: int) -> int:
    """Find the raw GDX-RB Force (N) channel without assuming its position."""
    root = ElementTree.fromstring(xml)
    desc = root.find("desc")
    if desc is None or desc.findtext("manufacturer") != "Vernier":
        raise LSLForceError("LSL stream is missing Vernier metadata")
    if desc.findtext("model") != "GDX-RB" or desc.findtext("stream_role") != "raw_measurement_recording":
        raise LSLForceError("LSL stream is not a raw GDX-RB recording")
    channels = desc.findall("channels/channel")
    if len(channels) != channel_count:
        raise LSLForceError("LSL channel metadata does not match the stream")
    matches = [
        index
        for index, channel in enumerate(channels)
        if channel.findtext("label") == "Force"
        and channel.findtext("unit") == "N"
        and channel.findtext("sensor_number") == "1"
        and channel.findtext("type") == "RawMeasurement"
    ]
    if len(matches) != 1:
        raise LSLForceError("Expected exactly one raw Force (N) channel 1")
    return matches[0]


def validate_force_info(info) -> int:
    """Units alone do not establish that a stream contains raw belt force."""
    from pylsl import cf_float32, cf_double64

    if info.type() != "VernierRaw":
        raise LSLForceError("Requires VernierRaw Force (N), not a derived breathing stream")
    if not info.source_id().startswith("polar-stream-vernier-raw-"):
        raise LSLForceError("Missing stable Vernier Stream Mini source ID")
    if info.channel_format() not in (cf_float32, cf_double64):
        raise LSLForceError("Raw Force must use floating-point LSL samples")
    return force_channel_index(info.as_xml(), info.channel_count())


@dataclass
class ForceStreamCandidate:
    info: object
    force_index: int | None
    reason: str


def scan_force_streams(wait_time: float = 1.0) -> list[ForceStreamCandidate]:
    """List all visible streams, with eligibility based on full channel metadata."""
    from pylsl import StreamInlet, resolve_streams

    candidates = []
    for resolved in resolve_streams(wait_time=wait_time):
        info = resolved
        inlet = None
        index = None
        try:
            if info.type() != "VernierRaw":
                raise LSLForceError("Requires VernierRaw Force (N)")
            inlet = StreamInlet(info, max_buflen=1, recover=False)
            # Full inlet info validates metadata; retain resolver info for reconnecting.
            full_info = inlet.info(timeout=1.0)
            if full_info.source_id() != info.source_id():
                raise LSLForceError("Stream identity changed during discovery")
            index = validate_force_info(full_info)
            reason = "Compatible: raw Force (N)"
        except Exception as exc:
            reason = str(exc)
        finally:
            if inlet is not None:
                inlet.close_stream()
        candidates.append(ForceStreamCandidate(info, index, reason))
    identities = Counter(item.info.source_id() for item in candidates)
    for item in candidates:
        if item.force_index is not None and identities[item.info.source_id()] > 1:
            item.force_index = None
            item.reason = "Duplicate source_id; cannot remember this stream unambiguously"
    return sorted(candidates, key=lambda item: (item.info.name().casefold(), item.info.source_id()))


def selection_path() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / ".config")) / "Respyra" / "lsl-source.json"


def load_force_selection(path: Path | None = None) -> dict | None:
    path = path or selection_path()
    if not path.exists():
        return None
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        if (saved["version"] != 1
                or not isinstance(saved["source_id"], str)
                or not saved["source_id"].startswith("polar-stream-vernier-raw-")
                or not isinstance(saved["stream_name"], str)):
            raise ValueError("Unsupported selection")
        return saved
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise LSLForceError("Saved LSL selection is invalid; choose a stream again") from exc


def save_force_selection(source, path: Path | None = None) -> None:
    """Remember only the accepted identity, never samples or participant data."""
    path = path or selection_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix="lsl-source-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump({"version": 1, "source_id": source.source_id,
                       "stream_name": source.stream_name}, handle)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class LSLForceSource:
    """Small adapter for respyra's ``get_all`` / ``stop`` phase calls."""

    def __init__(self, inlet, force_index: int, source_id: str = "", stream_name: str = "", channels=()) -> None:
        self.inlet = inlet
        self.force_index = force_index
        self.source_id = source_id
        self.stream_name = stream_name
        self.uid = ""
        self.last_force_at = time.monotonic()
        self.stopped = False
        self.channels = list(channels) or [{"index": force_index, "label": "Force", "unit": "N"}]
        self.latest_sample = None
        self.calibrated_outlet = None
        self.calibrated_id = None
        self.calibrated_uid = None
        self.calibrated_sample = None
        self.center = self.amplitude = None

    def start_derived(self, run_id):
        """Advertise the derived channel before recording; NaN means not calibrated."""
        from pylsl import StreamInfo, StreamOutlet, cf_float32
        identity = f"respyra-breathing-{run_id}"
        if self.calibrated_outlet is not None:
            if self.calibrated_id != identity:
                raise LSLForceError("A different derived breathing stream is already active")
            return
        self.calibrated_id = identity
        info = StreamInfo("Respyra-Calibrated-Breathing", "Respiration", 1, 0, cf_float32, identity)
        desc = info.desc()
        for key, value in {"application": "Respyra 2.0", "raw_source_id": self.source_id,
                           "formula": "(force_n - center_n) / amplitude_n",
                           "before_calibration": "NaN; parameters are in calibration.completed markers"}.items():
            desc.append_child_value(key, value)
        channel = desc.append_child("channels").append_child("channel")
        channel.append_child_value("label", "Calibrated breathing")
        channel.append_child_value("unit", "normalized")
        self.calibrated_outlet = StreamOutlet(info)
        self.calibrated_uid = self.calibrated_outlet.get_info().uid()

    def calibrate(self, center, amplitude, run_id):
        """Activate the accepted study calibration on the existing outlet."""
        if not math.isfinite(center) or not math.isfinite(amplitude) or amplitude <= 0:
            raise LSLForceError("Invalid breathing calibration")
        if self.calibrated_outlet is None or self.calibrated_id != f"respyra-breathing-{run_id}":
            raise LSLForceError("Derived breathing outlet was not started before recording")
        self.center, self.amplitude = center, amplitude

    def health_snapshot(self):
        """Only actual inlet freshness; the raw Force contract has no battery field."""
        age = max(0, time.monotonic() - self.last_force_at)
        preview = None
        if self.latest_sample:
            timestamp, sample = self.latest_sample
            preview = {"source_id": self.source_id, "name": self.stream_name,
                       "lsl_time": timestamp, "force_index": self.force_index,
                       "channels": [{**c, "value": float(sample[c["index"]])
                                     if c["index"] < len(sample) and math.isfinite(sample[c["index"]]) else None}
                                    for c in self.channels]}
        return {"signal": ("disconnected" if self.stopped else
                           "live" if age <= 1 else "stale" if age <= 3 else "lost"),
                "sample_age_ms": round(age * 1000), "battery_percent": None, "preview": preview,
                "calibrated": {"source_id": self.calibrated_id, "active": self.center is not None,
                               "prepared": self.calibrated_outlet is not None,
                               "lsl_time": self.calibrated_sample}}

    def get_all(self) -> list[tuple[float, float]]:
        try:
            samples, timestamps = self.inlet.pull_chunk(timeout=0.0, max_samples=1024)
        except Exception as exc:
            raise LSLForceError(f"Vernier LSL stream read failed: {exc}") from exc
        forces = []
        for sample, timestamp in zip(samples, timestamps, strict=True):
            if len(sample) > self.force_index and math.isfinite(sample[self.force_index]):
                forces.append((timestamp, float(sample[self.force_index])))
                self.latest_sample = (timestamp, list(sample))
                if self.calibrated_outlet is not None:
                    value = ((float(sample[self.force_index]) - self.center) / self.amplitude
                             if self.center is not None else math.nan)
                    self.calibrated_outlet.push_sample([value], timestamp=timestamp)
                    if self.center is not None:
                        self.calibrated_sample = timestamp
        if forces:
            self.last_force_at = time.monotonic()
        elif time.monotonic() - self.last_force_at > 3.0:
            raise LSLForceError("Vernier LSL stream has supplied no Force samples for 3 seconds")
        return forces

    def stop(self) -> None:
        self.stopped = True
        self.inlet.close_stream()
        self.calibrated_outlet = None
        self.calibrated_uid = None


def connect_force_source(timeout: float = 5.0, source_id: str | None = None) -> LSLForceSource:
    """Resolve the exact remembered/explicit identity; never substitute another."""
    from pylsl import resolve_streams

    source_id = source_id or os.environ.get("RESPYRA_LSL_SOURCE_ID")
    discovered = resolve_streams(wait_time=min(1.0, timeout))
    matches = [
        info
        for info in discovered
        if info.type() == "VernierRaw"
        and info.source_id().startswith("polar-stream-vernier-raw-")
        and (not source_id or info.source_id() == source_id)
    ]
    if len(matches) != 1:
        raise LSLForceError(
            f"Expected one Vernier Stream Mini raw LSL outlet; found {len(matches)}. "
            "Start Vernier Stream Mini in Separate Streams mode and use Add LSL Stream."
        )
    return open_force_source(matches[0], timeout=timeout)


def open_force_source(resolved, timeout: float = 5.0) -> LSLForceSource:
    """Revalidate the selected outlet and require live data before acceptance."""
    from pylsl import StreamInlet, proc_clocksync

    # Pin this outlet after validation; a restart requires fresh metadata validation.
    inlet = StreamInlet(resolved, max_buflen=2, processing_flags=proc_clocksync, recover=False)
    try:
        info = inlet.info(timeout=timeout)
        if info.source_id() != resolved.source_id():
            raise LSLForceError("Selected stream identity changed during connection")
        index = validate_force_info(info)
        channels = []
        metadata = ElementTree.fromstring(info.as_xml()).findall("./desc/channels/channel")
        for number in range(min(info.channel_count(), 32)):
            channel = metadata[number]
            channels.append({"index": number, "label": channel.findtext("label") or f"Channel {number + 1}",
                             "unit": channel.findtext("unit", "")})
        source = LSLForceSource(inlet, index, info.source_id(), info.name(), channels)
        source.uid = info.uid()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            samples, _ = inlet.pull_chunk(timeout=min(0.5, deadline - time.monotonic()))
            if any(len(sample) > index and math.isfinite(sample[index]) for sample in samples):
                source.last_force_at = time.monotonic()
                return source
        raise LSLForceError("Vernier LSL outlet is present but has no live Force samples")
    except Exception:
        inlet.close_stream()
        raise
