"""Identify signed breathing waveforms by format and metadata, never names."""

from __future__ import annotations

import math
import hashlib
import time
from collections import deque
from xml.etree import ElementTree

from mpi.lsl_force import LSLForceError, LSLForceSource, calibrated_stream_name


POLAR_CONTRACTS = {"respyra-polar-pca/1": 1, "respyra-polar-phan-signed/1": 2}


def bundled_polar_layout(desc, channel_count, contract):
    """Bind waveform and same-row readiness by channel metadata, never labels."""
    channels = desc.findall("channels/channel")
    ids = [channel.findtext("metric_id") for channel in channels]
    required = {"adr_pca_valid"}
    if contract == "respyra-polar-phan-signed/1":
        required.add("adr_axis_difference_valid")
    declared = set(filter(None, (desc.findtext("validity_channels") or "").split(",")))
    waveform = desc.findtext("waveform_channel")
    if (len(channels) != channel_count or not all(ids) or len(set(ids)) != len(ids)
            or waveform not in ids or declared != required
            or not required.issubset(ids) or "adr_pca_quality" not in ids):
        raise LSLForceError("Polar bundled channel metadata does not match its input contract")
    index = ids.index(waveform)
    if channels[index].findtext("unit") != "g" or channels[index].findtext("role") != "waveform":
        raise LSLForceError("Polar bundled waveform must be signed g")
    validity = tuple(ids.index(metric) for metric in sorted(required))
    if any(channels[i].findtext("unit") != "0/1" or channels[i].findtext("role") != "validity"
           for i in validity):
        raise LSLForceError("Polar bundled validity channels must be 0/1")
    quality = channels[ids.index("adr_pca_quality")]
    if quality.findtext("unit") not in {"0–1", "0-1"} or quality.findtext("role") != "quality":
        raise LSLForceError("Polar bundled quality channel must be 0–1")
    return index, validity, [dict(index=i, label=c.findtext("label") or ids[i],
                                  unit=c.findtext("unit"), metric_id=ids[i], role=c.findtext("role"))
                             for i, c in enumerate(channels)]


def validate_polar_info(info) -> tuple[str, tuple[str, ...]]:
    """Return a compatible waveform contract and its declared validity references."""
    from pylsl import cf_float32, cf_double64

    if info.channel_format() not in (cf_float32, cf_double64):
        raise LSLForceError("Requires a floating-point breathing waveform")
    if not math.isfinite(info.nominal_srate()) or info.nominal_srate() < 0:
        raise LSLForceError("Breathing waveform has an invalid sampling rate")
    root = ElementTree.fromstring(info.as_xml())
    desc = root.find("desc")
    if desc is None:
        raise LSLForceError("Polar candidate has no LSL metadata")
    contract = desc.findtext("respyra_input_contract")
    if contract not in POLAR_CONTRACTS:
        raise LSLForceError("Requires a supported signed Polar breathing-level candidate")
    declared = tuple(filter(None, (desc.findtext("validity_streams") or "").split(",")))
    if not declared:
        # Earlier Mini versions declare the same references alongside metric IDs.
        ids = (desc.findtext(".//companion_metric_ids") or "").split(",")
        names = (desc.findtext("companion_streams") or "").split(",")
        if len(ids) == len(names):
            declared = tuple(name for metric, name in zip(ids, names) if metric.endswith("_valid") and name)
    schema = desc.findtext("schema")
    if (not info.source_id()
            or schema not in {"adr-waveform/1", "adr-waveform/2"}
            or desc.findtext("stream_role") != "respiration_candidate"
            or desc.findtext("raw_source_metric_id") != "raw_acc"
            or desc.findtext("respyra_signal_role") != "signed_breathing_level"):
        raise LSLForceError("Polar candidate does not match its Respyra input contract")
    if schema == "adr-waveform/2":
        bundled_polar_layout(desc, info.channel_count(), contract)
        return contract, ()
    if (info.channel_count() != 1 or desc.findtext("channels/channel/unit") != "g"
            or len(set(declared)) != POLAR_CONTRACTS[contract]):
        raise LSLForceError("Polar candidate does not match its Respyra input contract")
    return contract, tuple(sorted(declared))


