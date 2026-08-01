# Run this once (as your normal user, not elevated) to register the keyboard
# watcher to start automatically at login.
#
# Adjust $ProjectDir if your project folder is somewhere else.

$ProjectDir = "C:\Users\blreams\Documents\git\keyboard-watcher"
$TaskName = "OpenRGB Keyboard Watcher"
$VbsPath = Join-Path $ProjectDir "run_hidden.vbs"

$Action = New-ScheduledTaskAction `
    -Execute "wscript.exe" `
    -Argument "`"$VbsPath`"" `
    -WorkingDirectory $ProjectDir

$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero)  # no time limit -- this runs indefinitely

# Remove any existing registration of this task first, so this script can be
# safely re-run to pick up changes (e.g. after updating main.py or this script).
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "Existing task '$TaskName' found -- removing it before re-registering..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Watches for the Razer keyboard reconnecting through the KVM and reapplies the OpenRGB lighting profile." `
    -RunLevel Limited

Write-Host "Task '$TaskName' registered. It will start at your next login."
Write-Host "To start it immediately without logging out: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Logs will be written to: $ProjectDir\watcher.log (auto-rotates at ~1MB, keeps 3 backups)"
