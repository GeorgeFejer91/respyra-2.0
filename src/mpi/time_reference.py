"""Optional HTTPS wall-clock reference; LSL remains the sample timing authority."""

from __future__ import annotations

import json
import math
import re
import threading
import time
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

API_URL = "https://timeapi.io/api/time/current/zone?timeZone=UTC"
BERLIN = ZoneInfo("Europe/Berlin")
TIME_COLUMNS = ["lsl_time_s", "utc_time", "berlin_time", "time_reference"]


def iso_time(unix_seconds, zone=timezone.utc):
    return datetime.fromtimestamp(unix_seconds, zone).isoformat(timespec="microseconds")


class TimeReference:
    """Probe during setup, freeze without waiting, ignore any late API response.

    One immutable LSL-to-UTC mapping keeps OS clock adjustments, API outages and
    Berlin DST transitions from changing experimental intervals mid-run.
    """

    def __init__(self, clock=None):
        if clock is None:
            from pylsl import local_clock
            clock = local_clock
        self.clock = clock
        before = clock()
        system_time = time.time()
        after = clock()
        self._reference = {
            "schema": "respyra-clock-reference-v1", "source": "system",
            "timezone": "Europe/Berlin", "lsl_anchor_s": (before + after) / 2,
            "unix_anchor_s": system_time, "utc_anchor": iso_time(system_time),
            "round_trip_s": None, "transport_uncertainty_s": None,
            "system_offset_s": 0.0, "api_status": "not_requested",
            "accuracy": "Estimated wall time; server accuracy, LSL alignment error and subsequent clock drift are not measured. Offline system-clock accuracy is unknown.",
        }
        self._lock = threading.Lock()
        self._system_reference = self._reference.copy()
        self._frozen = False
        self._worker = None

    def start(self):
        """No join or network wait on Start, display flips or sample logging."""
        with self._lock:
            if self._worker is not None or self._frozen:
                return
            self._reference["api_status"] = "pending"
            self._worker = threading.Thread(target=self._probe, daemon=True,
                                            name="respyra-time-reference")
            self._worker.start()

    def _probe(self):
        # Three small, uncached probes; use the smallest RTT, as with LSL's
        # clock filter. HTTPS server-generation time is only a midpoint estimate.
        for _ in range(3):
            with self._lock:
                if self._frozen:
                    return
            try:
                before = self.clock()
                request = Request(API_URL, headers={"Accept": "application/json",
                    "Cache-Control": "no-cache", "User-Agent": "Respyra-time-reference/1"})
                with urlopen(request, timeout=1.5) as response:
                    cache_age = float(response.headers.get("Age", "0"))
                    if response.status != 200 or not math.isfinite(cache_age) or cache_age != 0:
                        raise ValueError("Unusable or cached time response")
                    body = response.read(8193)
                    if len(body) > 8192:
                        raise ValueError("Oversized time response")
                after = self.clock()
                result = json.loads(body)
                if result.get("timeZone") != "UTC":
                    raise ValueError("Time API did not return UTC")
                # .NET emits seven fractional digits; CPython 3.10 accepts six.
                date_time = re.sub(r"(\.\d{6})\d+", r"\1", result["dateTime"])
                server = datetime.fromisoformat(date_time)
                if server.tzinfo is None:
                    server = server.replace(tzinfo=timezone.utc)
                if server.utcoffset().total_seconds() != 0:
                    raise ValueError("Time API returned a non-UTC offset")
                server_time = server.timestamp()
                rtt = after - before
                if not math.isfinite(rtt) or not 0 <= rtt <= 1.5:
                    raise ValueError("Time API response was too slow")
                midpoint = (before + after) / 2
                system_estimate = (self._system_reference["unix_anchor_s"] + midpoint
                                   - self._system_reference["lsl_anchor_s"])
                candidate = {**self._reference, "source": "timeapi.io",
                    "lsl_anchor_s": midpoint, "unix_anchor_s": server_time,
                    "utc_anchor": iso_time(server_time), "round_trip_s": rtt,
                    "transport_uncertainty_s": rtt / 2 + 0.000001,
                    "system_offset_s": server_time - system_estimate,
                    "api_status": "available"}
                with self._lock:
                    if not self._frozen and (self._reference["round_trip_s"] is None
                            or rtt < self._reference["round_trip_s"]):
                        self._reference = candidate
            except Exception:
                # Optional reference failure must never abort data collection.
                with self._lock:
                    if not self._frozen and self._reference["source"] == "system":
                        self._reference["api_status"] = "unavailable"
                return

    def freeze(self):
        with self._lock:
            self._frozen = True
            return self._reference.copy()

    def fields(self, lsl_time):
        return timestamp_fields(self.freeze(), lsl_time)


