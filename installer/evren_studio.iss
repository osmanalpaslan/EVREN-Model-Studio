; EVREN Studio kurulum sihirbazı (Inno Setup 6). Derleme: tools\paketle.py (ISCC'ye /DAppVersion=... ve imza aracını verir).
; Kararlar: docs/ILERIDE_YAPILACAKLAR.md §1 (yalnız bu kullanıcı varsayılan, yönetici izni gerekmez; veri yeri değişmez).
; Gömülü yükleyiciler (installer/prereqs.json): yalnız bilgisayarda EKSİK olan program görev listesinde görünür ve kurulur.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\build\pyi\dist\EVREN Studio"
#endif
#ifndef PrereqDir
  #define PrereqDir "..\build\onkosullar"
#endif
#ifndef OutDir
  #define OutDir "..\dist"
#endif

#define AppName "EVREN Studio"
#define AppExe "EVREN Studio.exe"
#define PyFile "python-3.12.10-amd64.exe"
#define GitFile "Git-2.56.0.4-64-bit.exe"
#define NodeFile "node-v26.13.0-x64.msi"
#define GhFile "gh_2.103.3_windows_amd64.msi"

[Setup]
; AppId DEĞİŞTİRİLMEZ: yükseltme ve kaldırma bununla eşleşir
AppId={{F8CA7568-5553-4B2F-8E5C-5CA5B58E9354}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Osman Alpaslan
AppPublisherURL=https://github.com/osmanalpaslan/EVREN-Model-Studio
AppSupportURL=https://github.com/osmanalpaslan/EVREN-Model-Studio/issues
AppCopyright=Copyright (c) 2026 Osman Alpaslan (MIT)
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Kurulum
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
LicenseFile=..\LICENSE
SetupIconFile=..\assets\evren.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
AppMutex=EVREN.Studio
CloseApplications=yes
WizardStyle=modern
DisableWelcomePage=no
; Sihirbaz resimleri uygulama logosundan (tools/paketle.py üretir); yoksa Inno'nun kendi resmi görünür
#ifdef WizImage
WizardImageFile={#WizImage}
WizardSmallImageFile={#WizSmallImage}
#endif
Compression=lzma2/max
SolidCompression=yes
OutputDir={#OutDir}
OutputBaseFilename=EVREN-Studio-Kurulum-{#AppVersion}
ChangesEnvironment=yes
#ifdef SignToolName
SignTool={#SignToolName}
SignedUninstaller=yes
#endif

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
turkish.DevGroup=Gerekli programlar (bilgisayarınızda eksik olanlar — önerilir):
english.DevGroup=Required programs (missing on this computer — recommended):
turkish.PyTask=Python 3.12 — ajanın Python projeleri, Serena ve masaüstü kontrolü için
english.PyTask=Python 3.12 — for Python projects, Serena and desktop control
turkish.GitTask=Git — sürüm takibi, Proje ajanı kayıt noktaları, GitHub
english.GitTask=Git — version control, project checkpoints, GitHub
turkish.NodeTask=Node.js LTS — web QA testleri (Playwright), npm projeleri (yönetici izni ister)
english.NodeTask=Node.js LTS — web QA tests (Playwright), npm projects (asks for admin rights)
turkish.GhTask=GitHub CLI — GitHub menüsü (yönetici izni ister)
english.GhTask=GitHub CLI — GitHub menu (asks for admin rights)
turkish.Installing=%1 kuruluyor…
english.Installing=Installing %1…
turkish.DeleteData=Kişisel verileriniz de silinsin mi?%n%nOturumlar, ayarlar, ekler (%1) ve kayıtlı API anahtarları kalıcı olarak silinir.%n%n"Hayır" derseniz yeniden kurduğunuzda her şey yerinde olur.
english.DeleteData=Also delete your personal data?%n%nSessions, settings, attachments (%1) and saved API keys will be removed permanently.%n%nChoose "No" to keep them for a later reinstall.
turkish.PrereqFailed=%1 kurulamadı (çıkış kodu %2). EVREN Studio yine de kurulur; bu programı daha sonra uygulamanın Ayarlar > Eksik program kurulumu bölümünden kurabilirsiniz.
english.PrereqFailed=%1 could not be installed (exit code %2). EVREN Studio will still be installed; you can install it later from Settings.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "dev"; Description: "{cm:DevGroup}"; Check: AnyMissing
Name: "dev\python"; Description: "{cm:PyTask}"; Check: NeedPython
Name: "dev\git"; Description: "{cm:GitTask}"; Check: NeedGit
Name: "dev\node"; Description: "{cm:NodeTask}"; Check: NeedNode
Name: "dev\gh"; Description: "{cm:GhTask}"; Check: NeedGh

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PrereqDir}\{#PyFile}"; Flags: dontcopy
Source: "{#PrereqDir}\{#GitFile}"; Flags: dontcopy
Source: "{#PrereqDir}\{#NodeFile}"; Flags: dontcopy
Source: "{#PrereqDir}\{#GhFile}"; Flags: dontcopy

[InstallDelete]
; Eski sürümden kalan paket dosyaları (yeni sürümde olmayan Qt/Python parçaları) karışmasın; veri {app} DIŞINDA
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "EVREN.Studio"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon; AppUserModelID: "EVREN.Studio"

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  PathDirs: TStringList;

function ReadPath(Root: Integer; Key: String): String;
begin
  if not RegQueryStringValue(Root, Key, 'Path', Result) then
    Result := '';
end;

{ PATH'teki klasörler: bu sürecin PATH'i + kayıt defterindeki kullanıcı ve sistem PATH'i (kurulumdan hemen sonra da doğru) }
procedure LoadPath();
var
  All, Part: String;
  P: Integer;
begin
  PathDirs := TStringList.Create;
  All := GetEnv('PATH') + ';' + ReadPath(HKCU, 'Environment') + ';' +
         ReadPath(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment');
  while Length(All) > 0 do
  begin
    P := Pos(';', All);
    if P = 0 then P := Length(All) + 1;
    Part := Trim(Copy(All, 1, P - 1));
    Delete(All, 1, P);
    if Part <> '' then
      PathDirs.Add(ExpandConstant(Part));
  end;
end;

{ Windows'un Microsoft Store'u açan sahte python.exe'si (WindowsApps) gerçek kurulum SAYILMAZ }
function OnPath(ExeName: String; SkipStore: Boolean): Boolean;
var
  I: Integer;
  D: String;
begin
  Result := False;
  if PathDirs = nil then LoadPath();
  for I := 0 to PathDirs.Count - 1 do
  begin
    D := AddBackslash(PathDirs[I]);
    if SkipStore and (Pos('\MICROSOFT\WINDOWSAPPS\', Uppercase(D)) > 0) then
      Continue;
    if FileExists(D + ExeName) then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

function PythonRegistered(): Boolean;
var
  V: Integer;
begin
  Result := False;
  for V := 11 to 15 do
    if RegKeyExists(HKCU, 'Software\Python\PythonCore\3.' + IntToStr(V) + '\InstallPath') or
       RegKeyExists(HKLM64, 'Software\Python\PythonCore\3.' + IntToStr(V) + '\InstallPath') or
       RegKeyExists(HKLM32, 'Software\Python\PythonCore\3.' + IntToStr(V) + '\InstallPath') then
    begin
      Result := True;
      Exit;
    end;
end;

function NeedPython(): Boolean;
begin
  Result := not (PythonRegistered() or OnPath('python.exe', True));
end;

function NeedGit(): Boolean;
begin
  Result := not OnPath('git.exe', False);
end;

function NeedNode(): Boolean;
begin
  Result := not OnPath('node.exe', False);
end;

function NeedGh(): Boolean;
begin
  Result := not OnPath('gh.exe', False);
end;

function AnyMissing(): Boolean;
begin
  Result := NeedPython() or NeedGit() or NeedNode() or NeedGh();
end;

procedure RunPrereq(Title, FileName, Exe, Params: String);
var
  Code: Integer;
begin
  WizardForm.StatusLabel.Caption := FmtMessage(CustomMessage('Installing'), [Title]);
  ExtractTemporaryFile(FileName);
  if not Exec(Exe, Params, '', SW_SHOW, ewWaitUntilTerminated, Code) or ((Code <> 0) and (Code <> 3010)) then
    MsgBox(FmtMessage(CustomMessage('PrereqFailed'), [Title, IntToStr(Code)]), mbError, MB_OK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  T: String;
begin
  if CurStep <> ssPostInstall then Exit;
  T := ExpandConstant('{tmp}\');
  { Python ve Git kullanıcı kapsamında kurulur (yönetici izni İSTEMEZ); Node ve gh MSI'ları yalnız makine geneli
    kurulabilir → Windows yönetici izni penceresini gösterir }
  if WizardIsTaskSelected('dev\python') then
    RunPrereq('Python 3.12', '{#PyFile}', T + '{#PyFile}',
      '/passive InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=0 Shortcuts=0');
  { Include_launcher=0 (2026-11-07 Windows Sandbox temiz kurulum denemesi): "Python Launcher" adımı 14 dk takıldı, kurulum
    hiç bitmedi. py başlatıcısı gerekmiyor: uygulama Python'u PATH'teki `python` ile bulur (PrependPath=1). }
  if WizardIsTaskSelected('dev\git') then
    RunPrereq('Git', '{#GitFile}', T + '{#GitFile}',
      '/SILENT /NORESTART /NOCANCEL /SP- /SUPPRESSMSGBOXES /CURRENTUSER');
  if WizardIsTaskSelected('dev\node') then
    RunPrereq('Node.js LTS', '{#NodeFile}', 'msiexec.exe', '/i "' + T + '{#NodeFile}' + '" /passive /norestart');
  if WizardIsTaskSelected('dev\gh') then
    RunPrereq('GitHub CLI', '{#GhFile}', 'msiexec.exe', '/i "' + T + '{#GhFile}' + '" /passive /norestart');
end;

{ Kaldırma: kişisel veri ve Credential Manager'daki EVREN-Model-Studio anahtarları — yalnız kullanıcı "Evet" derse.
  Sessiz kaldırmada (/VERYSILENT) hiçbir şey silinmez. Anahtarları uygulamanın kendisi siler (--anahtarlari-sil:
  CredEnumerate/CredDelete; ağ geçidi anahtarları dahil) — bu yüzden dosyalar silinmeden ÖNCE (usUninstall). }
var
  DeleteUserData: Boolean;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  Code: Integer;
begin
  DataDir := ExpandConstant('{localappdata}\EVREN-Model-Studio');
  if CurUninstallStep = usUninstall then
  begin
    DeleteUserData := (not UninstallSilent()) and
      (MsgBox(FmtMessage(CustomMessage('DeleteData'), [DataDir]), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES);
    if DeleteUserData then
      Exec(ExpandConstant('{app}\{#AppExe}'), '--anahtarlari-sil', '', SW_HIDE, ewWaitUntilTerminated, Code);
  end;
  if (CurUninstallStep = usPostUninstall) and DeleteUserData then
    DelTree(DataDir, True, True, True);
end;
