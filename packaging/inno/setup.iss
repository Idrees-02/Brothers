; Inno Setup script for Brothers for Selling Carpet.
; Build (on Windows, after `pyinstaller packaging/brothers.spec` has produced
; dist/Brothers/):
;   iscc packaging/inno/setup.iss
; Output: packaging/inno/Output/BrothersSetup.exe

#define MyAppName "الإخوة لبيع السجاد"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Brothers for Selling Carpet"
#define MyAppExeName "Brothers.exe"

[Setup]
AppId={{B90D8B6B-6E1E-4B0E-9B7B-BROTHERSCARPET}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Brothers
DefaultGroupName=Brothers
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=BrothersSetup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\..\dist\Brothers\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "تشغيل البرنامج الآن"; Flags: nowait postinstall skipifsilent
