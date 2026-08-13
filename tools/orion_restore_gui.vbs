Option Explicit

' Canonical safe ORION synchronization launcher.
Dim shell, fso, toolsDir, scriptPath, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
toolsDir = fso.GetParentFolderName(WScript.ScriptFullName)
scriptPath = fso.BuildPath(toolsDir, "orion_safe_sync_gui.pyw")
If Not fso.FileExists(scriptPath) Then
    MsgBox "ORION Safe Sync file is missing:" & vbCrLf & scriptPath, vbCritical, "ORION Safe Sync"
    WScript.Quit 1
End If
shell.CurrentDirectory = toolsDir
On Error Resume Next
Err.Clear
command = "pythonw.exe " & Chr(34) & scriptPath & Chr(34)
shell.Run command, 0, False
If Err.Number <> 0 Then
    Err.Clear
    command = "pyw.exe " & Chr(34) & scriptPath & Chr(34)
    shell.Run command, 0, False
End If
If Err.Number <> 0 Then
    MsgBox "ORION Safe Sync could not start." & vbCrLf & scriptPath, vbCritical, "ORION Safe Sync"
    WScript.Quit 1
End If
On Error GoTo 0
Set fso = Nothing
Set shell = Nothing
