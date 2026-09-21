# Test-Abdeckung — Prüfung und Ergänzungen

Stand: 21.09.2026 · gemessen am laufenden Stand (pytest mit Coverage,
vitest mit Coverage, Playwright-Stack-Suite, Chrome-headless-DOM-Audit,
Screenshot-Walk über alle Views und Menüs).

Diese Prüfung beantwortet zwei Fragen: **wo fehlen Tests** und **was sieht man
auf den Bildschirmen nicht, wenn man nur Code liest**.

## 1. Vorher/Nachher

| Ebene | vorher | nachher |
|---|---|---|
| pytest | 407 | **432** (+25) |
| vitest | 506 | **522** (+16) |
| Playwright (Stack) | 55 | 55 |
| verify-ui.cjs (DOM-Audit) | 133 Checks | 133 Checks |
| **verify-screens.cjs** (neu) | — | **225 Checks** + 52 Screenshots |
| Backend-Coverage | 95 % | **96 %** |
| `aggregation.py` | 76 % | **96 %** |
| `mllp.py` | 76 % | **95 %** |
| `api/broker.ts` (Client) | 83,7 % | **91,8 %** |
| Broker-UI gesamt | 97,3 % Komponenten / 94,6 % Seiten | unverändert hoch |

## 2. Neue Tests

### Backend

| Datei | Inhalt | Warum |
|---|---|---|
| `tests/test_aggregation.py` (neu, 7 Tests) | Prioritäts-Merge + Dedupe, übersprungene Quelle **mit** und **ohne** Snapshot, fehlgeschlagene Quelle mit/ohne Cache, Einzelquellen-Modus (der C-FIND-Test), lokale Einträge mit höchster Priorität, die Vorschau-Flags (`count_metrics`, `store_cache`) und dass eine Vorschau **keine** Routing-Herkunft schreibt | Der Aggregationscode war nach dem Umbau in Sprint 3 die schwächste Stelle (76 %) — und er ist das Herz des Brokers |
| `tests/test_mllp.py` (neu, 9 Tests) | MLLP-Framing (auch bei zerteilten TCP-Chunks), Übergröße, geschlossene Verbindung, Anwenden über den MLLP-Pfad (gleicher Parser wie REST), NAK bei kaputter Nachricht, Überleben einer unerwarteten Exception, **echter Socket-Round-Trip** gegen den Listener, belegter Port | Viele RIS sprechen nur MLLP; der Listener war nur indirekt berührt (76 %) |
| `test_api.py` (+7) | Einzelabrufe (A7), Zertifikat-Upload (A10, inkl. falscher Schlüssel/abgelaufen/Müll/0600/Audit ohne Schlüsselmaterial), HL7-Detail + Replay (A11), Cache-Refresh (A12), Treffer-Pfad des C-FIND-Tests | Sprint-3/4-Funktionen brauchten eigene Verträge |

### Frontend

| Datei | Inhalt |
|---|---|
| `src/api/broker.test.ts` (+9) | die neuen Client-Aufrufe: `sources.query`, `worklistPreview`, `hl7.message`/`reprocess` (dry_run), `cache.refresh` (auch je Quelle), `tls.upload`, die **neu ergänzten** `get()`-Einzelabrufe, `since`-Filter und `offset` bei den Listen |
| `components/ConfigRowCard.test.tsx` (neu, 4) | Karten-Klick öffnet die Bearbeitung, Enter/Leertaste ebenso, Knöpfe darin werden nicht geschluckt, ohne `onOpen` ist die Karte nicht klickbar |
| `lib/config-diff.test.ts` (+2) | kein „#?" mehr für Einträge ohne Objekt-ID, ID bleibt sonst sichtbar |
| `components/TlsCard.test.tsx` (+2) | Upload-Fehlerpfad zeigt die Server-Meldung, erfolgreicher Upload leert die Dateifelder |

### Neu: Screenshot-Walk (`e2e/stack/verify-screens.cjs`)

