#ifndef MyAppVersion
  #define MyAppVersion "0.4.0"
#endif
#ifndef SourceRoot
  #define SourceRoot "..\\dist\\OpenVINOWindowsLLM"
#endif
#ifndef ArtifactDir
  #define ArtifactDir "..\\artifacts"
#endif
#ifndef ArtifactSuffix
  #define ArtifactSuffix "unsigned"
#endif

#define MyAppName "OpenVINO Windows LLM"
#define MyAppPublisher "Quazmoz"
#define MyAppExeName "OpenVINOWindowsLLM.exe"

[Setup]
AppId={{F94A3938-C943-4E6D-B482-852D4AAE06F8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/Quazmoz/openvino-windows-llm
AppSupportURL=https://github.com/Quazmoz/openvino-windows-llm/issues
AppUpdatesURL=https://github.com/Quazmoz/openvino-windows-llm/releases
DefaultDirName={localappdata}\Programs\OpenVINOWindowsLLM
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#ArtifactDir}
OutputBaseFilename=OpenVINOWindowsLLM-{#MyAppVersion}-windows-x64-setup-{#ArtifactSuffix}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\LICENSE
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    ResultCode := SuppressibleMsgBox(
      'Keep downloaded models, settings, logs, and benchmark data?' + #13#10 + #13#10 +
      'Choose Yes to preserve data for a future installation. Choose No to remove the user data directory.',
      mbConfirmation, MB_YESNO, IDYES);
    if ResultCode = IDNO then
      DelTree(ExpandConstant('{localappdata}\OpenVINOWindowsLLM'), True, True, True);
  end;
end;