class LSLPolarSource(LSLForceSource):
    """Use valid signed ACC projections in the existing study phase API."""

    def __init__(self, inlet, source_id, stream_name, contract_id, valid_inlets,
                 waveform_index=0, validity_indices=(), channels=()):
        super().__init__(inlet, waveform_index, source_id, stream_name, channels or
                         [{"index": 0, "label": "Breathing-level candidate", "unit": "g"}])
        self.contract_id = contract_id
        self.valid_inlets = valid_inlets
        self.validity_indices = validity_indices
        self.valid_history = {name: deque(maxlen=2048) for name in valid_inlets}
        self.polarity = 1
        self.ever_valid = False

    def start_derived(self, run_id, comparison=False):
        from pylsl import StreamInfo, StreamOutlet, cf_float32

        suffix = hashlib.sha256(self.source_id.encode("utf-8")).hexdigest()[:16]
        identity = (f"respyra-comparison-{run_id}-{suffix}" if comparison
                    else f"respyra-breathing-{run_id}")
        if self.calibrated_outlet is not None:
            if self.calibrated_id != identity:
                raise LSLForceError("A different derived breathing stream is already active")
            return
        self.calibrated_id = identity
        self.calibrated_run_id = run_id
        name = calibrated_stream_name(self.stream_name)
        info = StreamInfo(name, "Respiration", len(self.channels), 0, cf_float32, identity)
        desc = info.desc()
        for key, value in {
            "application": "Respyra 2.0", "raw_source_id": self.source_id,
            "stream_protocol": "respyra-stream/1",
            "raw_source_name": self.stream_name,
            "input_contract": self.contract_id,
            "raw_waveform_channel_index": str(self.force_index),
            "formula": "(polarity * waveform_g - center_g) / amplitude_g",
            "before_calibration": "NaN; parameters are in calibration.completed markers",
            "role": "comparison" if comparison else "feedback",
            "comparison_polarity": "native +1; selected feedback direction is independent" if comparison else "operator selected",
        }.items():
            desc.append_child_value(key, value)
        channel = desc.append_child("channels").append_child("channel")
        channel.append_child_value("label", "Calibrated breathing")
        channel.append_child_value("unit", "normalized")
        channel.append_child_value("role", "waveform")
        channel.append_child_value("validity_channels", ",".join(c["metric_id"] for c in self.channels
                                                                  if c.get("role") == "validity"))
        for definition in self.channels:
            if definition["index"] == self.force_index:
                continue
            channel = desc.child("channels").append_child("channel")
            for key in ("label", "unit", "metric_id", "role"):
                if definition.get(key):
                    channel.append_child_value(key, definition[key])
        self.calibrated_outlet = StreamOutlet(info)
        self.calibrated_uid = self.calibrated_outlet.get_info().uid()

    def get_all(self):
        for name, inlet in self.valid_inlets.items():
            try:
                rows, times = inlet.pull_chunk(timeout=0.0, max_samples=1024)
            except Exception as exc:
                raise LSLForceError(f"Polar validity stream {name} failed: {exc}") from exc
            for row, timestamp in zip(rows, times, strict=True):
                value = row[0] if len(row) == 1 else math.nan
                self.valid_history[name].append((timestamp, math.isfinite(value) and value >= 0.5))
        try:
            rows, times = self.inlet.pull_chunk(timeout=0.0, max_samples=1024)
        except Exception as exc:
            raise LSLForceError(f"Polar breathing stream failed: {exc}") from exc
        accepted = []
        for row, timestamp in zip(rows, times, strict=True):
            if (len(row) != len(self.channels) or not math.isfinite(row[self.force_index])
                    or not all(math.isfinite(row[i]) and row[i] >= 0.5 for i in self.validity_indices)
                    or not all(self._valid_at(history, timestamp)
                               for history in self.valid_history.values())):
                continue
            value = self.polarity * float(row[self.force_index])
            accepted.append((timestamp, value))
            self.latest_sample = (timestamp, [value])
            if self.calibrated_outlet is not None:
                normalized = ((value - self.center) / self.amplitude
                              if self.center is not None else math.nan)
                # All channels are NaN before range calibration, so a finite
                # native receipt still proves a finite calibrated waveform.
                diagnostics = ([row[c["index"]] for c in self.channels if c["index"] != self.force_index]
                               if self.center is not None else [math.nan] * (len(self.channels) - 1))
                self.calibrated_outlet.push_sample([normalized, *diagnostics], timestamp=timestamp)
                if self.center is not None:
                    self.calibrated_sample = timestamp
        if accepted:
            self.ever_valid = True
            self.last_force_at = time.monotonic()
        elif self.ever_valid and time.monotonic() - self.last_force_at > 3.0:
            raise LSLForceError("Polar breathing candidate has supplied no valid samples for 3 seconds")
        if self.comparisons is not None:
            self.comparisons.drain()
        return accepted

    @staticmethod
    def _valid_at(history, timestamp):
        # Flags and waveform share a producer timestamp. Use the flag applicable
        # to this sample, not the newest flag in a chunk that may describe a
        # later (possibly recovered) sample.
        for seen_at, valid in reversed(history):
            if seen_at <= timestamp + 0.005:
                return valid and timestamp - seen_at <= 1.0
        return False

    def stop(self):
        super().stop()
        for inlet in self.valid_inlets.values():
            inlet.close_stream()


