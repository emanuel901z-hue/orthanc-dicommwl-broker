<#
.SYNOPSIS
    Bootstrap a Windows host for the mwl-broker Docker stack.

.DESCRIPTION
    Prepares Windows 11 for WSL2 (mirrored networking), installs Docker Engine
    inside an Ubuntu distro, clones this repository, builds and starts the
    stack, protects the OE3 UI with HTTP Basic auth and installs Portainer.

    The script is phase driven and records what it has done in
        %ProgramData%\mwl-broker-bootstrap\state.txt
    Enabling the WSL features needs a reboot; after that just run the script
    again — completed phases are skipped and it continues where it stopped.
    Every phase is idempotent, so re-running it is always safe.

.PARAMETER Check
    Only inspect the host and print the plan. Changes nothing.

.PARAMETER SkipStack
    Prepare Windows and WSL, but do not build or start the stack.

.PARAMETER NoUiAuth
    Do not put HTTP Basic auth in front of the OE3 UI.

.PARAMETER SkipPortainer
    Do not install Portainer.

.PARAMETER NoViewer
    Do not put the OHIF viewer into the base stack. By default the bootstrap
    sets COMPOSE_PROFILES=viewer, so ./build.sh builds and starts it — that
    adds 5-20 minutes (and a lot of RAM) to the first build.

.PARAMETER AutoReboot
    Reboot without asking when the WSL features require it.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 -Check

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1
#>
[CmdletBinding()]
param(
    [string] $RepoUrl      = 'https://github.com/emanuel901z-hue/orthanc-dicommwl-broker.git',
    [string] $RepoRef      = 'main',
    [string] $Distro       = 'Ubuntu-24.04',
    [string] $WslUser      = '',
    [string] $InstallPath  = '/opt/orthanc-dicommwl-broker',
    [string] $WslVersion   = '3.0.3',
    [string] $WslMemory    = '',
    [int]    $WslProcessors = 0,
    [string] $WslSwap      = '2GB',
    [string] $PortainerTag = '2.45.2',
    [switch] $Check,
    [switch] $SkipStack,
    [switch] $NoUiAuth,
    [switch] $SkipPortainer,
    [switch] $NoViewer,
    [switch] $AutoReboot,
    [switch] $Reset
)

$ErrorActionPreference = 'Stop'

# ── Ausgabe ──────────────────────────────────────────────────────────────────
function Write-Step { param([string] $Text) Write-Host ''; Write-Host "==> $Text" -ForegroundColor Cyan }
function Write-Ok   { param([string] $Text) Write-Host "  [ok] $Text" -ForegroundColor Green }
function Write-Note { param([string] $Text) Write-Host "       $Text" }
function Write-Warn { param([string] $Text) Write-Host "  [!!] $Text" -ForegroundColor Yellow }
function Write-Fail { param([string] $Text) Write-Host "  [xx] $Text" -ForegroundColor Red }

# ── Zustand ──────────────────────────────────────────────────────────────────
$StateDir  = Join-Path $env:ProgramData 'mwl-broker-bootstrap'
$StateFile = Join-Path $StateDir 'state.txt'

function Get-DonePhases {
    if (-not (Test-Path $StateFile)) { return @() }
    return @(Get-Content $StateFile | Where-Object { $_ -like 'done=*' } | ForEach-Object { $_.Substring(5) })
}
function Test-PhaseDone { param([string] $Name) return ((Get-DonePhases) -contains $Name) }
function Set-PhaseDone {
    param([string] $Name)
    if (-not (Test-Path $StateDir)) { New-Item -ItemType Directory -Path $StateDir -Force | Out-Null }
    if (-not (Test-PhaseDone $Name)) { Add-Content -Path $StateFile -Value "done=$Name" -Encoding ASCII }
}

