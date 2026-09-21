# Produktiv-Inbetriebnahme (`./setup.sh`)

Der geführte Bootstrap für den ersten echten Start. Er prüft die Umgebung,
füllt fehlende oder schlechte Werte, startet den Stack und richtet die
Betriebseinstellungen ein — mit Sicherheitsnetz, damit nichts versehentlich
kaputtgeht.

```bash
./setup.sh                 # geführte Einrichtung (interaktiv)
./setup.sh --check         # nur prüfen und berichten, ändert nichts
./setup.sh --dry-run       # zeigen, was passieren würde
./setup.sh --yes           # alle Vorschläge annehmen (Automatisierung)
./setup.sh --env-file .env.test   # andere Umgebungsdatei
./setup.sh --skip-stack    # nur konfigurieren, nicht bauen/starten
./setup.sh --self-test     # nur die Prüffunktionen testen (CI, ohne Docker)
```

## Was es abfängt

| Phase | Prüft / tut | Typischer Fehler, der damit auffällt |
|---|---|---|
| 1 | Docker + Compose vorhanden, Daemon erreichbar (installiert auf Wunsch) | „Permission denied“ statt kryptischer Compose-Fehler |
| 2 | **`.env`**: Pflichtwerte, Typen, Bereiche, **schwache/Dev-Passwörter**, AET-Format, Bind-Adressen, doppelt vergebene Ports; `.env` in `.gitignore`? Dateirechte 600 | `POSTGRES_PASSWORD=dev`, fehlende Pflichtwerte, zwei Dienste auf einem Port |
| 3 | **Host-Ports**: belegt durch dieses Projekt oder durch etwas anderes? (mit Vorschlag für den nächsten freien Port) | Kollision mit einem anderen Docker-Projekt auf demselben Host |
| 4 | **Bauen und starten** — ohne Demo-Services, mit Warten auf „healthy“ | versehentlich gestartete Mock-RIS im Produktivbetrieb |
| 5 | **Betriebseinstellungen** über die Broker-API: AET-Whitelist, RBAC, DICOM-TLS (PKI-Upload oder selbstsigniert), Alarmierung (mit Testnachricht), ATNA, MLLP, Aufbewahrung | „jeder darf alles“ (leere Whitelist, RBAC aus), „niemand erfährt von Ausfällen“ (kein Webhook), TLS aus |
| 6 | **Abschluss**: Konfigurations-Check des Brokers, C-FIND-Smoke-Test, Bilanz, Restliste | stiller Fehlstart, vergessene manuelle Schritte |

## Sicherheitsnetz (DAU-tauglich)

- **Sicherung vor jeder Änderung**: `cp .env .env.backup-<Zeitstempel>` (Modus 600) — wird am Ende angezeigt.
- **Jede Änderung wird vorher gezeigt**: „jetzt: … / warum: … / Vorschlag: …“, dann Rückfrage. `Enter` übernimmt den Vorschlag, `s` überspringt, `q` beendet ohne Änderung.
- **Passwörter werden nie angezeigt** — nur maskiert (`nm••••vc`), erzeugt werden sie mit `secrets` (24 Zeichen).
- **Eingaben werden geprüft und bei Fehlern erneut abgefragt** — kein Absturz, kein stiller Unsinn.
- **Keine zerstörenden Aktionen**: kein `down -v`, kein Löschen von Daten. Abbrechen (Strg-C) hinterlässt einen Hinweis auf die Sicherung.
- **Ohne Terminal** bricht es mit einer Anleitung ab (statt zu hängen) — für Automatisierung gibt es `--yes`/`--check`.
- **Werte mit Compose-Standardwert** (z. B. das Spool-Verzeichnis) werden als Hinweis geführt, nicht als Fehler.

## Was absichtlich manuell bleibt

Das Script kann nicht alles — diese Punkte landen in der Schlussliste:

| Punkt | Warum |
|---|---|
| Proxy muss die Rolle `brokerWrite` im Header `X-OE3-Roles` übergeben | Kennt nur der Betreiber; ohne sie wird die Oberfläche nach dem RBAC-Einschalten schreibgeschützt (das Script warnt vorher) |
| AET-Whitelist füllen | Die Gerätenamen kennt nur das Haus |
| Zertifikate aus der PKI | Dateien müssen vorliegen (Upload kann das Script, die Beschaffung nicht) |
| Firewall für den MLLP-Port | Netzsache |
| Backups einrichten | Das Script **zeigt** den fertigen `pg_dump`-Befehl und das Spool-Volume, richtet aber keinen Cron ein |
| Demo-Services entfernen | Das Script warnt nur (Entfernen ist ein `down`, das es bewusst nicht ausführt) |
| Monitoring (Prometheus-Scrape) | Betreiber-Infrastruktur |

## Ablauf einer typischen Erstinstallation

```bash
git clone --recurse-submodules <repo> orthanc-dicommwl-broker
cd orthanc-dicommwl-broker
./setup.sh                 # führt durch alles, fragt nach den offenen Punkten
# … später erneut prüfen, ohne etwas zu ändern:
./setup.sh --check
```

Der `--check`-Lauf ist auch der schnellste Weg, den Zustand einer bestehenden
Installation zu beurteilen: er listet genau die noch offenen Punkte
(AET-Whitelist, RBAC, Alarmierung, TLS, ATNA, MLLP) samt Bewertung.

## Abgrenzung zu den anderen Scripts

| Script | Zweck |
|---|---|
| `./setup.sh` | **Erstinbetriebnahme** — prüfen, konfigurieren, einrichten |
| `./build.sh` | Bauen, starten, stoppen, Logs, Registry — der tägliche Weg |
| `./bootstrap.sh` | Kompatibilitäts-Wrapper um `build.sh` (alte Anleitungen) |
| `./ci-local.sh` | Testpipeline (pytest, vitest, E2E, Screenshot-Walk) |
| `./test-stack.sh` | isolierter Test-Stack + Playwright + DOM-/Screenshot-Audit |
