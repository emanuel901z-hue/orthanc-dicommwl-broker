#!/usr/bin/env python3
r"""Drive a DVTk GUI application from Python (Win32 messages, no dependencies).

Some DVTk tools are only available as WinForms applications: the **RIS Emulator**
(Modality Worklist + MPPS SCP) and the **Modality Emulator** have no console mode
(`DVTCmd` covers storage only). Over SSH there is no one to click "Start".

This script starts the application, enumerates its windows and controls and can
click a button by its caption — enough to start an emulator and let it listen:

    python dvtk_gui.py --exe "D:\...\RIS Emulator.exe" --list
    python dvtk_gui.py --exe "D:\...\RIS Emulator.exe" --click "Start" --seconds 600

`--list` prints every control (class + caption) so the caller can see what the
window offers; `--click` sends `BM_CLICK` to the first control whose caption
matches (case-insensitive substring).

Runs **on the Windows machine**.

**Measured limit (23.09.2026):** over SSH this does *not* reach the RIS
Emulator's window. The process starts (18 threads) but has no enumerable window,
no listening port and writes no settings — Windows puts it on a window station
without a visible desktop, so `EnumWindows` finds nothing (`controls=0`) and
there is no one to press "Start". An interactive session at the machine (console
or RDP) is required for the GUI emulators; this script is the tool for that case.
"""
import argparse
import ctypes
import re
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.windll.user32
BM_CLICK = 0x00F5
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E


def window_text(hwnd: int) -> str:
    length = user32.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.SendMessageW(hwnd, WM_GETTEXT, length + 1, buffer)
    return buffer.value


def class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def children(hwnd: int) -> list[int]:
    found: list[int] = []
    EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(child, _param):
        found.append(child)
        return True

    user32.EnumChildWindows(hwnd, EnumProc(callback), 0)
    return found


def top_level_windows(pid: int) -> list[int]:
    found: list[int] = []
    EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _param):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(EnumProc(callback), 0)
    return found


def describe(pid: int) -> list[tuple[int, str, str]]:
    """(hwnd, class, caption) for every visible control of the process."""
    rows: list[tuple[int, str, str]] = []
    for top in top_level_windows(pid):
        rows.append((top, class_name(top), window_text(top)))
        for child in children(top):
            rows.append((child, class_name(child), window_text(child)))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--list", action="store_true", help="print controls and exit")
    parser.add_argument("--click", default="", help="caption (substring) to click")
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--wait", type=int, default=12, help="seconds to let the app start")
    args = parser.parse_args()

    if not args.exe.is_file():
        print(f"not found: {args.exe}", file=sys.stderr)
        return 2

    process = subprocess.Popen([str(args.exe)])
    time.sleep(args.wait)
    rows = describe(process.pid)
    print(f"pid={process.pid} controls={len(rows)}", flush=True)

    if args.list or not args.click:
        for hwnd, cls, caption in rows:
            if caption.strip():
                print(f"  {cls:42s} {caption!r}")
        if args.list:
            process.terminate()
            return 0

    pattern = re.compile(re.escape(args.click), re.IGNORECASE)
    target = next(((h, c, t) for h, c, t in rows if pattern.search(t)), None)
    if target is None:
        print(f"no control matching {args.click!r}", file=sys.stderr)
        for hwnd, cls, caption in rows:
            if caption.strip():
                print(f"  {cls:42s} {caption!r}")
        process.terminate()
        return 3

    hwnd, cls, caption = target
    print(f"clicking {caption!r} ({cls})", flush=True)
    user32.SendMessageW(hwnd, BM_CLICK, 0, 0)

    deadline = time.time() + args.seconds
    try:
        while time.time() < deadline and process.poll() is None:
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
    print("STOPPED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
