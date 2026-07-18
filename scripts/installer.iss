[Setup]
AppName=Licenditor
AppVersion=1.0.0
DefaultDirName={autopf}\Licenditor
DefaultGroupName=Licenditor
UninstallDisplayIcon={app}\Licenditor.exe
OutputDir={#SourcePath}\..\dist
OutputBaseFilename=Licenditor_Setup
SetupIconFile={#SourcePath}\..\libs\app-icon\icon.ico
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
DisableProgramGroupPage=yes

[Files]
Source: "{#SourcePath}\..\dist\Licenditor.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}\..\libs\app-icon\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Licenditor"; Filename: "{app}\Licenditor.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Licenditor"; Filename: "{app}\Licenditor.exe"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"

[Run]
Filename: "{app}\Licenditor.exe"; Description: "Chay Licenditor"; Flags: postinstall nowait skipifsilent shellexec
