# Windows-Host einrichten (`deploy/windows/bootstrap.ps1`)

Der Stack ist für Linux geschrieben — auf einem Windows-Host läuft er in einer
WSL2-Distro. Dieses Dokument beschreibt den Bootstrap und **was am Betrieb
anders ist**; die Eigenheiten von WSL sind hier die eigentliche Fehlerquelle.

Der Linux-Weg (Ubuntu-Server) bleibt der Referenzweg: `./setup.sh` und
[`docs/production-setup.md`](production-setup.md). Dieses Dokument ergänzt ihn
nur.

## Voraussetzungen

| Punkt | Anforderung |
|---|---|
| Windows | 11, **Build 22621 (22H2) oder neuer** — ältere Builds haben kein mirrored networking |
| Rechte | PowerShell **als Administrator** |
| Virtualisierung | im BIOS/UEFI aktiv (VT-x / AMD-V) |
| Platz | ~30 GB auf `C:` (WSL-VHD + Images; der OHIF-Build braucht mehr) |
| Netz | Internet für den WSL-Download, die Docker-Pakete und den Clone |
| RAM | ab 8 GB. Weniger macht den OHIF-Viewer-Build unbrauchbar |

## Schnellstart

```powershell
# 1. nur prüfen (ändert nichts)
irm https://raw.githubusercontent.com/emanuel901z-hue/orthanc-dicommwl-broker/main/deploy/windows/bootstrap.ps1 `
    -OutFile bootstrap.ps1
powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 -Check

