; Install-Backseat.exe, built by release.py with Inno Setup 6: Backseat's files, then install.ps1 in a window you can watch
; (Python 3.12 if missing, its packages, your API key, the shortcuts). One click, no admin rights, the same folder the
; .bat installs to, so either can update the other. Its uninstaller (Windows Settings > Apps > Backseat) removes the
; program and asks before deleting your memory, settings, key, characters and Hall of Shame.
#ifndef Src
  #define Src "build\exe\Backseat"
#endif
#ifndef Version
  #define Version "0.0.0"
#endif
#ifndef Name
  #define Name Version
#endif

[Setup]
; never change the AppId: install.ps1 uses it to keep Settings > Apps' version current after an auto-update
AppId={{9CFB28A7-8A68-4EAF-AA77-952507EC47E8}
AppName=Backseat
AppVersion={#Version}
AppVerName=Backseat {#Name}
AppPublisher=DivxPlays
AppPublisherURL=https://github.com/DivxPlays/backseat
AppSupportURL=https://github.com/DivxPlays/backseat/issues
AppUpdatesURL=https://github.com/DivxPlays/backseat/releases
DefaultDirName={localappdata}\Programs\Backseat
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=Install-Backseat
SetupIconFile={#Src}\vorn.ico
UninstallDisplayIcon={app}\vorn.ico
UninstallDisplayName=Backseat
WizardStyle=modern
Compression=lzma2
SolidCompression=yes

[Files]
Source: "{#Src}\*"; Excludes: "\presets\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; characters: only ones this PC doesn't have yet (an update must not undo your Settings > Character changes)
Source: "{#Src}\presets\*"; DestDir: "{app}\presets"; Flags: onlyifdoesntexist uninsneveruninstall

[Run]
Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: """{app}\main.py"""; WorkingDir: "{app}"; Description: "Start Backseat"; Flags: postinstall nowait skipifsilent; Check: SetUp

[Code]
var
  Done, Wipe: Boolean;

function SetUp: Boolean;
begin
  Result := Done;
end;

{ a path inside a PowerShell '...' string (a name like O'Brien in it doubles its quote) }
function Quoted(S: String): String;
begin
  Result := S;
  StringChangeEx(Result, '''', '''''', True);
  Result := '''' + Result + '''';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Code: Integer;
  Vorn: String;
begin
  Vorn := ExpandConstant('{localappdata}\Programs\Vorn');
  if (CurStep = ssInstall) and DirExists(Vorn) and not DirExists(ExpandConstant('{app}')) then
    RenameFile(Vorn, ExpandConstant('{app}'));  { installed when it was called Vorn: memory, settings and key come along }
  if CurStep <> ssPostInstall then
    exit;
  WizardForm.StatusLabel.Caption := 'Installing Python and what Backseat needs (a few minutes the first time)...';
  Done := Exec('powershell.exe', '-NoProfile -ExecutionPolicy Bypass -Command "try { & ' +
    Quoted(ExpandConstant('{app}\install.ps1')) + ' -Dest ' + Quoted(ExpandConstant('{app}')) + ' -NoLaunch; exit 0 } ' +
    'catch { Write-Host $_ -ForegroundColor Red; Read-Host ''Setup failed (the reason is above). Press Enter to close''; exit 1 }"',
    ExpandConstant('{app}'), SW_SHOW, ewWaitUntilTerminated, Code) and (Code = 0);
  if not Done then
    SuppressibleMsgBox('Backseat''s setup didn''t finish. Check your internet connection, then run Install-Backseat.exe again.',
      mbError, MB_OK, IDOK);
end;

{ yours: kept when you uninstall and say No to deleting them (the uninstaller's own files go after this runs) }
function Kept(N: String): Boolean;
begin
  N := Lowercase(N);
  Result := (N = 'api_key.txt') or (N = 'memory.json') or (N = 'settings.json') or (N = 'battle reports.txt') or
    (N = 'hall of shame') or (N = 'presets') or (Pos('memory backup ', N) = 1) or (Pos('unins', N) = 1);
end;

procedure RemoveAllBut(Dir: String);
var
  F: TFindRec;
begin
  if FindFirst(Dir + '\*', F) then
    try
      repeat
        if (F.Name <> '.') and (F.Name <> '..') and not Kept(F.Name) then
          if F.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0 then
            DelTree(Dir + '\' + F.Name, True, True, True)
          else
            DeleteFile(Dir + '\' + F.Name);
      until not FindNext(F);
    finally
      FindClose(F);
    end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Code: Integer;
  App: String;
begin
  App := ExpandConstant('{app}');
  if CurUninstallStep = usUninstall then
  begin
    { quit Backseat if it runs (its venv starts the real Python elsewhere, so it's found by its main.py) }
    Exec('powershell.exe', '-NoProfile -Command "$m = ' + Quoted(Lowercase(App + '\main.py')) + '; Get-CimInstance Win32_Process | ' +
      'Where-Object { $_.CommandLine -and $_.CommandLine.ToLower().Contains($m) } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"',
      '', SW_HIDE, ewWaitUntilTerminated, Code);
    Exec('schtasks.exe', '/Delete /TN Backseat /F', '', SW_HIDE, ewWaitUntilTerminated, Code);  { Start with Windows }
    RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'BackseatCompanion');
    DeleteFile(ExpandConstant('{userprograms}\Backseat.lnk'));  { install.ps1 made these }
    DeleteFile(ExpandConstant('{userdesktop}\Backseat.lnk'));
    { (a silent uninstall, /SUPPRESSMSGBOXES, takes the default: keep them; a plain MsgBox would wait for a click) }
    Wipe := SuppressibleMsgBox('Also delete your memory, settings, API key, characters and Hall of Shame?' + #13#13 +
      'No keeps them in ' + App + ', so installing Backseat again picks up where you left off.',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES;
  end;
  if CurUninstallStep = usPostUninstall then
    if Wipe then
      DelTree(App, True, True, True)
    else
      RemoveAllBut(App);  { the program, Python, its packages and voice models: files auto-updates added included }
end;
