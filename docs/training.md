# Schulungsunterlagen — MWL-Broker

Stand: 22.09.2026 · Ergebnis von **C4** aus [`next-steps.md`](next-steps.md)

Diese Unterlagen bauen auf dem auf, was im Projekt schon existiert: die
„Was ist das?"-Hilfe auf jeder Seite (`PageHelp`), die
[MFA-Reise](mfa-usability-test.md) (ein unbedarfter Anwender macht die Fehler, die
Anfänger machen), das [Runbook](runbook.md) und die Simulationswerkzeuge. Neu ist
die **Form**: Zielgruppen, Ablauf, Übungen mit überprüfbarem Ergebnis.

## 1. Zielgruppen

| Zielgruppe | Muss danach können | Zeit |
|---|---|---|
| **MTRA / Modalitäten-Admin** | wissen, dass die Arbeitsliste vom Broker kommt; „keine Arbeitsliste" melden können (mit den richtigen Angaben: Station, AET, Zeitpunkt) | 30 min |
| **Klinik-IT (1st Level)** | die drei Werkzeuge aus dem Runbook §0 bedienen; Alarm → Runbook-Abschnitt zuordnen; eskalieren oder abschließen | 2 h |
| **Radiologie-IT (2nd Level)** | Quellen/Ziele/Regeln/Stationen konfigurieren; Health-Findings abarbeiten; Spool und Dead Letters; Backup prüfen; Änderungen zurücknehmen | 1 Tag |
| **Integrator (RIS/PACS)** | die Schnittstellen aus dem [Conformance Statement](dicom-conformance-statement.md) anbinden; HL7 senden (ORM/OMG, ADT); Fehlerfälle einordnen | 1 Tag |
| **Datenschutz / QS** | Datenfluss und Aufbewahrung erklären ([`security-and-validation.md`](security-and-validation.md)); den Nachweis führen (Suiten, Änderungsprotokoll) | 1 h |

## 2. Bausteine (vorhanden, nicht neu zu bauen)

| Baustein | Wo | Wofür in der Schulung |
|---|---|---|
| „Was ist das?"-Hilfe je Seite | Oberfläche, jede Broker-Seite | Einstieg ohne Handbuch; die zehn Seiten haben je *Was ist das / Was trage ich ein / Was geht schief* |
| Runbook mit fünf echten Störungen | [`runbook.md`](runbook.md) | der Kern des 1st-Level-Kurses |
| MFA-Reise | `./mfa-test.sh` | Fehler eines unbedarften Anwenders **vorleben** statt behaupten |
| Simulation (Routing, Modify, Stationen) | Seite *MWL Broker* → *Fall prüfen*, *Stationsregeln* | Änderung prüfen, ohne sie zu machen |
| Änderungsprotokoll + Rollback | Seite *Änderungsprotokoll* | „Wer war das?" und zurücknehmen |
| Health-Panel mit Fix-Links | Seite *MWL Broker* | Fehlkonfiguration selbst finden |
| Alarmregeln + Runbook-Zuordnung | [`support-and-sla.md`](support-and-sla.md) §4 | Alarm → Maßnahme |
| Demo-/Test-Stack | `./build.sh --demo`, `./test-stack.sh` | Übungsplatz (nie produktiv) |

Die zehn Seiten mit Hilfetext (ein Test hält diese Liste mit der Oberfläche
zusammen) — `overview` (Übersicht), `sources` (Quellen), `targets` (Ziele),
`rules` (Routing-Regeln), `transforms` (Modify-Regeln), `stations`
(Stationsregeln), `worklist` (lokale Worklist), `spool` (Store-Warteschlange),
`audit` (Änderungsprotokoll), `settings` (Broker-Einstellungen).

## 3. Ablauf (Vorschlag)

**30 Minuten (MTRA).** Was der Broker ist (ein Satz), was die Modalität sieht,
warum die Arbeitsliste manchmal leer ist, was beim Anruf gebraucht wird:
Station, AET, Uhrzeit, Accession. Kein Terminal.

