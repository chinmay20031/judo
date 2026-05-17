@echo off
REM Silent batch launcher for Judo voice agent
REM Runs in background without showing console
cd /d "%~dp0"
if exist "%APPDATA%\Code\User\workspaceStorage\*\GitHub.copilot-chat\transcripts\*.jsonl" (
    REM Suppress any stray temp files created by VS Code
    del /q tempCodeRunnerFile.py >nul 2>&1
)
.venv\Scripts\python.exe judo.py voice > nul 2>&1
exit /b 0