Läuft über **jede** Route der App (Studien, Hochladen, Aktivität, Audit-Logs,
Worklists, Remote-Quellen, Einstellungen) und **alle zehn** Broker-Seiten, dazu
alle Dialoge/Panels (Quelle bearbeiten, C-FIND-Test, Arbeitslisten-Vorschau,
HL7, TLS-Karte, Aufbewahrung, Alerting, About, „Was ist das?"), jeweils
**Desktop 1400×900** und **Mobil 375×812**.

Pro Ansicht geprüft: Konsolen-/HTTP-Fehler, **genau eine `<h1>`**, kein
horizontaler Overflow, **keine Rohschlüssel** im DOM, nicht leer, erwarteter
Inhalt sichtbar. Die Screenshots landen in `e2e/stack/shots/` (52 Bilder) und
werden zusätzlich **visuell** begutachtet.

Eingebunden in `test-stack.sh` (läuft mit dem isolierten Stack) und in der
Skript-Stage von `ci-local.sh`.

## 3. Was die Screenshot-Analyse gefunden hat

| Befund | Wirkung | Status |
|---|---|---|
| **`broker.entity_cache` als Rohschlüssel** im Änderungsprotokoll | Meine neuen Audit-Aktionen (Sprint 1/4) führten die Objektarten `cache`, `tls`, `hl7_message` ein — es gab aber nur fünf Labels. Der Betreiber sah den Schlüssel statt „Cache" | **behoben**: 7 Labels in allen 9 Sprachen, Filterliste der Seite erweitert |
| **Upload-Seite ohne `<h1>`** (Desktop **und** Mobil) | Verstößt gegen die A11y-Regel des Forks (genau ein `<h1>` pro Seite); Screenreader-Nutzer verlieren die Seitenüberschrift | **behoben**: `<h1>` mit `upload.title` (neu in 9 Sprachen) |
| **`#?` in der Objekt-Spalte** des Änderungsprotokolls | Einträge ohne Objekt-ID (Cache/Spool/TLS) zeigten „#?" — Rauschen ohne Information | **behoben**: Feld bleibt leer, ID erscheint nur, wenn es eine gibt |
| **Aktionsknöpfe umbrechen** in der Quellentabelle (Desktop) | Drei Knöpfe (C-FIND-Test, Bearbeiten, Löschen) passten nicht in die 110 px breite Spalte; das Papierkorb-Symbol rutschte in eine zweite Zeile | **behoben**: Spalte auf 150 px (Quellen und Ziele) |
| Endpunkt bricht am Bindestrich (`mock-ris` / `-a:11114`) | bewusst: lange DICOM-Endpunkte dürfen nicht mitten im Token umbrechen — der Umbruch ist die schonendste Variante | akzeptiert (dokumentiert) |
| Leere Flächen unter kurzen Seiten (Full-Page-Screenshot) | kein Fehler, nur die Aufnahmeart | akzeptiert |

Zusätzlich bestätigt (keine Abweichung): mobile Dialoge passen und scrollen,
Mobile-Karten zeigen alle Felder, Sprachumschaltung ohne Rohschlüssel,
TLS-Karte mit gesperrtem Upload-Knopf bis zur Dateiauswahl, Vorschau mit
Herkunft und Dedupe-Anzeige, Hilfe-Dialog mit drei Abschnitten.

## 4. Hygiene-Fund beim Aufräumen

Der Screenshot-Walk schreibt nach `e2e/stack/shots/`, `vitest --coverage` nach
`coverage/` — beide Verzeichnisse waren **nicht** in der `.gitignore` (sie deckte
nur die älteren Playwright-Ausgaben ab), sodass 53 Screenshots und 334
Coverage-Dateien im öffentlichen Fork landeten. Entfernt und ignoriert; ebenso
die Altbestände `e2e/prod/screenshots/` und die versehentlich verschachtelte
Kopie `e2e/prod/e2e/` aus einem früheren Lauf.

Dabei kam ein Fehler im eigenen Schutzskript zum Vorschein: `pre-push-fork.sh`
verweigerte **jeden** Push, in dessen Diff eine blacklistete Datei vorkam — also
auch die Aufräum-Commits, die genau diese Dateien löschen. Der Guard prüft jetzt
den Diff-Status: **hinzugefügte oder geänderte** blacklistete Pfade werden
abgelehnt, **Löschungen** sind erlaubt. Der Schutz bleibt damit erhalten und
blockiert nicht mehr seine eigene Abhilfe.

## 5. Bewusst nicht getestet

| Bereich | Begründung |
|---|---|
| `mock_ris.py` (71 %) | Demo-Werkzeug, nicht Teil der Auslieferung; ein Test würde nur den Mock prüfen |
| `public/config.js`, `vite.config.ts`, E2E-Konfigurationen | Konfigurationsdateien ohne Logik |
| Basis-OE3-Features außerhalb des Broker-Slice (Studien, Serien, Viewer) | Nicht Teil dieses Forks; die Abdeckung dort (14–70 %) ist Upstream-Stand. Der Screenshot-Walk prüft sie trotzdem auf **Darstellung** (keine Konsolenfehler, eine H1, kein Overflow) |
| ATNA-Nachrichtenhistorie, Export-Diff | absichtlich nicht gebaut (siehe `api-completeness-audit.md`, Sprint 4) |

## 6. Reproduzieren

```bash
cd mwl-broker && .venv/bin/pytest tests -q --cov=mwl_broker --cov-report=term-missing
cd orthanc-explorer-3-usable && npx vitest run --coverage
./test-stack.sh                       # Playwright + verify-ui + Screenshot-Walk
node orthanc-explorer-3-usable/e2e/stack/verify-screens.cjs   # einzeln, gegen den laufenden Stack
node orthanc-explorer-3-usable/e2e/stack/verify-ui.cjs        # DOM-Audit
```
