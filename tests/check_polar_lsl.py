"""Run while Polar Mini's verify_adr_lsl example publishes separate outlets."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mpi.lsl_force import open_force_source, scan_force_streams  # noqa: E402


expected = {"respyra-polar-pca/1", "respyra-polar-phan-signed/1"}
deadline = time.monotonic() + 12
selected = []
while time.monotonic() < deadline:
    selected = [row for row in scan_force_streams(wait_time=0.3)
                if row.force_index is not None and row.reason.startswith("Compatible: respyra-polar-")]
    if len(selected) == 2:
        break
assert len(selected) == 2, [(row.info.name(), row.reason) for row in selected]
sources = []
try:
    for candidate in selected:
        source = open_force_source(candidate.info)
        sources.append(source)
        assert source.contract_id in expected
        fresh = []
        until = time.monotonic() + 2
        while not fresh and time.monotonic() < until:
            fresh = source.get_all()
            time.sleep(0.02)
        assert fresh
    assert {source.contract_id for source in sources} == expected
    print("Respyra Polar PCA and signed Phan contracts: live LSL readback passed")
finally:
    for source in sources:
        source.stop()
