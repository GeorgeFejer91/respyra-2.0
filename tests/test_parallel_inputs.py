"""Every live alternative gets its own calibration; feedback stays selected."""

from types import SimpleNamespace

import pytest

from mpi.parallel_inputs import ParallelInputs


class Source:
    def __init__(self, source_id, values, polar=False):
        self.source_id = source_id
        self.calibrated_id = f"comparison-{source_id}"
        self.uid = f"raw-{source_id}"
        self.calibrated_uid = f"derived-{source_id}"
        self.values = iter(values)
        self.calibration = None
        self.closed = False
        self.stopped = False
        if polar:
            self.contract_id = "respyra-polar-pca/1"
            self.polarity = 1

    def get_all(self):
        return [(0.0, next(self.values))]

    def calibrate(self, center, amplitude, run_id):
        self.calibration = center, amplitude, run_id

    def stop(self):
        self.closed = True
        self.stopped = True


def test_comparison_inputs_use_independent_ranges_and_keep_source_identities():
    force = Source("vernier", range(1, 11))
    polar = Source("polar", (value / 100 for value in range(1, 11)), polar=True)
    events = []
    manager = ParallelInputs([force, polar], SimpleNamespace(
        emit=lambda name, **fields: events.append((name, fields))), "run-1")
    assert manager.required == ("vernier", "comparison-vernier", "polar", "comparison-polar")
    assert manager.required_uids == {"raw-vernier", "derived-vernier", "raw-polar", "derived-polar"}
    manager.begin_range()
    for _ in range(10):
        manager.drain()
    manager.end_range()
    manager.activate(SimpleNamespace(percentile_lo=0, percentile_hi=100, scale=1.0))
    assert force.calibration == (5.5, 4.5, "run-1")
    assert polar.calibration[:2] == pytest.approx((0.055, 0.045))
    assert polar.calibration[2] == "run-1"
    assert [name for name, _ in events] == ["source.comparison.calibrated"] * 2
    manager.close()
    assert force.closed and polar.closed
