Option Explicit

' Windows launcher for the combined ORION Restore UI.
' MAIN is isolated into ORION_NEXT_MAIN so it never overwrites the development checkout.
Dim shell, fso, toolsDir, scriptPath, command, testArgument
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

toolsDir = fso.GetParentFolderName(WScript.ScriptFullName)
scriptPath = fso.BuildPath(toolsDir, "orion_restore_main_safe_gui.pyw")
If Not fso.FileExists(scriptPath) Then
    MsgBox "ORION Restore file is missing:" & vbCrLf & scriptPath, vbCritical, "ORION Restore"
    WScript.Quit 1
End If

testArgument = ""
If shell.Environment("PROCESS")("ORION_RESTORE_LAUNCH_TEST") = "1" Then testArgument = " --launch-smoke-test"
shell.CurrentDirectory = toolsDir

On Error Resume Next
Err.Clear
command = "pythonw.exe " & Chr(34) & scriptPath & Chr(34) & testArgument
shell.Run command, 0, False
If Err.Number <> 0 Then
    Err.Clear
    command = "pyw.exe " & Chr(34) & scriptPath & Chr(34) & testArgument
    shell.Run command, 0, False
End If
If Err.Number <> 0 Then
    MsgBox "ORION Restore could not start." & vbCrLf & _
           "Install Python for Windows (including pythonw.exe), then run this launcher again." & vbCrLf & vbCrLf & _
           scriptPath, vbCritical, "ORION Restore"
    WScript.Quit 1
End If
On Error GoTo 0
Set fso = Nothing
Set shell = Nothing