# ── Hilfsfunktionen ──────────────────────────────────────────────────────────
function Test-Admin {
    return ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-TcpPort {
    param([string] $Target, [int] $Port, [int] $TimeoutMs = 4000)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect($Target, $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne($TimeoutMs)
        if ($ok) { $client.EndConnect($iar) }
        $client.Close()
        return $ok
    } catch { return $false }
}

function New-Password {
    param([int] $Length = 24)
    $alphabet = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    $bytes = New-Object byte[] $Length
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return (-join ($bytes | ForEach-Object { $alphabet[$_ % $alphabet.Length] }))
}

function Get-LogicalProcessors {
    $sum = (Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum
    if (-not $sum) { return 4 }
    return [int] $sum
}

# WSL-Kommandos laufen als base64-kodiertes Bash-Skript: so bleibt die
# Quotierung zwischen PowerShell, wsl.exe und bash eindeutig.
function Invoke-WslCapture {
    param([string] $Script, [string] $User = 'root', [switch] $AllowFail)
    $b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Script))
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out  = & wsl.exe -d $Distro -u $User -- bash -c "echo $b64 | base64 -d | bash" 2>&1 | ForEach-Object { "$_" }
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
    if ($code -ne 0 -and -not $AllowFail) {
        throw "WSL-Kommando fehlgeschlagen (ExitCode $code):`n$($out -join "`n")"
    }
    return @{ Output = $out; Code = $code }
}

function Invoke-WslStream {
    param([string] $Script, [string] $User = 'root', [switch] $AllowFail)
    $b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Script))
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & wsl.exe -d $Distro -u $User -- bash -c "echo $b64 | base64 -d | bash"
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
    if ($code -ne 0 -and -not $AllowFail) {
        throw "WSL-Kommando fehlgeschlagen (ExitCode $code)"
    }
}

function Get-WslDistros {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { return @() }
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & wsl.exe -l -q 2>&1
    } finally { $ErrorActionPreference = $previous }
    if ($LASTEXITCODE -ne 0) { return @() }
    return @($out | ForEach-Object { ("$_" -replace "`0", '').Trim() } | Where-Object { $_ })
}

function Test-WslRuntime {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { return $false }
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out  = & wsl.exe --version 2>&1 | ForEach-Object { "$_" }
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
    return ($code -eq 0 -and (($out -join ' ') -match 'WSL[- ]Version|WSL-Version'))
}

function Write-TextFile {
    param([string] $Path, [string] $Content)
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    [IO.File]::WriteAllText($Path, $Content, (New-Object Text.UTF8Encoding($false)))
}

# ── Standardwerte, abhängig vom Host ─────────────────────────────────────────
$LogicalCpu = Get-LogicalProcessors
$RamGB      = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
if (-not $WslProcessors) { $WslProcessors = [math]::Max(1, [math]::Min(8, $LogicalCpu - 2)) }
if (-not $WslMemory)     { $WslMemory = ('{0}GB' -f [math]::Max(2, [math]::Min(8, [math]::Round($RamGB * 0.6)))) }
if (-not $WslUser) {
    $WslUser = ($env:USERNAME.ToLowerInvariant() -replace '[^a-z0-9_-]', '')
    if (-not $WslUser) { $WslUser = 'admin' }
    if ($WslUser -notmatch '^[a-z_]') { $WslUser = "u$WslUser" }
}

$RerunCommand = "powershell -ExecutionPolicy Bypass -File `"$PSCommandPath`" " +
    "-RepoUrl `"$RepoUrl`" -RepoRef `"$RepoRef`" -Distro `"$Distro`" -WslUser `"$WslUser`" " +
    "-InstallPath `"$InstallPath`""

# ── Phasen ───────────────────────────────────────────────────────────────────

function Phase-Preflight {
    Write-Step '1/12  Umgebung prüfen'

    if (-not (Test-Admin)) { throw 'Bitte in einer PowerShell mit Administratorrechten ausführen.' }
    Write-Ok 'Administratorrechte vorhanden'

    $key   = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
    $build = [int] $key.CurrentBuildNumber
    Write-Ok "Windows $($key.DisplayVersion) (Build $build)"
    if ($build -lt 22621) {
        throw "Windows 11 22H2 (Build 22621) oder neuer ist nötig — ältere Builds haben kein mirrored networking."
    }

    # Once Hyper-V (or WSL) runs, VirtualizationFirmwareEnabled reports False —
    # the hypervisor owns VT-x. So an already running hypervisor is just as good.
    $hypervisor = (Get-CimInstance Win32_ComputerSystem).HypervisorPresent
    $vt = (Get-CimInstance Win32_Processor | Select-Object -First 1).VirtualizationFirmwareEnabled
    if ($hypervisor) {
        Write-Ok 'Hypervisor läuft (Hyper-V/WSL) — Virtualisierung nutzbar'
    } elseif ($vt) {
        Write-Ok 'Virtualisierung in der Firmware aktiv'
    } else {
        throw 'Virtualisierung ist im BIOS/UEFI nicht aktiviert (VT-x / AMD-V).'
    }

    $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
    $freeGB = [math]::Round($disk.FreeSpace / 1GB, 1)
    if ($freeGB -lt 30) { throw "Zu wenig Platz auf C: ($freeGB GB frei, mindestens 30 GB nötig)." }
    Write-Ok "C: hat $freeGB GB frei"

    Write-Ok "Host: $LogicalCpu logische Kerne, $RamGB GB RAM"
    Write-Note "WSL bekommt: $WslMemory RAM, $WslProcessors Kerne, $WslSwap Swap"
    if ($RamGB -le 8) {
        Write-Warn "Wenig RAM — der OHIF-Viewer-Build ist auf diesem Host nicht zu empfehlen."
    }

    foreach ($target in 'github.com', 'download.docker.com', 'aka.ms') {
        if (Test-TcpPort -Target $target -Port 443) { Write-Ok "$target erreichbar" }
        else { Write-Warn "$target nicht erreichbar — Klonen, WSL-Download und Docker-Installation brauchen Internet" }
    }

    if ($Check) { return }
    if ((Get-DonePhases).Count -gt 0) {
        Write-Note "Bereits erledigt: $((Get-DonePhases) -join ', ')"
    }
}

function Phase-Features {
    Write-Step '2/12  WSL-Features aktivieren'

    $changed = $false
    foreach ($feature in 'Microsoft-Windows-Subsystem-Linux', 'VirtualMachinePlatform') {
        $state = (Get-WindowsOptionalFeature -Online -FeatureName $feature).State
        if ($state -eq 'Enabled') { Write-Ok "$feature ist bereits aktiv"; continue }

        Write-Note "aktiviere $feature …"
        $p = Start-Process dism.exe -Wait -PassThru -NoNewWindow -ArgumentList @(
            '/online', '/enable-feature', "/featurename:$feature", '/all', '/norestart'
        )
        if ($p.ExitCode -notin 0, 3010) { throw "dism $feature fehlgeschlagen (ExitCode $($p.ExitCode))" }
        $changed = $true
    }

    if ($changed) {
        Write-Warn 'Für die neuen Features ist ein Neustart nötig.'
        Write-Note "Danach dieses Skript erneut ausführen:"
        Write-Note "  $RerunCommand"
        $script:RestartRequired = $true
        return
    }
    Write-Ok 'WSL-Features sind aktiv'
}

function Phase-WslRuntime {
    Write-Step '3/12  WSL-Laufzeit installieren'

    if (Test-WslRuntime) {
        $previous = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try { $version = (& wsl.exe --version 2>&1 | Select-Object -First 1) } finally { $ErrorActionPreference = $previous }
        Write-Ok "WSL ist installiert ($version)"
        return
    }

    # Windows 11 ships only a stub: enabling the optional feature is not enough,
    # the runtime is a separate package. Over SSH the Store is not usable, so we
    # install Microsoft's signed MSI from GitHub releases.
    $version = $WslVersion
    if ($version -eq 'latest') {
        Write-Note 'ermittle die aktuelle WSL-Version …'
        $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/microsoft/WSL/releases/latest' -UseBasicParsing
        $version = $release.tag_name
    }
    $msiUrl = "https://github.com/microsoft/WSL/releases/download/$version/wsl.$version.0.x64.msi"
    $msi    = Join-Path $env:TEMP "wsl-$version.msi"

    Write-Note "lade $msiUrl"
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & curl.exe -L --fail --silent --show-error -o $msi $msiUrl
        $curlCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
    if ($curlCode -ne 0 -or -not (Test-Path $msi)) { throw "Download fehlgeschlagen: $msiUrl" }
    Write-Ok ("MSI geladen ({0} MB)" -f [math]::Round((Get-Item $msi).Length / 1MB, 1))

    Write-Note 'installiere still …'
    $p = Start-Process msiexec.exe -Wait -PassThru -NoNewWindow -ArgumentList @('/i', "`"$msi`"", '/qn', '/norestart')
    if ($p.ExitCode -notin 0, 3010) { throw "msiexec fehlgeschlagen (ExitCode $($p.ExitCode))" }
    Remove-Item $msi -Force -ErrorAction SilentlyContinue

    if (-not (Test-WslRuntime)) { throw 'WSL meldet sich nach der Installation weiterhin nicht.' }
    Write-Ok "WSL $version installiert"
}

