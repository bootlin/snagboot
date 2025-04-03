#define MyAppName "Snagboot"
#define MyAppVersion <EDITME>
#define MyAppPublisher "Bootlin"
#define MyAppURL "https://www.bootlin.com"
#define MyAppExeName "snagfactory.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application. Do not use the same AppId value in installers for other applications.
AppId={{DC9881D3-CE04-4CF8-842D-D8D10FF761C5}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\snagboot
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
LicenseFile=LICENSE
PrivilegesRequired=lowest
OutputBaseFilename=snagboot_installer_win64
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\snagboot\snagfactory.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\snagboot\snagflash.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\snagboot\snagrecover.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\snagboot\_internal\*"; DestDir: "{app}/_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{autoprograms}\snagfactory"; Filename: "{app}\snagfactory.exe"; IconFilename: "{app}\_internal\snagfactory\assets\lab_penguins.ico"
Name: "{autodesktop}\snagfactory"; Filename: "{app}\snagfactory.exe"; IconFilename: "{app}\_internal\snagfactory\assets\lab_penguins.ico"; Tasks: desktopicon
Name: "{autoprograms}\snagboot"; Filename: "powershell.exe"; Parameters: "-NoExit -Command $Env:PATH = '{app};$Env:PATH'; {app}\_internal\snagrecover\prompt.ps1"; IconFilename: "{app}\_internal\snagfactory\assets\lab_penguins.ico"
Name: "{autodesktop}\snagboot"; Filename: "powershell.exe"; Parameters: "-NoExit -Command $Env:PATH = '{app};$Env:PATH'; {app}\_internal\snagrecover\prompt.ps1"; IconFilename: "{app}\_internal\snagfactory\assets\lab_penguins.ico"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoExit -Command $Env:PATH = '{app};$Env:PATH'; {app}\_internal\snagrecover\prompt.ps1"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
