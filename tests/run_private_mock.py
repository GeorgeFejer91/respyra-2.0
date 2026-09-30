"""Run a Mini mock and Respyra checks on a private desktop.

Example: python tests/run_private_mock.py remote-full --published-phone
The launcher never switches the user's input desktop. XDF/logs stay ignored.
"""

import argparse
import csv
import ctypes
import json
import os
import sys
import time
import uuid
from ctypes import wintypes
from pathlib import Path

import psutil

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.c_void_p), ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD),
    ]


user32.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p,
                                   wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
user32.CreateDesktopW.restype = wintypes.HANDLE
user32.CloseDesktop.argtypes = [wintypes.HANDLE]
kernel32.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p,
                                    ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD,
                                    ctypes.c_void_p, wintypes.LPCWSTR,
                                    ctypes.POINTER(STARTUPINFOW), ctypes.POINTER(PROCESS_INFORMATION)]
kernel32.CreateProcessW.restype = wintypes.BOOL

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("mode", choices=["full", "memory", "remote", "remote-full", "startup"])
parser.add_argument("--mini-exe", type=Path,
                    default=Path(os.environ["LOCALAPPDATA"]) / "Vernier Stream Mini/vernier-stream-mini.exe")
parser.add_argument("--respyra-exe", type=Path)
parser.add_argument("--published-phone", action="store_true")
parser.add_argument("--polar-metric", choices=["pca", "phan"])
parser.add_argument("--invert", action="store_true")
parser.add_argument("--repeat", type=int, default=1)
parser.add_argument("--tracking-seconds", type=float, default=.15)
parser.add_argument("--disconnect-after-ready", action="store_true")
args = parser.parse_args()
if not 1 <= args.repeat <= 5 or not .15 <= args.tracking_seconds <= 5:
    parser.error("repeat must be 1..5 and tracking-seconds must be 0.15..5")
if args.disconnect_after_ready and (args.mode != "remote-full" or args.repeat != 1):
    parser.error("disconnect-after-ready requires one remote-full run")
if args.mode == "startup" and not args.polar_metric:
    parser.error("startup requires --polar-metric")
project = Path(__file__).resolve().parents[1]
python = project / ".venv/Scripts/pythonw.exe"
if not args.mini_exe.is_file():
    parser.error(f"Mini executable missing: {args.mini_exe}")
if not python.is_file():
    parser.error(f"Project Python runtime missing: {python}")
if args.mode not in {"full", "startup"} and not args.respyra_exe:
    args.respyra_exe = project / "src-tauri/target/debug/respyra-desktop.exe"
if args.respyra_exe and not args.respyra_exe.is_file():
    parser.error(f"Respyra executable missing: {args.respyra_exe}")

name = "RespyraProbe" + uuid.uuid4().hex
root = project / ".for-ai-local" / name
root.mkdir(parents=True)
desktop = user32.CreateDesktopW(name, None, None, 0, 0x10000000, None)
if not desktop:
    raise ctypes.WinError(ctypes.get_last_error())
cfg = root / "lsl.cfg"
cfg.write_text("[lab]\nSessionID = " + name + "\n")
os.environ["LSLAPICFG"] = str(cfg)
exe = args.mini_exe.resolve()
if args.respyra_exe:
    os.environ["RESPYRA_DEBUG_EXE"] = str(args.respyra_exe.resolve())
if args.published_phone:
    os.environ["RESPYRA_PUBLISHED_PHONE"] = "1"
