#ifndef VersionApp
  #define VersionApp "1.0.1"
#endif
#ifndef RaizProyecto
  #define RaizProyecto ".."
#endif

[Setup]
; AppId fijo para que cada compilacion actue como actualizacion sobre la instalacion existente
AppId={{A7E4C912-6D3F-4B8A-9C21-3E5F8A1D4B70}
AppName=PROCESOS_IA
AppVersion={#VersionApp}
AppVerName=PROCESOS_IA {#VersionApp}
AppPublisher=PROCESOS_IA
DefaultDirName={autopf}\PROCESOS_IA
DefaultGroupName=PROCESOS_IA
UsePreviousAppDir=yes
UsePreviousGroup=yes
CloseApplications=yes
RestartApplications=no
AllowNoIcons=yes
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
SetupIconFile={#RaizProyecto}\recursos\imagenes\icono-aplicacion.ico
UninstallDisplayIcon={app}\PROCESOS_IA.exe
OutputDir={#RaizProyecto}\dist\instaladores
OutputBaseFilename=PROCESOS_IA_Actualizacion_{#VersionApp}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Files]
Source: "{#RaizProyecto}\dist\PROCESOS_IA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PROCESOS_IA"; Filename: "{app}\PROCESOS_IA.exe"
Name: "{autodesktop}\PROCESOS_IA"; Filename: "{app}\PROCESOS_IA.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PROCESOS_IA.exe"; Description: "Ejecutar PROCESOS_IA"; Flags: nowait postinstall skipifsilent