function Phase-Distro {
    Write-Step '4/12  Ubuntu-Distribution einrichten'

    if (Get-WslDistros | Where-Object { $_ -eq $Distro }) {
        Write-Ok "$Distro ist bereits installiert"
    } else {
        Write-Note "installiere $Distro (ohne Start, damit keine interaktive Abfrage kommt) …"
        $previous = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try { & wsl.exe --install -d $Distro --no-launch; $code = $LASTEXITCODE } finally { $ErrorActionPreference = $previous }
        if ($code -ne 0) { throw "Installation von $Distro fehlgeschlagen (ExitCode $code)" }
        Write-Ok "$Distro installiert"
    }

    # Benutzer, sudo und wsl.conf — idempotent, läuft als root in der Distro.
    $script = @"
set -e
U='$WslUser'
if ! id "`$U" >/dev/null 2>&1; then
  if getent group "`$U" >/dev/null 2>&1; then
    useradd -m -s /bin/bash -g "`$U" -G sudo "`$U"
  else
    useradd -m -s /bin/bash -G sudo "`$U"
  fi
  echo "  Benutzer `$U angelegt"
else
  echo "  Benutzer `$U existiert bereits"
fi
echo "`$U ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-`$U
chmod 440 /etc/sudoers.d/90-`$U
touch /etc/wsl.conf
grep -q '^\[boot\]'      /etc/wsl.conf || printf '[boot]\nsystemd=true\n\n' >> /etc/wsl.conf
grep -q '^systemd=true'  /etc/wsl.conf || sed -i '/^\[boot\]/a systemd=true' /etc/wsl.conf
grep -q '^\[user\]'      /etc/wsl.conf || printf '[user]\ndefault=%s\n\n' "`$U" >> /etc/wsl.conf
grep -q '^\[interop\]'   /etc/wsl.conf || printf '[interop]\nenabled=true\nappendWindowsPath=true\n' >> /etc/wsl.conf
echo "  --- /etc/wsl.conf ---"
cat /etc/wsl.conf
echo "  --- Benutzer ---"
id "`$U"
"@
    $result = Invoke-WslCapture -Script $script -User 'root'
    $result.Output | ForEach-Object { Write-Note $_ }
    Write-Ok "$Distro eingerichtet (systemd, Benutzer $WslUser, sudo)"
}

