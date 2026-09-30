"""Run the installed Vernier Mini mock and Respyra checks on a private desktop.

Example: python tests/run_private_mock.py remote-full --published-phone
The launcher never switches the user's input desktop. XDF/logs stay ignored.
"""

import argparse
import ctypes
import os
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
parser.add_argument("mode", choices=["full", "memory", "remote", "remote-full"])
parser.add_argument("--mini-exe", type=Path,
                    default=Path(os.environ["LOCALAPPDATA"]) / "Vernier Stream Mini/vernier-stream-mini.exe")
parser.add_argument("--respyra-exe", type=Path)
parser.add_argument("--published-phone", action="store_true")
args = parser.parse_args()
project = Path(__file__).resolve().parents[1]
python = project / ".venv/Scripts/pythonw.exe"
if not args.mini_exe.is_file():
    parser.error(f"Vernier Stream Mini executable missing: {args.mini_exe}")
if not python.is_file():
    parser.error(f"Project Python runtime missing: {python}")
if args.mode != "full" and not args.respyra_exe:
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
    while time.monotonic() < deadline:
        streams = [stream for stream in resolve_streams(wait_time=1) if "Vernier" in stream.name()]
        if streams:
            for info in streams:
                print("stream", info.name(), info.type(), info.source_id(), info.channel_count(), flush=True)
                if info.type() == "VernierRaw":
                    source_id = info.source_id()
                    inlet = StreamInlet(info, recover=False)
                    print("model", "GDX-RB-MOCK" in inlet.info(timeout=2).as_xml(), flush=True)
                    for _ in range(5):
                        sample, timestamp = inlet.pull_sample(timeout=2)
                        print("sample", timestamp, sample, flush=True)
                    inlet.close_stream()
            break
        if not psutil.pid_exists(pid):
            print("mock exited", flush=True)
            break
    else:
        print("no Vernier LSL stream within 30 seconds", flush=True)
    if not source_id:
        raise RuntimeError("Vernier raw mock stream did not appear")
    os.environ["RESPYRA_TEST_SOURCE_ID"] = source_id
    if args.mode == "remote-full":
        os.environ["RESPYRA_FULL_MOCK_STUDY"] = "1"
        os.environ["PYTHONPATH"] = str(project / "tests/native_mock_site") + os.pathsep + os.environ.get("PYTHONPATH", "")
    os.environ["RESPYRA_PRIVATE_TARGET"] = "remote_full" if args.mode == "remote-full" else args.mode
    os.environ["RESPYRA_TEST_LOG"] = str(root / (args.mode + ".log"))
    env = ctypes.create_unicode_buffer("\0".join(f"{key}={value}" for key, value in sorted(os.environ.items())) + "\0\0")
    worker = Path(__file__).resolve().parent / "private_mock_worker.py"
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
        code = psutil.Process(worker_pid).wait(timeout=180)
    except psutil.TimeoutExpired:
        raise RuntimeError("Full-study worker exceeded 180 seconds")
    print("study_exit", code, flush=True)
    if Path(os.environ["RESPYRA_TEST_LOG"]).exists():
        print("study_tail", "\n".join(Path(os.environ["RESPYRA_TEST_LOG"]).read_text(encoding="utf-8").splitlines()[-12:]), flush=True)
    if code != 0:
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
