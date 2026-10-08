"""Send window-targeted key messages only on a noninteractive test desktop."""
import ctypes as C
import json
import os
import time
from ctypes import wintypes as W
from pathlib import Path
import psutil

user = C.WinDLL('user32', use_last_error=True)
user.GetThreadDesktop.argtypes = [W.DWORD]
user.GetThreadDesktop.restype = W.HANDLE
user.OpenInputDesktop.argtypes = [W.DWORD, W.BOOL, W.DWORD]
user.OpenInputDesktop.restype = W.HANDLE
user.GetUserObjectInformationW.argtypes = [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)]
user.CloseDesktop.argtypes = [W.HANDLE]
user.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
user.GetWindowThreadProcessId.restype = W.DWORD
user.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
user.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
user.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
user.GetGUIThreadInfo.argtypes = [W.DWORD, C.c_void_p]

class GUI(C.Structure):
    _fields_ = [('size', W.DWORD), ('flags', W.DWORD), ('active', W.HWND),
        ('focus', W.HWND), ('capture', W.HWND), ('menu', W.HWND),
        ('move', W.HWND), ('caret', W.HWND), ('rect', W.RECT)]

def name(handle):
    buf = C.create_unicode_buffer(256)
    length = W.DWORD()
    if not user.GetUserObjectInformationW(handle, 2, buf, C.sizeof(buf), C.byref(length)):
        raise C.WinError(C.get_last_error())
    return buf.value

def require_private_desktop():
    desktop = user.GetThreadDesktop(C.windll.kernel32.GetCurrentThreadId())
    other = user.OpenInputDesktop(0, False, 1)
    if not other:
        raise C.WinError(C.get_last_error())
    try:
        assert name(desktop) != name(other), 'Refusing keyboard check on the active desktop'
    finally:
        user.CloseDesktop(other)
    return desktop

def post_key(parent_pid, key='space'):
    """Exercise Win32/Pyglet dispatch; never synthesize global desktop input."""
    desktop = require_private_desktop()
    children = {p.pid: p for p in psutil.Process(parent_pid).children(recursive=True)}
    children[parent_pid] = psutil.Process(parent_pid)
    windows = []
    callback_type = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def visit(hwnd, _):
        pid = W.DWORD()
        tid = user.GetWindowThreadProcessId(hwnd, C.byref(pid))
        if pid.value in children:
            title = C.create_unicode_buffer(256)
            cls = C.create_unicode_buffer(256)
            user.GetWindowTextW(hwnd, title, 256)
            user.GetClassNameW(hwnd, cls, 256)
            if title.value == 'PsychoPy' and children[pid.value].name().lower() in {'python.exe','pythonw.exe'}:
                info = GUI(); info.size = C.sizeof(info)
                ok = user.GetGUIThreadInfo(tid, C.byref(info))
                windows.append({'hwnd': hwnd, 'pid': pid.value, 'class': cls.value,
                    'title': title.value, 'gui': bool(ok), 'focus': info.focus, 'active': info.active})
        return True
    user.EnumDesktopWindows.argtypes = [W.HANDLE, callback_type, W.LPARAM]
    if not user.EnumDesktopWindows(desktop, callback_type(visit), 0):
        raise C.WinError(C.get_last_error())
    print('native_key_target', json.dumps(windows), flush=True)
    assert len(windows) == 1, windows
    hwnd = windows[0]['hwnd']
    vk, scan = {'space': (0x20, 0x39), 'escape': (0x1b, 0x01),
                '1': (0x31, 0x02), 'n': (0x4e, 0x31)}[key]
    assert user.PostMessageW(hwnd, 0x100, vk, 1 | (scan << 16))
    assert user.PostMessageW(hwnd, 0x101, vk, 1 | (scan << 16) | (3 << 30))

def main():
    """Run with the packaged runtime on an isolated Windows desktop."""
    require_private_desktop()  # Fail closed before importing/creating any display.
    from uuid import uuid4
    config = Path(os.environ['RESPYRA_KEYBOARD_EVIDENCE']).with_suffix('.cfg')
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('[lab]\nSessionID = keyboard-' + uuid4().hex + '\n')
    os.environ['LSLAPICFG'] = str(config)
    from psychopy import visual
    from mpi.event_markers import MarkerOutlet
    trace = []
    markers = MarkerOutlet()
    markers.observer = trace.append
    win = visual.Window(fullscr=True, color='black')
    try:
        for _ in range(3):
            for key in ['space', 'escape']:
                deadline = time.monotonic() + 3
                def cancel():
                    if time.monotonic() > deadline:
                        raise TimeoutError('Prompt discarded the native ' + key + ' key')
                with markers.observe_inputs_and_screens(cancel_check=cancel) as show:
                    win.callOnFlip(post_key, os.getpid(), key)
                    assert show(win, 'Press SPACE to begin.', key_list=['space', 'escape']) == key
                    assert trace[-1]['event'] == 'ui.instructions.dismissed'
                    assert trace[-1]['key'] == key
                print('native_flip_key_passed', key, flush=True)
    finally:
        win.close()
        Path(os.environ['RESPYRA_KEYBOARD_EVIDENCE']).write_text(json.dumps(trace, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()