function Phase-WslConfig {
    Write-Step '5/12  WSL-Konfiguration (.wslconfig)'

    # Mirrored networking is what makes the published ports reachable from the
    # LAN *and* from the Windows desktop; hostAddressLoopback is required for
    # the latter. Without it the stack is only reachable from inside the VM.
    $content = @"
[wsl2]
memory=$WslMemory
processors=$WslProcessors
swap=$WslSwap
networkingMode=mirrored

[experimental]
hostAddressLoopback=true
"@
    $path = Join-Path $env:USERPROFILE '.wslconfig'
    $current = if (Test-Path $path) { [IO.File]::ReadAllText($path) } else { '' }

    if ($current.Trim() -eq $content.Trim()) {
        Write-Ok '.wslconfig ist bereits aktuell'
    } else {
        if ($current) {
            $backup = "$path.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
            Copy-Item $path $backup -Force
            Write-Warn "vorhandene .wslconfig gesichert nach $backup"
        }
        Write-TextFile -Path $path -Content $content
        Write-Ok "geschrieben: $path"
        Write-Note $content.Trim()
    }

    # The networking mode is read when the VM boots.
    Write-Note 'starte WSL neu, damit die Konfiguration greift …'
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & wsl.exe --shutdown; Start-Sleep -Seconds 3 } finally { $ErrorActionPreference = $previous }
    Write-Ok 'WSL neu gestartet'
}

