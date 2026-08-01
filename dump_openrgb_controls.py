from pywinauto import Desktop
from openrgb_window import get_openrgb_hwnd

hwnd = get_openrgb_hwnd()
w = Desktop(backend="uia").window(handle=hwnd)
w.print_control_identifiers()
