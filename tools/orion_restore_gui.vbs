Option Explicit

Dim shell, fso, toolsDir, scriptPath, cmd, rc
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

toolsDir = fso.GetParentFolderName(WScript.ScriptFullName)
scriptPath = fso.BuildPath(toolsDir, "orion_restore_gui.pyw")

If Not fso.FileExists(scriptPath) Then
    MsgBox "ملف ORION Restore غير موجود:" & vbCrLf & scriptPath, vbCritical, "ORION Restore"
    WScript.Quit 1
End If

shell.CurrentDirectory = toolsDir

On Error Resume Next
Err.Clear
cmd = "pythonw.exe " & Chr(34) & scriptPath & Chr(34)
rc = shell.Run(cmd, 1, False)

If Err.Number <> 0 Then
    Err.Clear
    rc = shell.Run(Chr(34) & scriptPath & Chr(34), 1, False)
End If

If Err.Number <> 0 Then
    MsgBox "تعذر تشغيل ORION Restore." & vbCrLf & _
           "تأكد أن Python مثبت وأن ملفات .pyw مرتبطة بـ Python." & vbCrLf & vbCrLf & _
           scriptPath, vbCritical, "ORION Restore"
    WScript.Quit 1
End If

On Error GoTo 0
Set fso = Nothing
Set shell = Nothing