function Phase-Repo {
    Write-Step '6/12  Repository klonen'

    $parent = ($InstallPath -replace '/[^/]+$', '')
    Invoke-WslCapture -User 'root' -Script "mkdir -p '$parent' && chown $WslUser '$parent'" | Out-Null

    $exists = (Invoke-WslCapture -User $WslUser -AllowFail -Script "test -d '$InstallPath/.git' && echo yes || echo no").Output -join ''
    if ($exists.Trim() -eq 'yes') {
        Write-Note 'Repository vorhanden — hole Änderungen, Pin bleibt gesetzt …'
        Invoke-WslStream -User $WslUser -Script @"
set -e
cd '$InstallPath'
git fetch --quiet origin '$RepoRef'
git checkout --quiet '$RepoRef'
git pull --quiet --ff-only origin '$RepoRef'
git submodule update --init --recursive --quiet
git log --oneline -1
git submodule status
"@
        Write-Ok 'Repository aktualisiert (ohne --remote, der Tag-Pin bleibt)'
    } else {
        Write-Note "klone $RepoUrl ($RepoRef) nach $InstallPath …"
        Invoke-WslStream -User $WslUser -Script @"
set -e
git clone --quiet --recurse-submodules --branch '$RepoRef' '$RepoUrl' '$InstallPath'
cd '$InstallPath'
git config --global --add safe.directory '$InstallPath' 2>/dev/null || true
git config --global --add safe.directory '$InstallPath/orthanc-explorer-3-usable' 2>/dev/null || true
git log --oneline -1
git submodule status
"@
        Write-Ok 'Repository geklont'
    }
}

function Phase-Provision {
    Write-Step '7/12  Docker und Workarounds in WSL einrichten'

    $script = @"
set -e
export MWL_DISTRO_USER='$WslUser'
bash '$InstallPath/deploy/windows/wsl-provision.sh'
"@
    Invoke-WslStream -User 'root' -Script $script
    Write-Ok 'WSL ist provisioniert'
}

