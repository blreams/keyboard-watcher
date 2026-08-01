# keyboard-watcher

Watches for a Razer keyboard to reconnect through a KVM switch and automatically reapplies the OpenRGB lighting profile when it does.

## Problem

When a KVM switches away and back, Windows re-enumerates the USB keyboard, which causes OpenRGB to lose the applied lighting profile. This watcher detects the reconnect via WMI and clicks OpenRGB's **Rescan** and **Load Profile** buttons automatically — no manual intervention needed.

## How it works

- Polls the keyboard's USB device instance via WMI every 1.5 seconds
- On reconnect, waits briefly for USB enumeration to settle, then drives OpenRGB's UI via UI Automation to rescan devices and reload the profile
- Listens on OpenRGB's SDK socket for the `DEVICE_LIST_UPDATED` packet to confirm the rescan completed before loading the profile
- Keeps OpenRGB's window permanently "parked" off-screen (no taskbar/Alt-Tab presence) so UI Automation can always reach its buttons without the window being in your way

## Requirements

- Windows 10/11
- [OpenRGB](https://openrgb.org/) running with the SDK server enabled (default port 6742)
- [uv](https://docs.astral.sh/uv/) for Python dependency management

## Setup

**1. Install dependencies**

```powershell
uv sync
```

**2. Register the startup task**

Run this once (as your normal user, not elevated) to register a scheduled task that starts the watcher automatically at login:

```powershell
.\register_startup_task.ps1
```

To start immediately without logging out:

```powershell
Start-ScheduledTask -TaskName "OpenRGB Keyboard Watcher"
```

**3. Make sure OpenRGB starts at login too**

The watcher expects OpenRGB to already be running. Configure OpenRGB to start at login via its own settings, or add it to your startup folder.

## Running manually

```powershell
uv run main.py
```

Logs are written to `watcher.log` in the project directory (auto-rotates at ~1 MB, keeps 3 backups).

## Utility scripts

| Script | Purpose |
|---|---|
| `show_gui.py` | Bring the OpenRGB window on-screen for interactive use |
| `park_window.py` | Park the OpenRGB window back off-screen when done |

When you want to use OpenRGB interactively, run `show_gui.py` to bring it on-screen. When finished, run `park_window.py` instead of closing it with the X button — closing it would break the watcher.

```powershell
uv run show_gui.py   # bring on screen
uv run park_window.py  # send back off screen
```

## Configuration

Key constants at the top of `main.py`:

| Constant | Default | Description |
|---|---|---|
| `KEYBOARD_EXACT_DEVICE_ID` | *(Razer-specific)* | WMI device instance ID for your keyboard |
| `POLL_SECONDS` | `1.5` | How often to check keyboard presence |
| `SETTLE_SECONDS` | `1.5` | Delay after reconnect before rescanning |
| `DEBOUNCE_SECONDS` | `3` | Minimum time between profile reapplications |
| `RESCAN_TIMEOUT_SECONDS` | `15` | Hard timeout waiting for OpenRGB rescan confirmation |

To use this with a different keyboard, update `KEYBOARD_EXACT_DEVICE_ID` to match your device. Find it with:

```powershell
Get-PnpDevice | Where-Object { $_.FriendlyName -like "*<your keyboard name>*" } | Select-Object InstanceId
```
