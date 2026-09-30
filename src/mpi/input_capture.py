"""Optional Windows input markers, scoped to the experiment's own windows."""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import os
import queue
import threading


class InputCapture:
    def __init__(self, keyboard=False, mouse=False):
        if os.name != "nt":
            raise RuntimeError("Optional input recording requires Windows")
        self.keyboard, self.mouse = keyboard, mouse
        # Virtualenv launchers may sit between the native shell and Python.
        self.processes = {os.getpid(), int(os.environ.get("RESPIRA_CONTROLLER_PID", os.getppid()))}
        self.events = queue.Queue(maxsize=10000)
        self.error = None
        self.ready = threading.Event()
        self.thread_id = None
        self.thread = threading.Thread(target=self._run, daemon=True, name="respyra-input-markers")
        self.thread.start()
        if not self.ready.wait(3) or self.error:
            self.close()
            raise RuntimeError(self.error or "Input recording did not initialize")

    def poll(self, markers):
        if self.error:
            raise RuntimeError(self.error)
        while True:
            try:
                event, fields = self.events.get_nowait()
            except queue.Empty:
                return
            markers.emit(event, **fields)

    def close(self):
        if self.thread_id is not None:
            C.windll.user32.PostThreadMessageW(self.thread_id, 0x12, 0, 0)  # WM_QUIT
        self.thread.join(timeout=3)
        if self.thread.is_alive():
            raise RuntimeError("Input recording could not stop")

    def _run(self):
        from pylsl import local_clock
        user = C.WinDLL("user32", use_last_error=True)
        kernel = C.WinDLL("kernel32", use_last_error=True)
        callback_type = C.WINFUNCTYPE(C.c_ssize_t, C.c_int, W.WPARAM, W.LPARAM)
        user.SetWindowsHookExW.argtypes = [C.c_int, callback_type, W.HINSTANCE, W.DWORD]
        user.SetWindowsHookExW.restype = W.HANDLE
        user.CallNextHookEx.argtypes = [W.HANDLE, C.c_int, W.WPARAM, W.LPARAM]
        user.CallNextHookEx.restype = C.c_ssize_t
        user.UnhookWindowsHookEx.argtypes = [W.HANDLE]
        user.GetForegroundWindow.restype = W.HWND
        user.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
        kernel.GetModuleHandleW.argtypes = [W.LPCWSTR]
        kernel.GetModuleHandleW.restype = W.HMODULE

        class Keyboard(C.Structure):
            _fields_ = [("vk", W.DWORD), ("scan", W.DWORD), ("flags", W.DWORD),
                        ("time", W.DWORD), ("extra", C.c_size_t)]

        class Mouse(C.Structure):
            _fields_ = [("point", W.POINT), ("data", W.DWORD), ("flags", W.DWORD),
                        ("time", W.DWORD), ("extra", C.c_size_t)]

        names = {0x100: "down", 0x101: "up", 0x104: "system_down", 0x105: "system_up",
                 0x200: "move", 0x201: "left_down", 0x202: "left_up", 0x204: "right_down",
                 0x205: "right_up", 0x207: "middle_down", 0x208: "middle_up",
                 0x20A: "wheel", 0x20B: "extra_down", 0x20C: "extra_up", 0x20E: "horizontal_wheel"}

        def capture(code, message, pointer, keyboard):
            try:
                process = W.DWORD()
                user.GetWindowThreadProcessId(user.GetForegroundWindow(), C.byref(process))
                if code >= 0 and process.value in self.processes:
                    fields = {"input_action": names.get(message, str(message)), "event_lsl_time": local_clock(),
                              "scope": "respyra_windows"}
                    if keyboard:
                        data = C.cast(pointer, C.POINTER(Keyboard)).contents
                        fields.update(vk_code=data.vk, scan_code=data.scan, flags=data.flags)
                    else:
                        data = C.cast(pointer, C.POINTER(Mouse)).contents
                        fields.update(x=data.point.x, y=data.point.y, mouse_data=data.data, flags=data.flags)
                    self.events.put_nowait(("input.keyboard_event" if keyboard else "input.mouse_event", fields))
            except Exception as exc:
                self.error = f"Input recording failed: {type(exc).__name__}"
            return user.CallNextHookEx(None, code, message, pointer)

        callbacks, hooks = [], []
        try:
            self.thread_id = kernel.GetCurrentThreadId()
            msg = W.MSG()
            user.PeekMessageW(C.byref(msg), None, 0, 0, 0)  # Create this thread's message queue.
            for hook_type, enabled, keyboard in [(13, self.keyboard, True), (14, self.mouse, False)]:
                if not enabled:
                    continue
                callback = callback_type(lambda code, message, pointer, keyboard=keyboard:
                                         capture(code, message, pointer, keyboard))
                callbacks.append(callback)
                hook = user.SetWindowsHookExW(hook_type, callback, kernel.GetModuleHandleW(None), 0)
                if not hook:
                    raise C.WinError(C.get_last_error())
                hooks.append(hook)
            self.ready.set()
            while user.GetMessageW(C.byref(msg), None, 0, 0) > 0:
                user.TranslateMessage(C.byref(msg))
                user.DispatchMessageW(C.byref(msg))
        except Exception as exc:
            self.error = f"Input recording failed: {exc}"
        finally:
            for hook in hooks:
                user.UnhookWindowsHookEx(hook)
            self.ready.set()