# 2. einrichten
powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1
```

Das Skript braucht **zwei Läufe**: Die WSL-Features erfordern einen Neustart.
Es sagt am Ende jedes Laufs, mit welcher Zeile es weitergeht; bereits erledigte
Phasen werden übersprungen, jede Phase ist idempotent.

## Parameter

| Parameter | Default | Wirkung |
|---|---|---|
| `-RepoUrl` / `-RepoRef` | Fork-URL / `main` | woher geklont wird |
| `-Distro` | `Ubuntu-24.04` | WSL-Distribution |
| `-WslUser` | Windows-Benutzer, bereinigt | Benutzer in der Distro (in der `docker`-Gruppe) |
| `-InstallPath` | `/opt/orthanc-dicommwl-broker` | Ziel **innerhalb** der Distro |
| `-WslVersion` | `3.0.3` | WSL-Runtime; `latest` löst über die GitHub-API auf |
| `-WslMemory` / `-WslProcessors` / `-WslSwap` | 60 % RAM (2–8 GB) / Kerne − 2 / `2GB` | Grenzen in `.wslconfig` |
| `-PortainerTag` | `2.45.2` | Portainer CE |
| `-Check` | — | nur prüfen, nichts ändern |
| `-SkipStack` | — | Umgebung vorbereiten, Stack nicht bauen/starten |
| `-NoUiAuth` / `-SkipPortainer` | — | Basic-Auth bzw. Portainer weglassen |
| `-AutoReboot` | — | beim nötigen Neustart nicht nachfragen |
| `-Reset` | — | Zustandsdatei löschen, alle Phasen erneut |

## Was der Bootstrap tut

| Phase | Inhalt |
|---|---|
| 1 `preflight` | Adminrechte, Windows-Build, Virtualisierung, Platz, Internet |
| 2 `features` | `Microsoft-Windows-Subsystem-Linux` + `VirtualMachinePlatform` → **Neustart** |
| 3 `wsl-runtime` | WSL als MSI von Microsofts GitHub-Releases |
| 4 `distro` | Ubuntu installieren (`--no-launch`), Benutzer + sudo + `systemd` + `/etc/wsl.conf` |
| 5 `wslconfig` | `%USERPROFILE%\.wslconfig`: mirrored networking, `hostAddressLoopback`, RAM/CPU |
| 6 `repo` | Repository klonen (Submodule auf dem Tag-Pin, ohne `--remote`) |
| 7 `provision` | `deploy/windows/wsl-provision.sh`: Docker Engine, klassischer Image-Store, `127.0.0.1`-Workaround |
| 8 `stack` | `.env` mit starkem Datenbank-Passwort, `./build.sh --health`, `./setup.sh --check` |
| 9 `ui-auth` | HTTP-Basic-Auth vor die Oberfläche (Benutzer `mwlbroker`) |
| 10 `portainer` | Portainer CE mit vorab gesetztem Admin-Passwort |
| 11 `summary` | Adressen, Passwortdateien, offene Punkte |

Warum diese Schritte nötig sind (jeder davon hat uns einmal Zeit gekostet):

- **WSL kommt als Store-App.** Der Schalter `Microsoft-Windows-Subsystem-Linux`
  allein aktiviert nur die alte Komponente; `wsl.exe` bleibt eine Attrappe.
  Über SSH ist der Store nicht benutzbar → MSI von GitHub.
- **Mirrored Networking + `hostAddressLoopback=true`** sind Pflicht. Ohne das
  ist der Stack weder aus dem LAN noch vom Windows-Desktop erreichbar.
- **Docker 29 nimmt den containerd-Snapshotter**, an dem BuildKit mit
  `failed to Lchown … libaom.so` scheitert. Der klassische `overlay2`-Store ist
  die Umgebung, in der der Stack gebaut und getestet wird.
- **Der `127.0.0.1`-Hang** (microsoft/WSL#10855) lässt jeden „läuft das
  schon?"-Test 130 s warten statt sofort abzulehnen; `setup.sh --check` bleibt
  an einem gestoppten Stack hängen. Der systemd-Service
  `wsl-127-route-fix.service` räumt die gespiegelte Route weg.

## Nach der Installation

```text
Oberfläche      http://<host-ip>:18082/oe3/      Benutzer mwlbroker
Portainer       https://<host-ip>:9443
DICOM           AET MWLBROKER, Port 11113   ← hierauf zeigen die Modalitäten
Orthanc DICOM   AET ORTHANC,   Port 14242
Broker-API      nur aus der Distro: http://127.0.0.1:18081/docs
OHIF-Viewer     http://<host-ip>:18082/ohif/viewer?StudyInstanceUIDs=<UID>
```

**Der Viewer braucht `?StudyInstanceUIDs=<UID>`.** Ohne den Parameter bleibt die
Seite leer — `showStudyList: false` in `deploy/ohif-config.js` schaltet die
eigene Studienliste des Viewers ab, weil die Studienliste in OE3 lebt. Wer den
Viewer direkt aufruft, muss die UID also mitgeben (mehrere komma-getrennt).
Der Weg über die Oberfläche — *Studien* → Studie → **In OHIF öffnen** — baut
genau diese URL selbst.

Die Viewer-Adresse erscheint nur, wenn der Viewer läuft (Profil `viewer`):

```bash
cd /opt/orthanc-dicommwl-broker
docker compose --profile viewer up -d --no-build ohif
```

`--no-build` nutzt ein vorhandenes Image; ohne die Option wird der Viewer neu
gebaut (5–20 min, speicherhungrig). Ein `docker compose up -d` **ohne** Profil
entfernt ihn nicht, ein `docker compose down` nimmt ihn aber mit.

Passwörter liegen in der Distro (root, 600):

```bash
wsl -d Ubuntu-24.04 -u root -- cat /opt/oe3-ui-password
wsl -d Ubuntu-24.04 -u root -- cat /opt/portainer/admin-password
```

Noch offen und bewusst manuell (in der Oberfläche): **AET-Whitelist**,
**Alarmierung** (Webhook; E-Mail braucht eine Brücke), optional **DICOM-TLS**.

## Betrieb auf Windows — die vier Regeln

**1. `localhost` erreicht die Distro nicht.**
In diesem Modus liegt der Listener „unterhalb" des Windows-TCP-Stacks. Immer die
**Host-IP** verwenden. Die per Default auf `127.0.0.1` gebundenen Dienste
(Broker-API 18081, Orthanc-REST 18042, OHIF 18083) erreicht man administrativ
nur über die Distro-Shell:

```powershell
wsl -d Ubuntu-24.04                      # danach: cd /opt/orthanc-dicommwl-broker
```

**2. Nach jeder Firewall-Änderung `wsl --shutdown`.**
Sonst bricht die Weiterleitung, bis die VM neu startet. Das gilt auch, wenn die
Firewall nur *aktiviert* wird.

**3. Die Hyper-V-Firewall für WSL nicht einschalten.**
`Set-NetFirewallProfile -Enabled True` aktiviert sie implizit mit. In diesem
Build blockt sie dann **jeden** WSL-Inbound — auch explizit erlaubte Ports
(mit `RemoteAddresses Any`, expliziter VMCreatorId und Default-Allow geprüft).
Die Windows-Firewall filtert WSL-Traffic umgekehrt überhaupt nicht. Wer das
zurückdrehen muss:

```powershell
Set-NetFirewallHyperVVMSetting -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -Enabled False
wsl --shutdown
```

**4. Die Stack-Ports lassen sich von Windows aus nicht filtern.**
Deshalb liegt der Schutz im Stack selbst: **Basic-Auth** vor der Oberfläche
(Phase 9), **AET-Whitelist** und **DICOM-TLS** für die DICOM-Ports. Für eine
grobe Netzbegrenzung bleibt nur die Netzwerkseite (Switch-ACL / eigenes VLAN).

## Portainer

Portainer CE deckt den Docker-Teil ab: Container, Images, Volumes, Netze,
Logs, Konsole, Compose-Stacks, Registry-Anbindung. Es ist der einzige Zugang mit
root-äquivalenten Rechten — deshalb Passwort vorab gesetzt (sonst könnte sich
der erste Besucher als Admin registrieren) und der Port nicht ins offene
Internet stellen.

Was Portainer **nicht** kann — dafür in die Distro-Shell:

```bash
cd /opt/orthanc-dicommwl-broker

