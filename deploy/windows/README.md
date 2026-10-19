# Windows-Bootstrap

`bootstrap.ps1` richtet einen Windows-11-Host für diesen Stack ein: WSL2 mit
mirrored networking, Docker Engine in einer Ubuntu-Distro, Repository, Stack,
Basic-Auth vor der Oberfläche und Portainer.

```powershell
# als Administrator
powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 -Check   # nur prüfen
powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1         # einrichten
```

Es sind **zwei Läufe** nötig: das Aktivieren der WSL-Features erfordert einen
Neustart, danach macht das Skript weiter, wo es aufgehört hat.

`wsl-provision.sh` ist der Teil, der **innerhalb** der Distro läuft
(Docker, klassischer Image-Store, `127.0.0.1`-Workaround). Er wird vom Bootstrap
aufgerufen und ist eigenständig idempotent.

Vollständige Anleitung inklusive der Betriebsbesonderheiten von WSL
(`localhost`, Firewall, Portainer-Grenzen): **[`docs/windows-host.md`](../../docs/windows-host.md)**.