env = ctypes.create_unicode_buffer("\0".join(f"{key}={value}" for key, value in sorted(os.environ.items())) + "\0\0")
si = STARTUPINFOW()
si.cb = ctypes.sizeof(si)
si.lpDesktop = "WinSta0\\" + name
pi = PROCESS_INFORMATION()
pid = None
worker_pid = None
try:
    command = ctypes.create_unicode_buffer(f'"{exe}" --mock')
    ok = kernel32.CreateProcessW(str(exe), command, None, None, False, 0x400,
                                  env, str(exe.parent), ctypes.byref(si), ctypes.byref(pi))
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    pid = pi.dwProcessId
    print("private_desktop", name, "mock_pid", pid, flush=True)
    kernel32.CloseHandle(pi.hThread)
    kernel32.CloseHandle(pi.hProcess)
    from pylsl import StreamInlet, resolve_streams
    deadline = time.monotonic() + 30
    source_id = None
    suffix = {"pca": "_adrPcaWaveform", "phan": "_adrAxisMeanDifference"}.get(args.polar_metric)
    while time.monotonic() < deadline:
        streams = [stream for stream in resolve_streams(wait_time=1)
                   if (stream.name().endswith(suffix) if suffix else "Vernier" in stream.name())]
        if streams:
            for info in streams:
                print("stream", info.name(), info.type(), info.source_id(), info.channel_count(), flush=True)
                if info.type() == ("Respiration" if suffix else "VernierRaw"):
                    source_id = info.source_id()
                    inlet = StreamInlet(info, recover=False)
                    print("source_metadata", inlet.info(timeout=2).name(),
                          inlet.info(timeout=2).type(), flush=True)
                    for _ in range(5):
                        sample, timestamp = inlet.pull_sample(timeout=2)
                        print("sample", timestamp, sample, flush=True)
                    inlet.close_stream()
            break
        if not psutil.pid_exists(pid):
            print("mock exited", flush=True)
            break
    else:
        print("no matching Mini LSL stream within 30 seconds", flush=True)
    if not source_id:
        raise RuntimeError("Mini mock input stream did not appear")
    os.environ["RESPYRA_TEST_SOURCE_ID"] = source_id
    if args.mode == "startup":
        from pylsl import resolve_byprop
        base = source_id.removeprefix("polar-h10-").removesuffix(suffix)
        names = {"pca": base + "_adrPcaWaveform",
                 "phan": base + "_adrAxisMeanDifference",
                 "pca_valid": base + "_adrPcaValid",
                 "axis_valid": base + "_adrAxisDifferenceValid",
                 "quality": base + "_adrPcaQuality"}
        inlets = {key: StreamInlet(resolve_byprop("name", name, timeout=5)[0], recover=False)
                  for key, name in names.items()}
        reference = {}
        with (project / ".for-ai-local/polar-reference-30000.csv").open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if int(row["tick"]) == 1200:
                    reference[row["metric_id"]] = float(row["value"])
        samples = {key: [] for key in names}
        deadline = time.monotonic() + 16
        while time.monotonic() < deadline:
            for key, inlet in inlets.items():
                rows, times = inlet.pull_chunk(timeout=0, max_samples=1024)
                samples[key].extend((stamp, row[0]) for row, stamp in zip(rows, times, strict=True))
            if all(len(samples[key]) >= 10 for key in ("pca", "phan")) and {0, 1} <= {
                int(value) for _, value in samples["pca_valid"]}:
                break
            time.sleep(.02)
        for inlet in inlets.values():
            inlet.close_stream()
        assert all(len(samples[key]) >= 10 for key in ("pca", "phan"))
        assert {0, 1} <= {int(value) for _, value in samples["pca_valid"]}
        assert samples["axis_valid"] and all(value == 1 for _, value in samples["axis_valid"][-10:])
        assert samples["quality"] and all(0 <= value <= 1 for _, value in samples["quality"])
        first = {key: samples[key][0] for key in ("pca", "phan")}
        assert abs(first["pca"][0] - first["phan"][0]) < .002
        for key, metric in (("pca", "adr_pca_waveform"), ("phan", "adr_axis_mean_difference")):
            assert abs(first[key][1] - reference[metric]) < 2e-6
        created = float(resolve_byprop("name", names["pca"], timeout=1)[0].created_at())
        assert 11 <= first["pca"][0] - created <= 14
        print("startup_probe", json.dumps({"first_waveform_age_s": first["pca"][0] - created,
              "pca_first": first["pca"][1], "phan_first": first["phan"][1],
              "pca_valid_zeros": sum(value == 0 for _, value in samples["pca_valid"]),
              "pca_valid_ones": sum(value == 1 for _, value in samples["pca_valid"]),
              "axis_valid_samples": len(samples["axis_valid"]),
              "quality_samples": len(samples["quality"])}), flush=True)
        raise SystemExit(0)
    if args.polar_metric:
        os.environ["RESPYRA_TEST_POLAR_METRIC"] = args.polar_metric
        if args.invert:
            os.environ["RESPYRA_TEST_POLAR_INVERT"] = "1"
    if args.mode == "remote-full":
        os.environ["RESPYRA_FULL_MOCK_STUDY"] = "1"
        os.environ["RESPYRA_TEST_TRACKING_SECONDS"] = str(args.tracking_seconds)
        os.environ["PYTHONPATH"] = str(project / "tests/native_mock_site") + os.pathsep + os.environ.get("PYTHONPATH", "")
    os.environ["RESPYRA_PRIVATE_REPEAT"] = str(args.repeat)
    os.environ["RESPYRA_PRIVATE_TARGET"] = "remote_full" if args.mode == "remote-full" else args.mode
    os.environ["RESPYRA_TEST_LOG"] = str(root / (args.mode + ".log"))
    if args.disconnect_after_ready:
        os.environ["RESPYRA_PRIVATE_READY_PATH"] = str(root / "study-ready")
    env = ctypes.create_unicode_buffer("\0".join(f"{key}={value}" for key, value in sorted(os.environ.items())) + "\0\0")
    worker = Path(__file__).resolve().parent / "private_mock_worker.py"
    worker_started_at = time.time()
    command = ctypes.create_unicode_buffer(f'"{python}" "{worker}"')
    ok = kernel32.CreateProcessW(str(python), command, None, None, False, 0x400,
                                  env, str(project), ctypes.byref(si), ctypes.byref(pi))
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    worker_pid = pi.dwProcessId
    print("study_pid", worker_pid, "log", os.environ["RESPYRA_TEST_LOG"], flush=True)
    kernel32.CloseHandle(pi.hThread)
    kernel32.CloseHandle(pi.hProcess)
    try:
        if args.disconnect_after_ready:
            ready = Path(os.environ["RESPYRA_PRIVATE_READY_PATH"])
            deadline = time.monotonic() + 90
            while not ready.exists() and time.monotonic() < deadline and psutil.pid_exists(worker_pid):
                time.sleep(.1)
            if not ready.exists():
                raise RuntimeError("Study did not reach the first display flip before disconnect")
            psutil.Process(pid).terminate()
            print("mock_disconnected", pid, flush=True)
        code = psutil.Process(worker_pid).wait(timeout=180 * args.repeat +
                                                48 * max(0, args.tracking_seconds - .15) * args.repeat)
    except psutil.TimeoutExpired:
        raise RuntimeError("Full-study worker exceeded 180 seconds")
    print("study_exit", code, flush=True)
    if Path(os.environ["RESPYRA_TEST_LOG"]).exists():
        print("study_tail", "\n".join(Path(os.environ["RESPYRA_TEST_LOG"]).read_text(encoding="utf-8").splitlines()[-12:]), flush=True)
    if args.disconnect_after_ready:
        sys.path.insert(0, str(project))
        from scripts.audit_polar_mock_xdf import audit
        files = [file for file in (project / ".for-ai-local").glob("native-recordings-*/*.xdf")
                 if file.stat().st_mtime >= worker_started_at]
        if code != 0 or len(files) != 1:
            raise RuntimeError("Source-loss run did not produce a fresh failed-study XDF")
        print("disconnect_audit", json.dumps(audit(files[0], expect_disconnect=True)), flush=True)
    elif code != 0:
        raise RuntimeError("Full-study worker failed")
finally:
    if worker_pid and psutil.pid_exists(worker_pid):
        psutil.Process(worker_pid).kill()
    if pid and psutil.pid_exists(pid):
        process = psutil.Process(pid)
        children = process.children(recursive=True)
        for child in children:
            child.terminate()
        process.terminate()
        psutil.wait_procs(children + [process], timeout=5)
        for child in children:
            if child.is_running():
                child.kill()
        if process.is_running():
            process.kill()
    user32.CloseDesktop(desktop)
