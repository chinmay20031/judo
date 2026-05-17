' Silent launcher for Judo - runs without showing console
Set objShell = CreateObject("WScript.Shell")
strPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
objShell.Run "cmd /c cd /d " & strPath & " && .venv\Scripts\python.exe judo.py voice > nul 2>&1", 0, False
