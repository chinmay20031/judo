# Setup script to register Judo for auto-start on Windows boot
# Run this once with: powershell -ExecutionPolicy Bypass -File setup_autostart.ps1

$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$JudoDir = $ScriptPath
$VBSFile = Join-Path $JudoDir "run_judo_silent.vbs"
$BatchFile = Join-Path $JudoDir "run_judo_silent.bat"

# Ensure venv is set up
if (!(Test-Path (Join-Path $JudoDir ".venv"))) {
    Write-Error ".venv not found. Please run setup and install dependencies first."
    exit 1
}

# Create a scheduled task that runs at startup
$TaskName = "JudoVoiceAgent"
$TaskDescription = "Judo Windows Voice Agent - runs silently on startup"

Write-Host "Setting up auto-start task: $TaskName"

# Use the VBS file for silent execution
$Action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument $VBSFile
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

try {
    # Remove old task if it exists
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
    
    # Register new task
    Register-ScheduledTask -TaskName $TaskName `
        -Description $TaskDescription `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -RunLevel Highest | Out-Null
    
    Write-Host "[SUCCESS] Registered '$TaskName' to run at startup."
    Write-Host ""
    Write-Host "Judo will now:"
    Write-Host "  - Start automatically when you log in"
    Write-Host "  - Run in voice mode (listening mode)"
    Write-Host "  - Display no console window"
    Write-Host ""
    Write-Host "To verify the task:"
    Write-Host "  - Press Win+R and type: taskschd.msc"
    Write-Host "  - Find '$TaskName' in the task list"
    Write-Host ""
    Write-Host "To disable auto-start later:"
    Write-Host "  - Run: Unregister-ScheduledTask -TaskName $TaskName"
    Write-Host "  - Or disable in Task Scheduler"
}
catch {
    Write-Host "ERROR: Failed to register scheduled task: $PSItem"
    exit 1
}
