"""Record calibrated comparison waveforms without changing the feedback source."""

from __future__ import annotations

from mpi.lsl_force import LSLForceError, open_force_source, scan_force_streams


class ParallelInputs:
    def __init__(self, sources, markers, run_id):
        self.sources = sources
        self.active = set(sources)
        self.markers = markers
        self.run_id = run_id
        self.capturing = False
        self.range_samples = {source: [] for source in sources}

    @classmethod
    def discover(cls, selected, markers, excluded_uids=()):
        """Open only live compatible alternatives allowed by the Record checkboxes."""
        from mpi.lsl_polar import open_polar_source

        sources = []
        seen = {selected.source_id}
        for candidate in scan_force_streams(wait_time=0.2):
            info = candidate.info
            if (candidate.force_index is None or info.source_id() in seen
                    or info.uid() in excluded_uids):
                continue
            seen.add(info.source_id())
            source = None
            try:
                source = (open_polar_source(info, timeout=3.0) if info.type() == "Respiration"
                          else open_force_source(info, timeout=3.0))
                source.start_derived(markers.run_id, comparison=True)
            except (LSLForceError, OSError) as exc:
                if source is not None:
                    source.stop()
                markers.emit("source.comparison.skipped", source_id=info.source_id(), reason=str(exc))
                continue
            sources.append(source)
        return cls(sources, markers, markers.run_id)

    @property
    def required(self):
        return tuple(identity for source in self.sources
                     for identity in (source.source_id, source.calibrated_id))

    @property
    def required_uids(self):
        return {uid for source in self.sources for uid in (source.uid, source.calibrated_uid)}

    def drain(self):
        for source in tuple(self.active):
            try:
                rows = source.get_all()
            except LSLForceError as exc:
                self.active.remove(source)
                source.stop()
                self.markers.emit("source.comparison.lost", source_id=source.source_id(), reason=str(exc))
                continue
            if self.capturing:
                self.range_samples[source].extend(value for _, value in rows)

    def begin_range(self):
        self.range_samples = {source: [] for source in self.sources}
        self.capturing = True

    def end_range(self):
        self.capturing = False

    def activate(self, range_cal):
        """Apply each candidate's own range; Polar alternatives retain native sign."""
        self.capturing = False
        for source in self.sources:
            values = sorted(self.range_samples[source])
            if source not in self.active or len(values) < 6:
                self.markers.emit("source.comparison.skipped", source_id=source.source_id(),
                                  reason="Too few valid samples during range calibration")
                continue
            n = len(values)
            lo = values[max(0, min(int(n * range_cal.percentile_lo / 100), n - 1))]
            hi = values[max(0, min(int(n * range_cal.percentile_hi / 100) - 1, n - 1))]
            half_range = (hi - lo) / 2
            if half_range <= (1e-5 if hasattr(source, "contract_id") else 0):
                self.markers.emit("source.comparison.skipped", source_id=source.source_id(),
                                  reason="Insufficient calibration range")
                continue
            center = (hi + lo) / 2
            amplitude = (half_range * range_cal.scale if hasattr(source, "contract_id")
                         else max(half_range * range_cal.scale, 0.5))
            source.calibrate(center, amplitude, self.run_id)
            self.markers.emit("source.comparison.calibrated", source_id=source.source_id,
                              center=center, amplitude=amplitude,
                              unit="g" if hasattr(source, "contract_id") else "N",
                              polarity=source.polarity if hasattr(source, "contract_id") else None,
                              sample_count=n)

    def close(self):
        for source in self.sources:
            if not source.stopped:
                source.stop()
        self.active.clear()
