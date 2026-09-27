#include "version.iss"

[Setup]
AppId={{F72E59D8-41C1-4A22-9DBA-14F8C331D292}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppVerName={#MyAppName} {#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppDescription}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
; Keep the v0.7.3 install path so AppId-based upgrades reuse the existing install.
DefaultDirName={localappdata}\Programs\CodexUsageMonitor
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release
OutputBaseFilename=QuotaTray-{#MyAppVersion}-Setup
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "startupwithwindows"; Description: "Start QuotaTray with Windows"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "..\dist\QuotaTray\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

; PyInstaller onedir payloads change shape between builds (a library can be
; dropped, renamed or moved between directories). A plain overwrite leaves the
; files that the new build no longer ships, producing a mixed old/new payload —
; exactly the class of problem that produces confusing native DLL load errors.
; Remove the previous payload before laying down the new one.
;
; This ONLY touches the program directory ({app}); user data lives in
; %LOCALAPPDATA%\CodexUsageMonitor (usage.db, settings, logs) and is never
; referenced here. PrepareToInstall requests shutdown and verifies exit before
; these entries run; upgrades do not automatically run the old uninstaller.
[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\{#MyAppExeName}"
Type: files; Name: "{app}\CodexUsageMonitor.exe"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\_internal\assets\app.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\_internal\assets\app.ico"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "CodexUsageMonitor"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: startupwithwindows; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch QuotaTray"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--quit"; RunOnceId: "QuitCodexUsageMonitor"; Flags: runhidden waituntilterminated skipifdoesntexist

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: dirifempty; Name: "{app}"

[Code]
const
  VCRedistRegistryKey = 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64';
  VCRedistOfficialUrl = 'https://aka.ms/vc14/vc_redist.x64.exe';

function IsNumericVersionComponent(Value: String): Boolean;
var
  I: Integer;
begin
  Result := Value <> '';
  for I := 1 to Length(Value) do
    if (Value[I] < '0') or (Value[I] > '9') then begin
      Result := False;
      exit;
    end;
end;

function ParseRuntimeVersion(Value: String; var Major, Minor, Build: Cardinal): Boolean;
var
  Dot, Parsed: Integer;
  MajorText, MinorText, BuildText, RevisionText: String;
  HasRevision: Boolean;
  Work: String;
begin
  Result := False;
  HasRevision := False;
  Work := Trim(Value);
  if (Length(Work) > 0) and ((Work[1] = 'v') or (Work[1] = 'V')) then
    Delete(Work, 1, 1);
  Dot := Pos('.', Work);
  if Dot <= 1 then exit;
  MajorText := Copy(Work, 1, Dot - 1);
  Delete(Work, 1, Dot);
  Dot := Pos('.', Work);
  if Dot <= 1 then exit;
  MinorText := Copy(Work, 1, Dot - 1);
  Delete(Work, 1, Dot);
  Dot := Pos('.', Work);
  if Dot = 0 then begin
    BuildText := Work;
    RevisionText := '';
  end else begin
    if Dot <= 1 then exit;
    HasRevision := True;
    BuildText := Copy(Work, 1, Dot - 1);
    Delete(Work, 1, Dot);
    RevisionText := Work;
  end;
  if not IsNumericVersionComponent(MajorText) or
      not IsNumericVersionComponent(MinorText) or
      not IsNumericVersionComponent(BuildText) then exit;
  if HasRevision and not IsNumericVersionComponent(RevisionText) then exit;
  Parsed := StrToIntDef(MajorText, -1);
  if (Parsed < 0) or (Parsed > 65535) then exit;
  Major := Parsed;
  Parsed := StrToIntDef(MinorText, -1);
  if (Parsed < 0) or (Parsed > 65535) then exit;
  Minor := Parsed;
  Parsed := StrToIntDef(BuildText, -1);
  if (Parsed < 0) or (Parsed > 65535) then exit;
  Build := Parsed;
  if (RevisionText <> '') then begin
    if not IsNumericVersionComponent(RevisionText) then exit;
    Parsed := StrToIntDef(RevisionText, -1);
    if (Parsed < 0) or (Parsed > 65535) then exit;
  end;
  Result := True;
end;

function RuntimeVersionAtLeast(InstalledMajor, InstalledMinor, InstalledBuild: Cardinal): Boolean;
begin
  Result := (InstalledMajor = 14) and (InstalledMinor >= 44);
end;

function HasSupportedVCRedist: Boolean;
var
  Installed, Major, Minor, Build, VersionMajor, VersionMinor, VersionBuild: Cardinal;
  Version: String;
begin
  Result := False;
  if not IsWin64 then exit;
  if not RegQueryDWordValue(HKEY_LOCAL_MACHINE_64, VCRedistRegistryKey,
      'Installed', Installed) or (Installed <> 1) then exit;
  if not RegQueryDWordValue(HKEY_LOCAL_MACHINE_64, VCRedistRegistryKey,
      'Major', Major) then exit;
  if not RegQueryDWordValue(HKEY_LOCAL_MACHINE_64, VCRedistRegistryKey,
      'Minor', Minor) then exit;
  if not RegQueryDWordValue(HKEY_LOCAL_MACHINE_64, VCRedistRegistryKey,
      'Bld', Build) then exit;
  if not RegQueryStringValue(HKEY_LOCAL_MACHINE_64, VCRedistRegistryKey,
      'Version', Version) then exit;
  if not ParseRuntimeVersion(Version, VersionMajor, VersionMinor, VersionBuild) then exit;
  if (VersionMajor <> Major) or (VersionMinor <> Minor) or (VersionBuild <> Build) then exit;
  Result := RuntimeVersionAtLeast(Major, Minor, Build);
end;

function InitializeSetup: Boolean;
var
  MessageText: String;
  ErrorCode: Integer;
begin
  Result := HasSupportedVCRedist;
  if Result then exit;
  MessageText := 'QuotaTray requires the Microsoft Visual C++ Redistributable (x64).' + #13#10 + #13#10 +
    'Install the Microsoft official x64 package, then run the QuotaTray installer again.' + #13#10 +
    VCRedistOfficialUrl;
  MsgBox(MessageText, mbError, MB_OK);
  if MsgBox('Open the Microsoft download page now?', mbConfirmation, MB_YESNO) = IDYES then
    ShellExec('open', VCRedistOfficialUrl, '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
  Result := False;
end;

function MonitorRunning: Boolean;
var
  Services, Processes: Variant;
begin
  { Check process lifetime as well as the mutex: guards close just before exit. }
  Services := CreateOleObject('WbemScripting.SWbemLocator');
  Services := Services.ConnectServer('.', 'root\CIMV2');
  Processes := Services.ExecQuery('SELECT ProcessId FROM Win32_Process WHERE Name = ''CodexUsageMonitor.exe'' OR Name = ''QuotaTray.exe''');
  Result := (Processes.Count > 0) or
    CheckForMutexes('Local\CodexUsageMonitor.SingleInstance.Mutex');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  OldExe: String;
  ResultCode, Attempt: Integer;
begin
  Result := '';
  try
    if not MonitorRunning then exit;
    OldExe := ExpandConstant('{app}\CodexUsageMonitor.exe');
    if not FileExists(OldExe) then
      OldExe := ExpandConstant('{app}\{#MyAppExeName}');
    if not FileExists(OldExe) then begin
      Result := 'QuotaTray is running. Exit it from its tray menu, then retry installation.';
      exit;
    end;
    Log('Requesting graceful shutdown using installed executable --quit');
    if not Exec(OldExe, '--quit', ExpandConstant('{app}'), SW_HIDE,
        ewNoWait, ResultCode) then begin
      Result := 'Could not request QuotaTray shutdown. Exit it from its tray menu, then retry installation.';
      exit;
    end;
    for Attempt := 1 to 120 do begin
      Sleep(250);
      if not MonitorRunning then begin
        Log('QuotaTray exit confirmed before program file cleanup');
        exit;
      end;
    end;
    Result := 'QuotaTray did not exit within 30 seconds. No program files were replaced. Exit it from its tray menu, then retry or cancel installation.';
  except
    Result := 'Unable to verify Codex Usage Monitor has exited. Installation stopped before replacing program files. ' + GetExceptionMessage;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  StartupValue: String;
begin
  { Preserve enabled v0.7.3 startup while retargeting its stable Run value. }
  if CurStep = ssPostInstall then
  begin
    if RegQueryStringValue(HKEY_CURRENT_USER,
        'Software\Microsoft\Windows\CurrentVersion\Run',
        'CodexUsageMonitor', StartupValue) then
    begin
      if (Pos('CodexUsageMonitor.exe', StartupValue) > 0) or
         (Pos('QuotaTray.exe', StartupValue) > 0) then
        RegWriteStringValue(HKEY_CURRENT_USER,
          'Software\Microsoft\Windows\CurrentVersion\Run',
          'CodexUsageMonitor', '"' + ExpandConstant('{app}\{#MyAppExeName}') + '"');
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'CodexUsageMonitor');
  end;
end;
