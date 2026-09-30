"""Private-desktop child for run_private_mock.py."""

import os
import runpy
import sys
import traceback
from pathlib import Path

log = Path(os.environ["RESPYRA_TEST_LOG"])
mode = os.environ.get("RESPYRA_PRIVATE_TARGET", "full")
target = Path(__file__).resolve().parent / (
    "check_native_lsl.py" if mode in {"remote", "remote_full", "memory"} else "check_control_center.py")
test_mode = "remote" if mode == "remote_full" else mode if mode in {"remote", "memory"} else "--full-study"
sys.argv = [str(target)] + [test_mode] * int(os.environ.get("RESPYRA_PRIVATE_REPEAT", "1"))
with log.open("w", encoding="utf-8", buffering=1) as output:
    sys.stdout = output
    sys.stderr = output
    try:
        runpy.run_path(str(target), run_name="__main__")
    except BaseException:
        traceback.print_exc()
        sys.exit(1)
