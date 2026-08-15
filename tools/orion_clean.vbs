Option Explicit

Dim shell
Dim fso
Dim scriptDir
Dim pythonScript
Dim command

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Directory containing this VBS launcher
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' ORION CLEAN Python GUI
pythonScript = fso.BuildPath(scriptDir, "orion_clean_gui.py")

' Verify that the Python program exists
If Not fso.FileExists(pythonScript) Then
    MsgBox _
        "ORION CLEAN could not be started." & vbCrLf & vbCrLf & _
        "Python program not found:" & vbCrLf & _
        pythonScript, _
        vbCritical, _
        "ORION CLEAN"
    WScript.Quit 1
End If

' Start Python without showing a CMD window.
' WindowStyle = 0  -> hidden
' WaitOnReturn = False -> GUI runs independently
command = "pythonw.exe """ & pythonScript & """"

shell.Run command, 0, False

Set fso = Nothing
Set shell = Nothing