; Instalador de AirWin (Inno Setup 6) — lo genera GitHub Actions o:  iscc installer\AirWin.iss
#define AppName "AirWin"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{7D4B2C1E-5A3F-4E8B-9C2D-AE11F0A1B2C3}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=emanueldev1
AppPublisherURL=https://github.com/emanueldev1/airwin
AppSupportURL=https://github.com/emanueldev1/airwin/issues
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\dist
OutputBaseFilename=AirWin-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\AirWin.exe
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
LicenseFile=..\LICENSE

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\AirWin\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\AirWin.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\AirWin.exe"; Tasks: desktopicon

[Run]
; Permitir que el Apple TV descargue videos del PC y que se vean los dispositivos (sólo redes privadas).
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""AirWin"" dir=in action=allow program=""{app}\AirWin.exe"" profile=private,domain"; Flags: runhidden
Filename: "{app}\AirWin.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""AirWin"""; Flags: runhidden; RunOnceId: "fw"
