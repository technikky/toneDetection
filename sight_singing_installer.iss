; Sight-Singing Studio -- Inno Setup installer script.
; Build with: offline-sdk\tools\inno-setup\ISCC.exe sight_singing_installer.iss
; Requires dist\SightSingingStudio.exe to already exist (pyinstaller sight_singing.spec).
;
; NOT CODE-SIGNED. Windows SmartScreen will warn on first run until this is
; signed with a real code-signing certificate -- see docs/packaging/CODE_SIGNING.md.

#define MyAppName "Sight-Singing Studio"
#define MyAppVersion "0.1.0-beta"
#define MyAppPublisher "Sight-Singing Studio"
#define MyAppExeName "SightSingingStudio.exe"

[Setup]
AppId={{B1E7B1B0-3F1A-4E2A-9E36-1B7D6A8B4F21}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer-output
OutputBaseFilename=SightSingingStudioSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "dist\SightSingingStudio.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
