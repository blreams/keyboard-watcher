"""Run this to bring the OpenRGB window back on-screen for interactive use.
When you're done, run park_window.py instead of closing with the X button."""

from openrgb_window import get_openrgb_hwnd, show_interactive


def main():
    hwnd = get_openrgb_hwnd()
    if hwnd is None:
        print("OpenRGB main window not found -- is OpenRGB running?")
        return

    print(f"Showing OpenRGB window (hwnd={hwnd})...")
    show_interactive(hwnd)
    print("Done. When finished, run park_window.py (not the X button).")


if __name__ == "__main__":
    main()
