import logging
import os
import socket
import struct
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import psutil
import wmi
from pywinauto import Desktop

from openrgb_window import ensure_parked, get_openrgb_hwnd, show_interactive

# --- Configuration ---
# Exact, known-stable device instance ID for the keyboard's composite USB
# parent (confirmed stable across many reconnects). We match this exact ID
# rather than the VID/PID prefix, because Windows can leave behind stale
# "ghost" device-instance entries sharing the same VID/PID that intermittently
# report misleading status and were masking the real device's true state.
VERSION = "3"

KEYBOARD_EXACT_DEVICE_ID = "USB\\VID_1532&PID_0266\\9&32FBD72&0&2"
POLL_SECONDS = 1.5              # how often to check the keyboard's own connection status
SETTLE_SECONDS = 1.5            # let child interfaces finish enumerating after reconnect detected
DEBOUNCE_SECONDS = 3            # ignore repeat transitions within this window
RESCAN_TIMEOUT_SECONDS = 15     # hard cap fallback if we never see the "device list updated" packet

LOG_PATH = Path(__file__).parent / "watcher.log"
LOG_MAX_BYTES = 1_000_000       # rotate once the log reaches ~1 MB
LOG_BACKUP_COUNT = 3            # keep this many rotated backups (watcher.log.1, .2, .3)

RESCAN_AUTO_ID = "OpenRGBDialog.centralWidget.MainButtonsFrame.ButtonRescan"
PROFILE_BOX_AUTO_ID = "OpenRGBDialog.centralWidget.MainButtonsFrame.ProfileBox"
LOAD_PROFILE_AUTO_ID = "OpenRGBDialog.centralWidget.MainButtonsFrame.ButtonLoadProfile"
PROFILE_NAME = "BlueKeyboard"

OPENRGB_HOST = "127.0.0.1"
OPENRGB_PORT = 6742
NET_PACKET_ID_DEVICE_LIST_UPDATED = 100
HEADER_FORMAT = "<4sIII"  # magic(4s), dev_idx(I), pkt_id(I), pkt_size(I)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)


_logger = logging.getLogger("keyboard_watcher")
_logger.setLevel(logging.INFO)
_formatter = logging.Formatter(f"[%(asctime)s v{VERSION}] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

_file_handler = RotatingFileHandler(LOG_PATH, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT)
_file_handler.setFormatter(_formatter)
_logger.addHandler(_file_handler)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)
_logger.addHandler(_console_handler)


def log(message):
    _logger.info(message)


def kill_other_instances():
    current_pid = os.getpid()
    try:
        parent_pid = psutil.Process(current_pid).parent().pid
    except (psutil.NoSuchProcess, AttributeError):
        parent_pid = None

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        pid = proc.info["pid"]
        if pid in (current_pid, parent_pid):
            continue
        if not (proc.info.get("name") or "").lower().startswith("python"):
            continue
        if "keyboard_watcher.py" in (proc.info.get("cmdline") or []):
            log(f"Killing duplicate watcher process {pid}.")
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                pass


def wait_for_device_list_updated(timeout):
    """Block until OpenRGB's SDK server broadcasts DEVICE_LIST_UPDATED, or
    timeout elapses. Returns True if the notification was seen."""
    try:
        sock = socket.create_connection((OPENRGB_HOST, OPENRGB_PORT), timeout=timeout)
    except OSError as e:
        log(f"Could not connect to OpenRGB SDK server: {e}")
        return False

    sock.settimeout(1.0)
    deadline = time.time() + timeout
    buffer = b""
    try:
        while time.time() < deadline:
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            buffer += chunk
            while len(buffer) >= HEADER_SIZE:
                magic, dev_idx, pkt_id, pkt_size = struct.unpack(HEADER_FORMAT, buffer[:HEADER_SIZE])
                total_len = HEADER_SIZE + pkt_size
                if len(buffer) < total_len:
                    break
                buffer = buffer[total_len:]
                if pkt_id == NET_PACKET_ID_DEVICE_LIST_UPDATED:
                    return True
        return False
    finally:
        sock.close()


def reapply_profile():
    hwnd = get_openrgb_hwnd()
    if hwnd is None:
        log("OpenRGB main window not found -- is it running?")
        return

    # Self-heal: in case the window was left in the wrong state (e.g. someone
    # closed it with the X button, or it's mid-interactive-use), make sure
    # it's parked (shown, off-screen, no taskbar presence) before we click.
    ensure_parked(hwnd)
    window = Desktop(backend="uia").window(handle=hwnd)

    result = {}

    def listener():
        result["updated"] = wait_for_device_list_updated(RESCAN_TIMEOUT_SECONDS)

    listener_thread = threading.Thread(target=listener, daemon=True)
    listener_thread.start()
    time.sleep(0.3)  # give the listener socket a moment to connect first

    window.child_window(auto_id=RESCAN_AUTO_ID, control_type="Button").invoke()
    listener_thread.join(timeout=RESCAN_TIMEOUT_SECONDS + 2)
    if not result.get("updated"):
        log("Warning: no rescan confirmation from OpenRGB SDK server; proceeding anyway.")

    # Qt's UIA bridge doesn't implement SelectionItemPattern on ComboBox items,
    # so we must bring the window on-screen to use real mouse coordinates.
    show_interactive(hwnd)
    time.sleep(0.3)
    profile_box = window.child_window(auto_id=PROFILE_BOX_AUTO_ID, control_type="ComboBox")
    profile_box.click_input()  # physically click to open the dropdown
    time.sleep(0.3)
    profile_box.child_window(title=PROFILE_NAME, control_type="ListItem").click_input()
    log(f"Selected profile '{PROFILE_NAME}'.")

    window.child_window(auto_id=LOAD_PROFILE_AUTO_ID, control_type="Button").invoke()
    log("Profile reapplied.")
    ensure_parked(hwnd)


def keyboard_present(c):
    # Filter server-side (like PowerShell's Get-PnpDevice -InstanceId does)
    # instead of enumerating every PnP device on the system and filtering
    # in Python -- that full enumeration was taking ~30s per call.
    #
    # No backslash-escaping needed here -- confirmed earlier in this project
    # that WQL matches single backslashes in DeviceID strings as-is.
    wql = f"SELECT * FROM Win32_PnPEntity WHERE DeviceID = '{KEYBOARD_EXACT_DEVICE_ID}'"
    results = c.query(wql)
    if not results:
        return False
    return results[0].Status == "OK"


def main():
    log("Startup: killing duplicates...")
    kill_other_instances()
    log("Startup: connecting to WMI...")
    c = wmi.WMI()
    log("Startup: checking keyboard state...")
    was_present = keyboard_present(c)
    log(f"Keyboard watcher v{VERSION} started. Initial state: {'present' if was_present else 'absent'}.")

    # Park OpenRGB's window right away, rather than leaving it visible until
    # the first reconnect event happens to trigger reapply_profile().
    hwnd = get_openrgb_hwnd()
    if hwnd is not None:
        ensure_parked(hwnd)
        log("OpenRGB window parked.")
    else:
        log("OpenRGB not running yet at watcher startup -- will park on first reconnect instead.")

    last_applied = 0.0

    while True:
        time.sleep(POLL_SECONDS)
        now_present = keyboard_present(c)

        if now_present and not was_present:
            now = time.time()
            if now - last_applied >= DEBOUNCE_SECONDS:
                log("Keyboard reconnected -- reapplying OpenRGB profile.")
                time.sleep(SETTLE_SECONDS)
                reapply_profile()
                last_applied = time.time()

        was_present = now_present


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopping watcher.")
    except Exception as e:
        log(f"Fatal error: {e!r}")
