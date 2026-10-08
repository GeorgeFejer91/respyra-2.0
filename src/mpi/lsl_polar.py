"""Identify signed breathing waveforms by format and metadata, never names."""

from __future__ import annotations

import math
import hashlib
import time
from collections import deque
from xml.etree import ElementTree

from mpi.lsl_force import LSLForceError, LSLForceSource


POLAR_CONTRACTS = {"respyra-polar-pca/1": 1, "respyra-polar-phan-signed/1": 2}


def validate_polar_info(info) -> tuple[str, tuple[str, ...]]:
    """Return a compatible waveform contract and its declared validity references."""
    from pylsl import cf_float32, cf_double64

    if info.channel_count() != 1 or info.channel_format() not in (cf_float32, cf_double64):
        raise LSLForceError("Requires a one-channel floating-point breathing waveform")
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
    if (not info.source_id()
            or desc.findtext("schema") != "adr-waveform/1"
            or desc.findtext("stream_role") != "respiration_candidate"
            or desc.findtext("raw_source_metric_id") != "raw_acc"
            or desc.findtext("respyra_signal_role") != "signed_breathing_level"
            or desc.findtext("channels/channel/unit") != "g"
            or len(set(declared)) != POLAR_CONTRACTS[contract]):
        raise LSLForceError("Polar candidate does not match its Respyra input contract")
    return contract, tuple(sorted(declared))


class LSLPolarSource(LSLForceSource):
    """Use valid signed ACC projections in the existing study phase API."""

    def __init__(self, inlet, source_id, stream_name, contract_id, valid_inlets):
        super().__init__(inlet, 0, source_id, stream_name,
                         [{"index": 0, "label": "Breathing-level candidate", "unit": "g"}])
        self.contract_id = contract_id
        self.valid_inlets = valid_inlets
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
        name = f"Respyra-Comparison-{suffix}" if comparison else "Respyra-Calibrated-Breathing"
        info = StreamInfo(name, "Respiration", 1, 0, cf_float32, identity)
        desc = info.desc()
        for key, value in {
            "application": "Respyra 2.0", "raw_source_id": self.source_id,
            "input_contract": self.contract_id,
            "formula": "(polarity * waveform_g - center_g) / amplitude_g",
            "before_calibration": "NaN; parameters are in calibration.completed markers",
            "role": "comparison" if comparison else "feedback",
            "comparison_polarity": "native +1; selected feedback direction is independent" if comparison else "operator selected",
        }.items():
            desc.append_child_value(key, value)
        channel = desc.append_child("channels").append_child("channel")
        channel.append_child_value("label", "Calibrated breathing")
        channel.append_child_value("unit", "normalized")
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
            if (len(row) != 1 or not math.isfinite(row[0])
                    or not all(self._valid_at(history, timestamp)
                               for history in self.valid_history.values())):
                continue
            value = self.polarity * float(row[0])
            accepted.append((timestamp, value))
            self.latest_sample = (timestamp, [value])
            if self.calibrated_outlet is not None:
                normalized = ((value - self.center) / self.amplitude
                              if self.center is not None else math.nan)
                self.calibrated_outlet.push_sample([normalized], timestamp=timestamp)
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
        while time.monotonic() < deadline:
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
        source = LSLPolarSource(inlet, info.source_id(), info.name(), contract, valid_inlets)
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
