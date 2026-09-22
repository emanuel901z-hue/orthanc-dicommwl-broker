# Betriebshandbuch (Runbook)

Für den Dienst am Gerät: **was tun, wenn …** — mit den echten Befehlen, den
Stellen, an denen man nachsieht, und der Grenze, ab der man eskaliert.

Alle Befehle laufen im Repository-Verzeichnis (`orthanc-dicommwl-broker`).
`./build.sh --logs mwl-broker` zeigt die Broker-Logs, `./setup.sh --check`
prüft den Konfigurationszustand.

## 0. Die drei Werkzeuge, die fast alles beantworten

| Werkzeug | Wofür |
|---|---|
| `./setup.sh --check` | Ist-Zustand: Ports, AET-Whitelist, RBAC, TLS, Alarmierung, Health-Findings — **ändert nichts** |
| Oberfläche → **MWL-Broker** | Übersicht: SCP/DB, C-ECHO-Matrix, Abfrage-Log, Spool, Cache, MPPS, Auslastung |
| `./build.sh --logs mwl-broker` | Live-Log des Brokers |

Dazu die Health-Endpunkte:

```bash
curl -s http://127.0.0.1:18081/healthz/ready          # bereit? (db, scp)
curl -s http://127.0.0.1:18081/api/v1/health/config  # Konfigurations-Findings
curl -s http://127.0.0.1:18081/api/v1/status          # Version, Quellen, Ziele
```

## 1. „Die Modalität sieht keine Arbeitsliste"

**Erste Frage:** kommt die Abfrage überhaupt an? → Übersicht, Karte
*Abfrage-Log* (`logs/queries`).

| Beobachtung | Ursache | Maßnahme |
|---|---|---|
| **Kein Eintrag im Abfrage-Log** | Die Modalität erreicht den Broker nicht (falscher AET/Port, Netz, Firewall) | Am Gerät AET `BROKER_AET` (Standard `MWLBROKER`) und Port `BROKER_DICOM_PORT` prüfen; `ss -tln | grep <port>` auf dem Broker-Host |
| Eintrag mit Status **failed** | Keine Quelle hat geantwortet | Unten „Eine Quelle antwortet nicht" |
| Eintrag mit Status **partial**, Spalte „stale" | Eine Quelle war weg, Cache hat überbrückt | Quelle prüfen (siehe unten) — die Liste war unvollständig |
| Eintrag mit **0 Antworten**, Quellen aber grün | Die Quellen kennen den Fall nicht, oder die **Stationsregel** verbirgt ihn | Übersicht → *Fall prüfen*; Stationsregeln-Seite → *Vorschau* für diese Station |
| Antworten vorhanden, Gerät zeigt sie nicht | Filter am Gerät (Datum/Modalität/Station) | Mit derselben Abfrage gegen den Broker testen: **Upstream-Quellen → Lupe** (C-FIND-Test) |

**Stationsregel-Verdacht:** Stationsregeln → *„Was würde diese Konsole
bekommen?"* mit der AET der Modalität. Erscheint die Liste leer, während die
Quellen grün sind, ist die Regel zu eng (`allow` mit falscher Quellenliste) oder
eine `deny`-Regel greift.

## 2. „Eine Quelle (RIS) antwortet nicht"

1. **C-ECHO:** Übersicht → in der Quellenzeile auf das Blitz-Symbol, oder
   ```bash
   curl -s -X POST http://127.0.0.1:18081/api/v1/sources/1/echo | python3 -m json.tool
   ```
   - `ok: false` mit `Temporary failure in name resolution` → **Hostname falsch** oder der Broker erreicht das Netz nicht.
   - `ok: false` mit `Connection refused` → Dienst am Ziel aus oder falscher Port.
   - `ok: true` → die Quelle lebt: es ist ein **Inhaltsproblem**, kein Netzproblem.
