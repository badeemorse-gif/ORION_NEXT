Option Explicit

Dim shell, fso, scriptDir, pyw, scriptPath, cmd, rc, branchArg

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
scriptPath = scriptDir & "\orion_restore_gui_dynamic.pyw"

If Not fso.FileExists(scriptPath) Then
    MsgBox "ORION Restore dynamic file not found:" & vbCrLf & scriptPath, vbCritical, "ORION Restore"
    WScript.Quit 1
End If

pyw = "pythonw.exe"

On Error Resume Next
rc = shell.Run("""" & pyw & """ --version", 0, True)

If Err.Number <> 0 Or rc <> 0 Then
    Err.Clear
    pyw = "pyw.exe"
    rc = shell.Run("""" & pyw & """ --version", 0, True)

    If Err.Number <> 0 Or rc <> 0 Then
        On Error GoTo 0
        MsgBox "Python (pythonw.exe / pyw.exe) was not found." & vbCrLf & vbCrLf & _
               "Please verify that Python is installed and available in PATH.", _
               vbCritical, "ORION Restore"
        WScript.Quit 1
    End If
End If

On Error GoTo 0

branchArg = ""
If WScript.Arguments.Count > 0 Then
    branchArg = Trim(WScript.Arguments(0))
End If

cmd = """" & pyw & """ """ & scriptPath & """"
If branchArg <> "" Then
    cmd = cmd & " """ & branchArg & """"
End If
shell.Run cmd, 0, False

Set shell = Nothing
Set fso = Nothing
