; Instalador de AirWin (Inno Setup 6). Lo genera GitHub Actions o:  iscc /DAppVersion=1.2.3 installer\AirWin.iss
; Se instala por usuario (como VS Code o Discord): no pide permisos de administrador,
; así el actualizador integrado puede instalar versiones nuevas en silencio.
#define AppName "AirWin"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{7D4B2C1E-5A3F-4E8B-9C2D-AE11F0A1B2C3}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=emanueldev1
AppPublisherURL=https://github.com/emanueldev1/airwin
AppSupportURL=https://github.com/emanueldev1/airwin/issues
AppUpdatesURL=https://github.com/emanueldev1/airwin/releases
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=AirWin-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\AirWin.exe
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force
RestartApplications=no
LicenseFile=..\LICENSE

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Limpia archivos de la versión anterior que ya no existan en la nueva.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\AirWin\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\AirWin.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\AirWin.exe"; Tasks: desktopicon

[Run]
; Instalación normal: casilla «Abrir AirWin» al final.
Filename: "{app}\AirWin.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
; Actualización silenciosa desde la app: volver a abrirla sola.
Filename: "{app}\AirWin.exe"; Flags: nowait; Check: WizardSilent
