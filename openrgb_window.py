"""Shared helpers for locating and positioning the OpenRGB main window.

We keep OpenRGB's window permanently in a "shown" (never minimized, never
hidden) state, but parked off-screen with no taskbar/Alt-Tab presence. This
keeps Qt's accessibility tree fully populated at all times, so UI Automation
can always find and click its buttons -- while staying out of your way
visually.
"""

import time

import psutil
import win32con
import win32gui
import win32process

OPENRGB_PROCESS_NAME = "openrgb.exe"
OPENRGB_WINDOW_CLASS_SUBSTR = "QWindowIcon"  # real main window, not popup-shadow helpers

# Off-screen parking position (well outside any real monitor).
PARK_X = -32000
PARK_Y = -32000

# Normal on-screen size/position used when showing interactively.
INTERACTIVE_X = 100
INTERACTIVE_Y = 100
INTERACTIVE_WIDTH = 861
INTERACTIVE_HEIGHT = 522


def find_openrgb_pid():
    for proc in psutil.process_iter(["pid", "name"]):
        if proc.info["name"] and proc.info["name"].lower() == OPENRGB_PROCESS_NAME:
            return proc.info["pid"]
    return None


def find_main_hwnd(pid):
    matches = []

    def callback(hwnd, _):
        _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
        if found_pid == pid:
            class_name = win32gui.GetClassName(hwnd)
            if OPENRGB_WINDOW_CLASS_SUBSTR in class_name:
                matches.append(hwnd)
        return True

    win32gui.EnumWindows(callback, None)
    return matches[0] if matches else None


def get_openrgb_hwnd():
    pid = find_openrgb_pid()
    if pid is None:
        return None
    return find_main_hwnd(pid)


def ensure_parked(hwnd, settle_seconds=0.4):
    """Make sure the window is shown (not minimized/hidden), off-screen,
    and has no taskbar/Alt-Tab presence. Safe to call repeatedly/idempotently."""
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    ex_style |= win32con.WS_EX_TOOLWINDOW
    ex_style &= ~win32con.WS_EX_APPWINDOW

    # Toggle hide/show around the style change -- this is the standard trick
    # to force Windows to actually refresh the taskbar/Alt-Tab presence.
    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
    win32gui.SetWindowPos(
        hwnd, None, PARK_X, PARK_Y, INTERACTIVE_WIDTH, INTERACTIVE_HEIGHT,
        win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER,
    )
    win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
    time.sleep(settle_seconds)


def show_interactive(hwnd):
    """Bring the window to a normal on-screen position with taskbar/Alt-Tab
    presence restored, and put it in the foreground."""
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    ex_style &= ~win32con.WS_EX_TOOLWINDOW
    ex_style |= win32con.WS_EX_APPWINDOW

    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
    win32gui.SetWindowPos(
        hwnd, None, INTERACTIVE_X, INTERACTIVE_Y, INTERACTIVE_WIDTH, INTERACTIVE_HEIGHT,
        win32con.SWP_NOZORDER,
    )
    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        # SetForegroundWindow can fail/error spuriously due to Windows'
        # foreground-lock restrictions; the window is already shown at this
        # point regardless, so this is just a "bring to front" nicety.
        pass