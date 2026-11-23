; The Windows download: an installer for dist\Colbert (built by PyInstaller from app\colbert.spec).
;
;   iscc /DAppVersion=0.1.0 tools\colbert-setup.iss      -> Colbert-Windows-Setup.exe
;
; Installs for the current user only (no administrator rights, nothing outside the user's
; profile), adds Colbert to the Start menu, and can be removed from Settings -> Apps. Settings,
; checkpoints and results live in %APPDATA%\Colbert and survive upgrades and uninstalling.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{7FAD1B0F-16D2-4198-91CA-877EFFBC72A3}
AppName=Colbert
AppVersion={#AppVersion}
AppVerName=Colbert {#AppVersion}
AppPublisher=Cade Ryan
AppPublisherURL=https://github.com/CadeRyan/colbert
AppSupportURL=https://github.com/CadeRyan/colbert/issues
DefaultDirName={autopf}\Colbert
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..
OutputBaseFilename=Colbert-Windows-Setup
SetupIconFile=..\app\icons\colbert.ico
UninstallDisplayIcon={app}\Colbert.exe
UninstallDisplayName=Colbert
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; an upgrade closes a running Colbert first (it saves progress every few minutes)
CloseApplications=force

[Tasks]
Name: "desktopicon"; Description: "Put Colbert on the desktop"; Flags: unchecked

[Files]
Source: "..\dist\Colbert\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[InstallDelete]
; files from an older version that this one no longer ships
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\Colbert"; Filename: "{app}\Colbert.exe"
Name: "{autodesktop}\Colbert"; Filename: "{app}\Colbert.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Colbert.exe"; Description: "Open Colbert now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; stop the app and its engine before removing their files
Filename: "{sys}\taskkill.exe"; Parameters: "/IM Colbert.exe /T /F"; Flags: runhidden; RunOnceId: "StopColbert"
Filename: "{sys}\taskkill.exe"; Parameters: "/IM colbert.exe /T /F"; Flags: runhidden; RunOnceId: "StopEngine"
