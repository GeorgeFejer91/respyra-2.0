"""Read the Vernier Stream Mini raw Force channel from LSL."""

from __future__ import annotations

import math
import os
import time
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


class LSLForceSource:
    """Small adapter for respyra's ``get_all`` / ``stop`` phase calls."""

    def __init__(self, inlet, force_index: int, source_id: str = "", stream_name: str = "") -> None:
        self.inlet = inlet
        self.force_index = force_index
        self.source_id = source_id
        self.stream_name = stream_name
        self.last_force_at = time.monotonic()

    def get_all(self) -> list[tuple[float, float]]:
        try:
            samples, timestamps = self.inlet.pull_chunk(timeout=0.0, max_samples=1024)
        except Exception as exc:
            raise LSLForceError(f"Vernier LSL stream read failed: {exc}") from exc
        forces = [
            (timestamp, float(sample[self.force_index]))
            for sample, timestamp in zip(samples, timestamps, strict=True)
            if len(sample) > self.force_index and math.isfinite(sample[self.force_index])
        ]
        if forces:
            self.last_force_at = time.monotonic()
        elif time.monotonic() - self.last_force_at > 3.0:
            raise LSLForceError("Vernier LSL stream has supplied no Force samples for 3 seconds")
        return forces

    def stop(self) -> None:
        self.inlet.close_stream()


def connect_force_source(timeout: float = 5.0) -> LSLForceSource:
    """Discover one live Vernier Stream Mini raw outlet and validate its data."""
    from pylsl import StreamInlet, proc_clocksync, resolve_byprop

    source_id = os.environ.get("RESPYRA_LSL_SOURCE_ID")
    if source_id:
        discovered = resolve_byprop("source_id", source_id, timeout=timeout)
    else:
        # Minimum 1 may return the first outlet before discovering another.
        discovered = resolve_byprop("type", "VernierRaw", minimum=2, timeout=timeout)
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
            "Start one Vernier Stream Mini in Separate Streams mode or set "
            "RESPYRA_LSL_SOURCE_ID to its exact source ID."
        )
    inlet = StreamInlet(matches[0], max_buflen=2, processing_flags=proc_clocksync)
    try:
        info = inlet.info(timeout=timeout)
        index = force_channel_index(info.as_xml(), info.channel_count())
        source = LSLForceSource(inlet, index, info.source_id(), info.name())
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
