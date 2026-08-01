' Launches the keyboard watcher with no visible console window.
' Used by the scheduled task instead of calling cmd.exe/uv.exe directly.

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\blreams\Documents\git\keyboard-watcher"
WshShell.Run """C:\Users\blreams\.local\bin\uv.exe"" run keyboard_watcher.py", 0, True