2. **Liefert sie Arbeitslisten?** Upstream-Quellen → **Lupe** (C-FIND-Test):
   ```bash
   curl -s -X POST http://127.0.0.1:18081/api/v1/sources/1/query \
     -H 'Content-Type: application/json' -d '{}' | python3 -m json.tool
   ```
   `answers: 0` bei `ok: true` heißt: das RIS hat für diese Abfrage nichts —
   nicht der Broker ist das Problem.
3. **Circuit Breaker offen?** In der Quellenzeile erscheint ein Badge
   „übersprungen"; die Übersicht zeigt `breaker_state: open`. Der Broker wartet
   `breaker_open_seconds` (Standard 60 s) ab. Sofort wieder aufnehmen:
   ```bash
   curl -X POST http://127.0.0.1:18081/api/v1/sources/1/reset-breaker
   ```
   Der Reset steht im Änderungsprotokoll.
4. **Timeout zu knapp?** Broker-Einstellungen → `upstream_timeout_s`
   (Standard 10 s). Bei langsamen RIS auf 20–30 s erhöhen.

## 3. „Bilder kommen nicht im PACS an"

1. **Store-Queue** (Seite *Store-Warteschlange*): Einträge mit Status
   *wartend*/*aufgegeben* ansehen — dort steht der **letzte Fehler** im Klartext.
2. **Ziel erreichbar?** Store-Ziele → C-ECHO in der Zeile.
3. **Routing prüfen:** Übersicht → *Fall prüfen* mit der Zugangsnummer. Es wird
   die Quelle, die Regel und das Ziel genannt. Kein Treffer → es greift das
   **Standard-Ziel**; ist keines gesetzt, wird das Bild **abgewiesen** (Health
   meldet `no_default_target`).
4. **Aufgegebene Bilder erneut senden:** Store-Warteschlange → *Alle erneut
   senden* (oder einzeln *Jetzt erneut senden*). Das ist auditiert.
5. **Spool voll?** Health-Finding `spool_full` bzw. Badge in der Karte
   *C-STORE-Spool*. Platz schaffen (alte, zugestellte Einträge räumt die
   Aufbewahrung) oder `spool_max_items`/`spool_max_bytes` erhöhen.
   **Wichtig:** Bei vollem Spool weist der Broker neue Bilder **ab** — die
   Modalität sieht einen Fehler, statt dass Bilder still verloren gehen.

## 4. „Das RIS bekommt keine Statusmeldungen (MPPS)"

1. Übersicht → Karte **Durchgeführte Schritte (MPPS)**: Badge
   *„n noch nicht gemeldet"* und die Spalte *Meldung an RIS* mit dem Fehlertext.
2. Broker-Einstellungen prüfen: `mpps_forward_enabled`, `mpps_forward_transport`
   (`mllp`/`webhook`), `mpps_forward_host`/`_port` bzw. `_url`.
3. MLLP-Test von Hand:
   ```bash
   nc -zv <ris-host> 2575          # erreichbar?
   ```
4. Offene Meldungen erneut senden:
   ```bash
   curl -X POST http://127.0.0.1:18081/api/v1/mpps/forward-pending \
     -H 'X-OE3-Roles: brokerWrite'
   ```
5. Der Broker meldet **asynchron** — eine langsame Gegenstelle verzögert die
   Modalität nie.

## 5. „Der Broker antwortet nicht / 500er"

```bash
./build.sh --logs mwl-broker | tail -50      # Traceback?
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:18081/healthz
docker compose ps                            # alles healthy?
```

| Symptom | Ursache | Maßnahme |
|---|---|---|
| 500 auf mehreren Seiten, Log zeigt `column … does not exist` | **Schema und Code passen nicht zusammen** | `./build.sh mwl-broker` (Image mit den Migrationen neu bauen) — der Broker prüft das beim Start und verweigert sonst den Dienst |
| `unhandled error on …` mit Request-ID | Programmfehler | Log-Zeile mit Traceback sichern und melden |
| Antworten dauern sekundenlang | Quelle langsam / Timeout zu hoch | `upstream_timeout_s` senken, Quelle prüfen |
| `QueuePool limit … connection timed out` | DB-Pool erschöpft (viele Modalitäten + Worker) | `BROKER_DB_POOL_SIZE`/`BROKER_DB_MAX_OVERFLOW` in `.env` erhöhen, `./build.sh` |

## 6. Sicherung und Wiederherstellung

```bash
./deploy/backup.sh --check                # läuft Postgres? Platz? letzte Sicherung?
./deploy/backup.sh --dir /mnt/backup      # sichern (DB + Spool + .env)
./deploy/backup.sh --list                 # vorhandene Sicherungen
./deploy/backup.sh --restore <Pfad>       # wiederherstellen (fragt nach!)
```

* Gesichert werden **beide** Datenbanken (Broker `mwl`, Orthanc `orthanc`),
  das Spool-Verzeichnis und die `.env`.
* Eine Sicherung ist erst dann etwas wert, wenn die Wiederherstellung geübt ist:
  `./deploy/backup-roundtrip-test.sh` legt im Test-Stack einen Marker an, löscht
  ihn, stellt die Sicherung zurück und prüft, dass er wieder da ist. Das läuft
  bei jedem `./test-stack.sh` mit.
* Empfohlener Cron (täglich 2:15, 30 Sicherungen behalten):
  `15 2 * * * cd /opt/orthanc-dicommwl-broker && ./deploy/backup.sh --dir /mnt/backup --keep 30 >> /var/log/mwl-backup.log 2>&1`

## 7. Update auf eine neue Version

```bash
git pull --recurse-submodules
./setup.sh --check          # was ist konfiguriert (unverändert lassen)
./deploy/backup.sh          # Sicherung VOR dem Update
./build.sh --health         # bauen + starten; Migrationen laufen beim Start
./setup.sh --check          # Health-Findings ansehen
```
Der Broker **verweigert den Start**, wenn das Image Migrationen enthält, die
nicht zur Datenbank passen — dann ist das Image falsch gebaut, nicht die
Datenbank defekt.

## 8. Wann eskalieren

| Lage | Sofortmaßnahme | Eskalation |
|---|---|---|
| Keine Modalität bekommt Arbeitslisten | Cache-Refresh (`Cache jetzt aktualisieren`) + Quellen-C-ECHO | RIS-Betreiber, Broker-Betreiber |
| Bilder stapeln sich im Spool | Ziel-C-ECHO, Ziel prüfen | PACS-Betreiber |
| RIS bekommt keine Statusmeldungen | `forward-pending` erneut senden | RIS-Schnittstellenbetreuer |
| Broker startet nicht | Logs sichern, Sicherung prüfen | Broker-Betreiber |
| Verdacht auf Datenverlust | **Nichts weiter tun**, Sicherung + Logs sichern | Betreiber + Backup-Verantwortlicher |

## 9. Wo man nachsieht (Kurzliste)

| Frage | Ort |
|---|---|
| Was hat das Gerät abgefragt? | Übersicht → *Abfrage-Log* (PHI-frei: Accession, Station, Modalität) |
| Wer hat die Konfiguration geändert? | Seite *Änderungsprotokoll* (mit Rollback) |
| Was wurde weitergeleitet? | Seite *Store-Warteschlange*, Log `logs/stores` |
| Welche Schritte haben die Modalitäten gemeldet? | Übersicht → *MPPS*, `/api/v1/mpps` |
| Wie ausgelastet ist der Broker? | Übersicht → *Auslastung und Fehler* (`/api/v1/stats/overview`) |
| Ist etwas grundsätzlich falsch konfiguriert? | Übersicht → *Konfigurations-Check* (`/health/config`) |
| Was macht die DICOM-Strecke gerade? | `/metrics` (Prometheus) |
