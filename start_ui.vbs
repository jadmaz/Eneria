Set objShell = CreateObject("WScript.Shell")
strPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
objShell.Run """" & strPath & "\.venv\Scripts\pythonw.exe"" """ & strPath & "\program.py""", 0, False