**2 Stunden (1st Level).** Runbook §0 (die drei Werkzeuge) am laufenden
Demo-Stack; dann je 15 Minuten eine der fünf Störungen — vorgeturnt **und**
selbst gemacht (Übungen 3, 7, 9). Danach: Alarm → Tabelle in
[`support-and-sla.md`](support-and-sla.md) §4, Eskalationsgrenzen
([Runbook §8](runbook.md#8-wann-eskalieren)).

**1 Tag (2nd Level).** Vormittag: Konfiguration (Übungen 1, 2, 4, 10),
Nachmittag: Betrieb (Übungen 3, 6, 7, 8, 9, 12), zum Schluss eine **Störung ohne
Ansage** (der Trainer wählt eine aus dem Runbook).

**1 Tag (Integrator).** Conformance Statement und IHE-Aussage durchgehen, dann
gemeinsam: C-FIND-Matching prüfen, MPPS-Rückmeldung sehen, HL7 senden
(Übungen 4, 5, 10), TLS aufsetzen, Grenzen besprechen
([§9](dicom-conformance-statement.md)).

## 4. Übungen

Alle Übungen laufen gegen den **Demo-Stack** (`./build.sh --demo`) oder den
Test-Stack (`./test-stack.sh --keep`). Vorher: `./build.sh --health`.

### Ü1 — Eine Quelle anlegen und prüfen

**Ziel:** den Weg „Quelle hinzufügen → erreicht sie uns?" beherrschen.
**Vorgehen:** Seite *Upstream sources* → *Quelle hinzufügen* (Name `ris-a`,
AET `RIS_A`, Host `mock-ris-a`, Port 11114) → speichern → Zeile anklicken →
*C-ECHO jetzt* → *Worklist-Abfrage testen*.
**Erwartet:** C-ECHO mit RTT in Millisekunden; der C-FIND-Test listet
Accession-Nummern (`ACC-A-…`).
**Geht schief, wenn:** der Port der Host-Port statt des Container-Ports ist, oder
die AET nicht zur Gegenstelle passt → Fehlermeldung im Dialog lesen.

### Ü2 — Stationsregel und Vorschau

**Ziel:** einer Konsole eine eigene Sicht geben, **ohne** etwas zu ändern.
**Vorgehen:** Seite *Stationsregeln* → Regel für `CT_01` anlegen (Quelle `ris-b`
ausblenden) → *Vorschau starten*.
**Erwartet:** die Matrix zeigt je Station sichtbare/verborgene Quellen; eine
Warnung erscheint, wenn eine Konsole eine **leere** Liste sehen würde.
**Merksatz:** die Vorschau läuft über denselben Code wie die echte Abfrage.

### Ü3 — Eine tote Quelle und der Circuit Breaker

**Ziel:** verstehen, dass eine tote Quelle die Modalität **nicht** blockiert.
**Vorgehen:** Quelle `dead` (Host `orthanc`, Port 8042 — kein DICOM) anlegen,
`timeout_s` 1 → C-FIND-Test je Quelle → Statuskarte ansehen → Breaker-Reset.
**Erwartet:** die Abfrage antwortet trotzdem (nur langsamer); nach drei Fehlern
steht der Breaker auf *offen* und die Quelle wird übersprungen; der Reset-Knopf
holt sie zurück.
**Geht schief, wenn:** der Timeout zu hoch steht — dann wartet jede Modalität.

### Ü4 — Einen Auftrag per HL7 schicken

**Ziel:** den Weg „RIS schickt Auftrag → Modalität sieht ihn" einmal selbst gehen.
**Vorgehen:** Seite *Lokale Worklist* → ORM-Beispiel einfügen → **Trockenlauf** →
anwenden → in der Liste prüfen.

```bash
curl -s -X POST 'http://127.0.0.1:18081/api/v1/hl7/orm?dry_run=true' \
  -H 'Content-Type: text/plain' --data-binary @/tmp/orm.hl7 | python3 -m json.tool
```

**Erwartet:** Trockenlauf zeigt die geparsten Felder und die geplante Aktion;
nach dem Anwenden steht der Eintrag in der lokalen Worklist.
**Geht schief, wenn:** OBR-3/ORC-3 fehlt → „no accession number" (gewollt).

### Ü5 — Was **nicht** angewandt wird (und warum)

**Ziel:** die gefährlichste Verwechslung kennen: Befund ≠ Auftrag.
**Vorgehen:** dieselbe Abfrage mit einer `ORU^R01` (Befundmeldung) senden.
**Erwartet:** HTTP 422 mit dem Satz „… is a result/report message, not an order —
it must not create a worklist entry"; in der Arbeitsliste entsteht **nichts**;
im HL7-Nachrichtenprotokoll steht die Ablehnung mit Begründung.
**Lehre:** Ein RIS, das Befunde streut, verunreinigt die Arbeitsliste nicht.

### Ü6 — Sicherung und Wiederherstellung üben

**Ziel:** den Nachweis führen, dass die Sicherung etwas wert ist.
**Vorgehen:** `./deploy/backup.sh --dir /tmp/backup` → `./deploy/backup.sh --list`
→ `./deploy/backup-roundtrip-test.sh`.
**Erwartet:** beide Datenbanken, Spool und `.env` sind in der Sicherung; der
Round-Trip legt einen Marker an, löscht ihn, stellt zurück und findet ihn wieder.
**Merksatz:** eine Sicherung ohne geübte Wiederherstellung ist eine Annahme.

### Ü7 — Eine Fehlkonfiguration finden und beheben

**Ziel:** das Health-Panel als Werkzeug nutzen.
**Vorgehen:** beim Standardziel die Markierung *Standard* entfernen → Seite
*MWL Broker* → Konfigurationsprüfung ansehen → Fix-Link folgen → wieder setzen.
**Erwartet:** ein Befund „kein Standardziel" (mit Erklärung, was dann passiert:
Instanzen ohne Routing-Treffer werden **abgewiesen**); nach dem Setzen ist die
Prüfung grün.

### Ü8 — Änderung nachvollziehen und zurücknehmen

**Ziel:** „wer hat das geändert?" beantworten können.
**Vorgehen:** eine Regel ändern → Seite *Änderungsprotokoll* → Eintrag öffnen
(vorher/nachher) → *Zurücknehmen*.
**Erwartet:** der Diff zeigt die alte und die neue Priorität; nach dem Rollback
gilt wieder der alte Wert — beides als neuer Protokolleintrag.

### Ü9 — PACS-Ausfall: der Spool

**Ziel:** Bilder gehen bei einem Ausfall **nicht** verloren.
**Vorgehen:** Ziel stoppen (`docker compose stop dicom-peer`) → Bilder schicken
(`python3 mwl-broker/scripts/cstore_smoke.py 127.0.0.1 11113 MWLBROKER ACC-SPOOL 1.2.3.4`)
→ Seite *Store-Warteschlange* ansehen → Ziel starten → *Erneut senden* (oder
*Alle erneut senden*).
**Erwartet:** die Modalität bekam trotzdem eine Bestätigung („sicher gepuffert");
der Eintrag wandert nach dem Retry auf *zugestellt*.
**Geht schief, wenn:** das Budget voll ist — dann **Abweisung** (kein stilles
Verwerfen), sichtbar als Alarm.

### Ü10 — Zwei Patienten-IDs, zwei Bedeutungen (IHE PIR)

**Ziel:** Zusammenführen und Verknüpfen unterscheiden.
**Vorgehen:** `ADT^A40` senden (Zusammenführen) → Arbeitsliste/Vorschau ansehen;
dann `ADT^A24` für ein anderes Paar (Verknüpfen) → Seite *Lokale Worklist* →
Karte *Patienten-IDs*.

```bash
curl -s -X POST 'http://127.0.0.1:18081/api/v1/hl7/adt?dry_run=false' \
  -H 'Content-Type: text/plain' --data-binary @/tmp/a40.hl7 | python3 -m json.tool
```

**Erwartet:** die Karte kennzeichnet beide Arten; die Abfrage
`GET /api/v1/merges/resolve/<alte ID>` liefert für **beide** die aktuelle ID —
aber nur die Zusammenführung schreibt die Arbeitslisten-Antwort um.
**Lehre:** eine Verknüpfung entzieht keine ID.

### Ü11 — Zwei Instanzen (Hochverfügbarkeit)

**Ziel:** wissen, was HA hier bedeutet und was nicht.
**Vorgehen:** `docker compose --profile ha up -d` → Seite *MWL Broker* → Karte
*Broker-Instanzen* → Warnung lesen.
**Erwartet:** zwei Instanzen mit Herzschlag; die Warnung nennt die zwei Dinge, die
der Broker nicht sehen kann (gemeinsames Spool-Volume, VIP/Load Balancer).

### Ü12 — Alarmierung testen

**Ziel:** wissen, dass Alarme wirklich ankommen.
**Vorgehen:** Seite *Broker-Einstellungen* → Webhook eintragen und Ereignisse
wählen → *Testnachricht*; Ereigniskatalog ansehen (`GET /notify/events`).
**Erwartet:** die Testnachricht kommt am Webhook an; die Ereignisliste ist
dieselbe wie im Backend.

## 5. „Kann danach" — Abnahmekriterien je Rolle

- **1st Level:** kann aus dem Runbook die passende Störung wählen, die drei
  Werkzeuge bedienen und begründet eskalieren — ohne Konfiguration zu ändern.
- **2nd Level:** kann eine Quelle/Ziel/Regel/Stationsregel anlegen, prüfen
  (C-ECHO, C-FIND-Test, Simulation, Vorschau), wieder zurücknehmen und im
  Änderungsprotokoll belegen.
- **Integrator:** kann C-FIND-Matching und MPPS gegen den Broker prüfen, HL7
  senden (ORM/OMG, ADT), die Grenzen benennen und ein Backup einrichten.
- **QS/Datenschutz:** kann Datenfluss, Aufbewahrung und Nachweisbarkeit
  ([`security-and-validation.md`](security-and-validation.md)) erklären und die
  Suiten als Abnahmegrundlage benennen.

## 6. Wo geübt wird

**Nie am produktiven Stack.** Übungsplätze sind `./build.sh --demo` (Mock-RIS +
zweites PACS) oder `./test-stack.sh --keep` (eigener Projektname, eigene Ports,
danach `--down`). Die Übungen 3, 6 und 9 verändern Daten oder stoppen Dienste —
auf einer Anlage im Betrieb wäre das ein Zwischenfall.

## 7. Kurztest: fünf Störungen

Zum Abschluss des 1st-Level-Kurses (Lösungen in [`runbook.md`](runbook.md)):

1. Um 8:10 ruft die CT an: „keine Arbeitsliste". Der Broker läuft, die Quellen
   antworten auf C-ECHO. Was prüfen Sie zuerst?
2. Das PACS ist seit 20 Minuten nicht erreichbar. Was passiert mit den Bildern,
   die jetzt aufgenommen werden — und was sagen Sie der MTRA?
3. Der Alarm `MWLSpoolDeadLetters` feuert. Was ist passiert, und was dürfen Sie
   **nicht** tun?
4. Das RIS meldet „der Auftrag bleibt offen". Wo sehen Sie, ob die
   Statusmeldung rausgegangen ist?
5. Der Broker antwortet auf allen Seiten 500, im Log steht `column … does not
   exist`. Was ist die Ursache, und was ist die Maßnahme?