./setup.sh --check          # was ist konfiguriert, was fehlt (ändert nichts)
./setup.sh                  # Betriebseinstellungen setzen (interaktiv)
./build.sh --health         # bauen, starten, auf „healthy" warten
./build.sh --logs mwl-broker
./build.sh --down           # stoppen (--volumes löscht Daten!)
./deploy/backup.sh --dir /mnt/backup --keep 30
```

Update auf eine neue Version (der Pin bleibt auf dem Release-Tag):

```bash
cd /opt/orthanc-dicommwl-broker
git pull --ff-only
git submodule update --init      # ohne --remote, sonst reißt der Tag-Pin
./deploy/backup.sh
./build.sh --health
./setup.sh --check
```

## Bekannte Grenzen

- **Kein Windows-Firewall-Filter für WSL** (siehe Regel 4).
- **OHIF-Viewer** wird nicht mitgebaut (5–20 min, speicherhungrig). Auf einem
  Host mit 8 GB ist davon abzuraten; das Image lässt sich von einem Build-Host
  per `docker save`/`docker load` übertragen.
- **WSL2-VHD wächst** und gibt Platz nicht von selbst zurück. Bei Bedarf
  `wsl --shutdown` und die `ext4.vhdx` komprimieren.
- **Der erste Start baut die Images** — der OE3-Build (npm/vite) dauert auf
  einem kleinen Host spürbar lange.
- **Ein Windows-Neustart** bringt WSL und damit den Stack mit zurück; die
  Container haben `restart: unless-stopped`.

## Zurücksetzen

```powershell
# Phasen erneut durchlaufen lassen (idempotent)
powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 -Reset

# Zustandsdatei ansehen
Get-Content "$env:ProgramData\mwl-broker-bootstrap\state.txt"

# Distro komplett entfernen (löscht auch alle Stack-Daten!)
wsl --unregister Ubuntu-24.04
```