function Phase-Stack {
    Write-Step '8/12  Stack bauen und starten'

    # A fresh clone only has .env.example. Replace the dev password *before*
    # the first start: the Postgres volume is initialised with it.
    $password = New-Password
    $viewerFlag = if ($NoViewer) { '0' } else { '1' }
    $script = @"
set -e
cd '$InstallPath'
[ -f .env ] || cp .env.example .env
chmod 600 .env
if grep -q '^POSTGRES_PASSWORD=dev$' .env; then
  sed -i 's|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$password|' .env
  echo '  Datenbank-Passwort gesetzt'
else
  echo '  Datenbank-Passwort war schon gesetzt'
fi
if [ '$viewerFlag' = '1' ]; then
  if grep -q '^COMPOSE_PROFILES=' .env; then
    sed -i 's|^COMPOSE_PROFILES=.*|COMPOSE_PROFILES=viewer|' .env
  else
    printf '\nCOMPOSE_PROFILES=viewer\n' >> .env
  fi
  echo '  OHIF-Viewer läuft mit (COMPOSE_PROFILES=viewer)'
fi
"@
    Invoke-WslCapture -User $WslUser -Script $script | Out-Null
    Write-Ok 'Konfiguration vorbereitet (.env, starkes Datenbank-Passwort)'

    Write-Note 'baue die Images und starte den Stack — beim ersten Mal dauert das (OE3- und ggf. OHIF-Build) …'
    Invoke-WslStream -User $WslUser -Script "cd '$InstallPath' && ./build.sh --health"

    Write-Note 'Konfigurations-Check …'
    Invoke-WslStream -User $WslUser -AllowFail -Script "cd '$InstallPath' && ./setup.sh --check"
    Write-Ok 'Stack läuft'
}

function Phase-UiAuth {
    Write-Step '9/12  Oberfläche mit Passwort schützen'

    $password = New-Password
    $script = @"
set -e
cd '$InstallPath'
if [ -s /opt/oe3-ui-password ]; then
  PW="`$(cat /opt/oe3-ui-password)"
else
  printf '%s' '$password' > /opt/oe3-ui-password
  chmod 600 /opt/oe3-ui-password
  PW='$password'
fi
[ -s /opt/oe3-ui-password ] || { echo 'FEHLER: Passwort für die Oberfläche ist leer'; exit 1; }
mkdir -p deploy/nginx-auth
printf 'mwlbroker:%s\n' "`$(openssl passwd -apr1 "`$PW")" > deploy/nginx-auth/.htpasswd
chmod 644 deploy/nginx-auth/.htpasswd
chown '$WslUser' deploy/nginx-auth/.htpasswd
grep -vE '^#' deploy/nginx-auth/auth.conf.example | grep -vE '^`$' > deploy/nginx-auth/auth.conf
chown '$WslUser' deploy/nginx-auth/auth.conf
docker compose up -d --no-build oe3
"@
    Invoke-WslStream -User 'root' -Script $script
    Write-Ok 'Basic-Auth aktiv (Benutzer mwlbroker)'
    Write-Note 'Passwort: /opt/oe3-ui-password in der WSL-Distro'
}

function Phase-Portainer {
    Write-Step '10/12  Portainer bereitstellen'

    $password = New-Password
    $script = @"
set -e
docker volume inspect portainer_data >/dev/null 2>&1 || docker volume create portainer_data >/dev/null
install -d -m 700 /opt/portainer
if [ ! -s /opt/portainer/admin-password ]; then
  printf '%s' '$password' > /opt/portainer/admin-password
  chmod 600 /opt/portainer/admin-password
fi
[ -s /opt/portainer/admin-password ] || { echo 'FEHLER: Portainer-Passwort ist leer'; exit 1; }
docker rm -f portainer >/dev/null 2>&1 || true
docker run -d --name portainer --restart=always \
  -p 9443:9443 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v portainer_data:/data \
  -v /opt/portainer/admin-password:/run/secrets/portainer-admin:ro \
  portainer/portainer-ce:$PortainerTag --admin-password-file=/run/secrets/portainer-admin >/dev/null
sleep 8
docker ps --filter name=portainer --format '{{.Names}} {{.Status}}'
"@
    Invoke-WslStream -User 'root' -Script $script
    Write-Ok 'Portainer läuft auf Port 9443'
    Write-Note 'Passwort: /opt/portainer/admin-password in der WSL-Distro'
}

