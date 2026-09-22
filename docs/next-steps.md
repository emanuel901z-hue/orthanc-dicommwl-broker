# Nächste Schritte

Stand: 22.09.2026 · Die fünf Sprints aus
[`commercial-comparison.md`](commercial-comparison.md) sind abgeschlossen
(MPPS, feldweiser Merge + HL7-Mapping, Conformance Statement, Statistik,
UPS-RS-Subset). Dieses Dokument plant, was danach sinnvoll ist — getrennt nach
**Funktion**, **Betrieb** und **Beschaffung**, mit Aufwand und Begründung.

## 1. Wo wir stehen (kurz)

| Fähigkeit | Stand |
|---|---|
| MWL C-FIND Fan-out/Merge/Dedupe, Stationsregeln, Transforms, Store-Routing + Spool, Cache-Ausfallbrücke | vorhanden |
| HL7 ORM (REST + MLLP), lokale Worklist, ATNA, DICOM-TLS/mTLS, RBAC, Änderungsprotokoll, Retention | vorhanden |
| **MPPS SCP + Status-Rückmeldung an das RIS** | vorhanden (Sprint 1) |
| **Feldweiser Merge + HL7→DICOM-Mapping** | vorhanden (Sprint 2) |
| **DICOM Conformance Statement + IHE-Aussage** | vorhanden (Sprint 3) |
| **Statistik/Reporting** | vorhanden (Sprint 4) |
| **UPS-RS** (Suche/Abruf/Anlegen/Status) | vorhanden, **Subset** (Sprint 5) |
| Werkzeuge: Vorschau, C-FIND-Test, Trockenläufe, Health, Bootstrap, Tests aller Ebenen | vorhanden |

## 2. Funktionale Kandidaten

| # | Vorhaben | Warum | Aufwand |
|---|---|---|---|
| F1 | **MRN-Merge / Identifier-Reconciliation** (IHE PIR vollständig) | Häuser mit mehreren Patienten-IDs pro Person bekommen sonst doppelte Einträge; kommerzielle Produkte haben das | mittel–groß |
| F2 | **Weitere Datenquellen**: HL7 `ADT` (Patientenänderungen/Merge), `OMG`, GDT/BDT, strukturierte Textdateien | Praxisumgebungen ohne HL7-Schnittstelle (GDT) und Häuser, die ADT nicht weiterleiten | mittel (je Quelle klein) |
| F3 | **UPS-RS vervollständigen**: Subscriptions/WebSocket-Events, vollständiger Attributsatz, Suche über Upstream | Für Clients, die den Standard voll ausreizen; heute bewusst als Grenze dokumentiert | groß |
| F4 | **Voraufnahmen-Prefetch** (relevante Voruntersuchungen auf Anforderung ziehen) | Radiologen brauchen Voraufnahmen am Befundplatz; heute Aufgabe von PACS/VNA | groß (eigenes Werkzeug) |
| F5 | **Tag-Morphing über Felder hinaus**: Sequenz-Operationen, Private Tags, Encoding-Transkodierung | Für Häuser mit exotischen Empfängern | mittel |
| F6 | **MPPS N-GET** (Status zurücklesen) und MPPS-Statistik je Modalität | Betreiber fragen „welche Modalität meldet nicht?" | klein |
| F7 | **Arbeitslisten-Vorschau für mehrere Stationen gleichzeitig** (Matrix „welche Konsole sieht was") | Konfigurationsprüfung vor dem Rollout | klein |

## 3. Betriebliche Kandidaten

| # | Vorhaben | Warum | Aufwand |
|---|---|---|---|
| B1 | **Hochverfügbarkeit**: zweite Instanz + gemeinsame DB/Spool-Volume, Health-basiertes Umschalten, Runbook | Ein einzelner Broker ist ein Single Point of Failure für alle Modalitäten | groß |
| B2 | ~~Backup-Automatik~~ — **erledigt**: `deploy/backup.sh` (beide Datenbanken, Spool, `.env`, Prüfungen) + `deploy/backup-roundtrip-test.sh` (sichern → zerstören → wiederherstellen → prüfen), läuft bei jedem `./test-stack.sh` | — | ✅ |
| B3 | **Betriebshandbuch/Runbook**: „Modalität sieht nichts", „PACS nimmt nicht an", „RIS bekommt keine Rückmeldung" mit Befehlen | Verkürzt die Fehlersuche im Dienst | klein |
| B4 | ~~Monitoring-Vorlage~~ — **erledigt**: `deploy/monitoring/prometheus-rules.yml` (17 Regeln) + `grafana-dashboard.json` (14 Panels), durch `test_monitoring_config.py` an die echten Metriknamen gebunden | — | ✅ |
| B5 | **Lasttest** (100+ Modalitäten, 20 000 Spool-Einträge, 100 000 Cache-Einträge) mit dokumentierten Grenzwerten | Belegt die Dimensionierung für die Beschaffung | mittel |
| B6 | **Selbstüberwachung**: Broker prüft seine eigene DB/Spool-Platte und meldet es über die Alarmierung | „Platte voll" fällt heute erst beim Schreiben auf | klein |

## 4. Beschaffung und Compliance

| # | Vorhaben | Warum | Aufwand |
|---|---|---|---|
| C1 | **CE-Kennzeichnung nach MDR** als Medizinprodukt, IEC 62304-Lebenszyklus, ISO 14971-Risikodossier | Ohne das ist kein Verkauf/Einsatz als Medizinprodukt in der EU möglich — der eigentliche Unterschied zu kommerziellen Produkten | organisatorisch, groß |
| C2 | **Validierungsdokumentation** (Installations-, Funktions-, Regressionstest mit Abzeichnung) auf Basis der vorhandenen Suiten | Krankenhäuser verlangen die Abnahme dokumentiert | klein–mittel (Tests existieren) |
| C3 | **Cybersecurity-Dokumentation** (IEC 81001-5-1): Bedrohungsmodell, Härtung, Patchprozess | Wird in Ausschreibungen zunehmend gefordert | mittel |
| C4 | **Support-/SLA-Konzept**, Schulungsunterlagen | Teil jeder Ausschreibung | organisatorisch |

## 5. Empfohlene Reihenfolge

1. **B2 + B3 + B4** (klein, sofort nutzbar: Backup, Runbook, Alarme) — macht den
   Betrieb belastbar, ohne neue Funktion.
2. **F6 + F7 + B6** (klein): schnell sichtbarer Nutzen für Betreiber.
3. **F1 (MRN-Merge)** — die größte verbleibende funktionale Lücke gegenüber
   kommerziellen Produkten.
4. **C2 + C3** — Vorbereitung der Beschaffung, auf den vorhandenen Tests.
5. **B1 (Hochverfügbarkeit)**, dann **F2**, **F5**.
6. **F3/F4** nur, wenn ein konkreter Kunde sie verlangt.

## 6. Was bewusst außerhalb bleibt

Prefetch von Voraufnahmen, Transkodierung, De-Identifikation (PS3.15),
Storage Commitment, C-MOVE/C-GET, Print — das sind Aufgaben von PACS, VNA oder
einem Router. Sie sind im
[Conformance Statement §9](dicom-conformance-statement.md) mit Begründung
aufgeführt.