def timestamp_fields(reference, lsl_time):
    unix_time = reference["unix_anchor_s"] + (float(lsl_time) - reference["lsl_anchor_s"])
    return {"lsl_time_s": format(float(lsl_time), ".17g"),
            "utc_time": iso_time(unix_time), "berlin_time": iso_time(unix_time, BERLIN),
            "time_reference": reference["source"]}


def recorded_reference(markers):
    """Use the marker's synchronized XDF time, not its producer clock domain."""
    matches = []
    for stamp, row in zip(markers["time_stamps"], markers["time_series"]):
        event = json.loads(row[0])
        if event.get("event") == "recording.started" and event.get("clock_reference"):
            reference = event["clock_reference"].copy()
            if reference.get("schema") != "respyra-clock-reference-v1":
                raise ValueError("Unsupported recorded clock reference")
            for key in ("lsl_anchor_s", "unix_anchor_s"):
                if not math.isfinite(float(reference[key])):
                    raise ValueError("Invalid recorded clock reference")
                reference[key] = float(reference[key])
            if reference.get("source") not in {"system", "timeapi.io"}:
                raise ValueError("Invalid recorded clock source")
            if not math.isfinite(float(event["lsl_time"])) or not math.isfinite(float(stamp)):
                raise ValueError("Invalid clock-reference marker timestamp")
            # PyXDF synchronizes marker timestamps to its recording clock domain.
            reference["lsl_anchor_s"] += float(stamp) - float(event["lsl_time"])
            matches.append(reference)
    if len(matches) > 1:
        raise ValueError("Ambiguous recorded clock reference")
    return matches[0] if matches else None


class TimedCSVLogger:
    """Add sample timestamps to the upstream frame/phase CSV without changing it.

    The upstream phase runners discard _ts when they call log_row. Capture the
    current batch once and consume its timestamps in the same row order. Idle
    drains replace that batch; they cannot leak old timestamps into a new phase.
    """

    def __init__(self, logger, reference, *, sample_rows=False):
        self.logger = logger
        self.reference = reference
        self.sample_rows = sample_rows
        self.samples = deque()
        Path(logger.filepath + ".json").write_text(json.dumps({
            "ClockReference": reference.freeze(),
            "Columns": {"timestamp": "Legacy phase-relative display-frame time; unchanged",
                "lsl_time_s": "Clock-synchronized LSL sample time, or log-write time for assessment rows",
                "utc_time": "Estimated UTC time in ISO 8601",
                "berlin_time": "Estimated Europe/Berlin time in ISO 8601 with DST-correct UTC offset",
                "time_reference": "timeapi.io or offline system reference"},
            "TimestampBasis": "accepted_sample" if sample_rows else "assessment_log_write",
        }, indent=2) + "\n", encoding="utf-8")

    @contextmanager
    def observe_samples(self, source):
        original = source.get_all
        def get_all():
            rows = original()
            self.samples.clear()
            self.samples.extend(stamp for stamp, _value in rows)
            return rows
        source.get_all = get_all
        try:
            yield
        finally:
            source.get_all = original

    def log_row(self, **fields):
        if self.sample_rows:
            if not self.samples:
                raise ValueError("Sample CSV row has no corresponding LSL timestamp")
            stamp = self.samples.popleft()
        else:
            stamp = self.reference.clock()
        self.logger.log_row(**fields, **self.reference.fields(stamp))

    def close(self):
        self.logger.close()