function Phase-KeepAlive {
    Write-Step '11/12  Stack am Leben halten'

    $action = New-ScheduledTaskAction -Execute 'wsl.exe' -Argument "-d $Distro -u root -- tail -f /dev/null"
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId "$env:COMPUTERNAME\$env:USERNAME" `
        -LogonType Interactive -RunLevel Highest

    Register-ScheduledTask -TaskName 'MWL-Broker-KeepAlive' -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force | Out-Null
    Start-ScheduledTask -TaskName 'MWL-Broker-KeepAlive'
    Start-Sleep -Seconds 6

    if (Get-Process wsl -ErrorAction SilentlyContinue) {
        Write-Ok 'Keep-Alive läuft (offene WSL-Sitzung)'
    } else {
        Write-Warn 'Keep-Alive startete nicht — Get-ScheduledTask MWL-Broker-KeepAlive prüfen'
    }
    Write-Note 'WSL2 hält den Stack nur bei offener Sitzung; die Aufgabe startet ab der Anmeldung.'
    Write-Note 'Nach einem Neustart ist der Stack also erst nach dem Login wieder da.'
}

function Phase-Summary {
    Write-Step '12/12  Zusammenfassung'

    $script = @"
cd '$InstallPath' 2>/dev/null || exit 0
echo '--- Container ---'
docker compose ps --format '{{.Service}}  {{.Status}}' 2>/dev/null
echo
echo '--- Adressen ---'
grep -E '^(OE3_PORT|BROKER_DICOM_PORT|BROKER_AET|ORTHANC_DICOM_PORT|ORTHANC_AET)=' .env 2>/dev/null
"@
    $result = Invoke-WslCapture -User $WslUser -AllowFail -Script $script
    $result.Output | ForEach-Object { Write-Note $_ }

    $ip = (Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254*' -and $_.PrefixOrigin -ne 'WellKnown' } |
        Sort-Object -Property SkipAsSource | Select-Object -First 1).IPAddress
    if (-not $ip) { $ip = '<host-ip>' }

    Write-Host ''
    Write-Host '  Adressen' -ForegroundColor Cyan
    Write-Note "Oberfläche      http://${ip}:18082/oe3/      (Benutzer mwlbroker)"
    Write-Note "Portainer       https://${ip}:9443"
    Write-Note "DICOM           AET MWLBROKER, Port 11113 — hierauf zeigen die Modalitäten"
    Write-Note "Orthanc DICOM   AET ORTHANC,   Port 14242"
    Write-Note "Broker-API      nur aus der WSL-Shell: http://127.0.0.1:18081/docs"
    Write-Note "OHIF-Viewer     http://${ip}:18082/ohif/viewer?StudyInstanceUIDs=<UID>"
    Write-Note "                (ohne die UID bleibt der Viewer leer — showStudyList ist aus)"

    Write-Host ''
    Write-Host '  Noch offen (in der Oberfläche)' -ForegroundColor Cyan
    Write-Note 'AET-Whitelist    Übersicht → Konfigurations-Check, sonst darf jedes Gerät zugreifen'
    Write-Note 'Alarmierung      Einstellungen → Webhook (Slack/Teams-kompatibel; E-Mail braucht eine Brücke)'
    Write-Note 'DICOM-TLS        optional, sobald die Modalitäten es unterstützen'
    Write-Note 'Passwörter       /opt/oe3-ui-password und /opt/portainer/admin-password in der Distro'

    Write-Host ''
    Write-Host '  Wichtig für den Betrieb' -ForegroundColor Cyan
    Write-Note 'Windows-"localhost" erreicht WSL nicht — immer die Host-IP verwenden.'
    Write-Note 'Nach jeder Änderung an der Windows- oder Hyper-V-Firewall: wsl --shutdown.'
    Write-Note 'Die Hyper-V-Firewall für WSL nicht aktivieren — sie blockt alles, auch erlaubte Ports.'
    Write-Note 'Shell in der Distro:  wsl -d Ubuntu-24.04     (danach: cd /opt/orthanc-dicommwl-broker)'
}

$PhaseTable = @(
    @{ Name = 'preflight';   Run = { Phase-Preflight } },
    @{ Name = 'features';    Run = { Phase-Features } },
    @{ Name = 'wsl-runtime'; Run = { Phase-WslRuntime } },
    @{ Name = 'distro';      Run = { Phase-Distro } },
    @{ Name = 'wslconfig';   Run = { Phase-WslConfig } },
    @{ Name = 'repo';        Run = { Phase-Repo } },
    @{ Name = 'provision';   Run = { Phase-Provision } },
    @{ Name = 'stack';       Run = { Phase-Stack } },
    @{ Name = 'ui-auth';     Run = { Phase-UiAuth } },
    @{ Name = 'portainer';   Run = { Phase-Portainer } },
    @{ Name = 'keep-alive';  Run = { Phase-KeepAlive } },
    @{ Name = 'summary';     Run = { Phase-Summary } }
)

# ── Ablauf ───────────────────────────────────────────────────────────────────
Write-Host ''
Write-Host '  mwl-broker — Windows-Bootstrap' -ForegroundColor White
Write-Host '  ─────────────────────────────────────────────────────────────'
Write-Note "Distro:      $Distro"
Write-Note "Ziel:        $InstallPath"
Write-Note "Repository:  $RepoUrl ($RepoRef)"
if ($Check) { Write-Note 'Modus:       nur prüfen (-Check) — es wird nichts geändert' }

# -Check prüft nur: es läuft ausschließlich die Vorprüfung und es wird
# ausdrücklich kein Zustand geschrieben (sonst wäre die Prüfung beim zweiten
# Aufruf „schon erledigt" und würde nichts mehr anzeigen).
if ($Check) {
    Phase-Preflight
    Write-Host ''
    Write-Ok 'Prüfung abgeschlossen — nichts geändert.'
    Write-Note 'Ohne -Check einrichten:'
    Write-Note "  $RerunCommand"
    return
}

if ($Reset -and (Test-Path $StateFile)) {
    Remove-Item $StateFile -Force
    Write-Warn 'Zustand zurückgesetzt — alle Phasen laufen erneut (idempotent).'
}

$script:RestartRequired = $false
foreach ($phase in $PhaseTable) {
    if (Test-PhaseDone $phase.Name) {
        Write-Note "übersprungen (bereits erledigt): $($phase.Name)"
        continue
    }
    if ($SkipStack -and $phase.Name -in @('stack', 'ui-auth')) {
        Write-Note "übersprungen (-SkipStack): $($phase.Name)"
        continue
    }
    if ($NoUiAuth -and $phase.Name -eq 'ui-auth') {
        Write-Note 'übersprungen (-NoUiAuth)'
        continue
    }
    if ($SkipPortainer -and $phase.Name -eq 'portainer') {
        Write-Note 'übersprungen (-SkipPortainer)'
        continue
    }

    & $phase.Run

    if ($script:RestartRequired) {
        Write-Host ''
        if ($AutoReboot) {
            Write-Warn 'starte den Host neu …'
            Start-Process shutdown.exe -ArgumentList @('/r', '/t', '10', '/f', '/c', 'mwl-broker Bootstrap: Neustart für WSL2')
        } else {
            Write-Warn 'Neustart erforderlich. Danach das Skript erneut ausführen:'
            Write-Note "  $RerunCommand"
            Write-Host ''
            $answer = Read-Host '  Jetzt neu starten? [j/N]'
            if ($answer -match '^[jJyY]') {
                Start-Process shutdown.exe -ArgumentList @('/r', '/t', '10', '/f', '/c', 'mwl-broker Bootstrap: Neustart für WSL2')
            }
        }
        return
    }

    Set-PhaseDone $phase.Name
}

Write-Host ''
Write-Ok 'Fertig.'