def open_polar_source(resolved, timeout=20.0):
    from pylsl import StreamInlet, cf_float32, cf_double64, proc_clocksync, resolve_streams

    inlet = StreamInlet(resolved, max_buflen=2, processing_flags=proc_clocksync, recover=False)
    valid_inlets = {}
    try:
        info = inlet.info(timeout=min(timeout, 5.0))
        if info.source_id() != resolved.source_id():
            raise LSLForceError("Selected Polar stream identity changed during connection")
        contract, flags = validate_polar_info(info)
        desc = ElementTree.fromstring(info.as_xml()).find("desc")
        names = (desc.findtext("validity_streams") or "").split(",")
        identities = (desc.findtext("validity_source_ids") or "").split(",")
        references = dict(zip(names, identities)) if len(names) == len(identities) and all(identities) else {}
        def referenced(item, name):
            return (item.source_id() == references[name] if name in references
                    else item.name() == name)
        deadline = time.monotonic() + timeout
        found = []
        while flags and time.monotonic() < deadline:
            found = resolve_streams(wait_time=min(1.0, deadline - time.monotonic()))
            if all(sum(referenced(item, name) for item in found) == 1 for name in flags):
                break
        for name in flags:
            matches = [item for item in found if referenced(item, name)
                       and item.type() == "SignalQuality" and item.channel_count() == 1
                       and item.channel_format() in (cf_float32, cf_double64)]
            if len(matches) != 1:
                raise LSLForceError(f"Required Polar validity outlet is unavailable: {name}")
            companion = StreamInlet(matches[0], max_buflen=2,
                                     processing_flags=proc_clocksync, recover=False)
            full = companion.info(timeout=min(5.0, max(0.1, deadline - time.monotonic())))
            if (full.source_id() != matches[0].source_id() or full.type() != "SignalQuality"
                    or full.channel_count() != 1 or full.channel_format() not in (cf_float32, cf_double64)
                    or ElementTree.fromstring(full.as_xml()).findtext("./desc/channels/channel/unit") != "0/1"):
                companion.close_stream()
                raise LSLForceError(f"Polar validity outlet metadata changed: {name}")
            valid_inlets[name] = companion
        layout = (bundled_polar_layout(desc, info.channel_count(), contract)
                  if desc.findtext("schema") == "adr-waveform/2" else (0, (), ()))
        source = LSLPolarSource(inlet, info.source_id(), info.name(), contract, valid_inlets, *layout)
        source.uid = info.uid()
        while time.monotonic() < deadline:
            if source.get_all():
                return source
            time.sleep(0.025)
        raise LSLForceError("Polar breathing candidate did not become valid; check placement and ACC output")
    except Exception:
        inlet.close_stream()
        for companion in valid_inlets.values():
            companion.close_stream()
        raise
