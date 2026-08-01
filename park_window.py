"""Run this after you're done using the OpenRGB GUI interactively, instead
of closing it with the X button. This parks it off-screen with no taskbar
presence, while keeping it fully accessible to the watcher script."""

from openrgb_window import ensure_parked, get_openrgb_hwnd


def main():
    hwnd = get_openrgb_hwnd()
    if hwnd is None:
        print("OpenRGB main window not found -- is OpenRGB running?")
        return

    print(f"Parking OpenRGB window (hwnd={hwnd})...")
    ensure_parked(hwnd)
    print("Done. Window is off-screen with no taskbar presence.")


if __name__ == "__main__":
    main()
