# Lasttest — Methode, Messwerte, Grenzen

Stand: 22.09.2026 · Ergebnis von **B5** aus [`next-steps.md`](next-steps.md)

Dieses Dokument beantwortet die Beschaffungsfrage „für wie viele Modalitäten
reicht das?" — und dokumentiert, was der Lasttest dabei gefunden hat. Der Test
misst das **laufende System über die Leitung** (DIMSE + REST), nicht Unit-Code:
nur so kommt heraus, wie sich der Broker unter Nebenläufigkeit *verhält*.

> **Die Zahlen sind ein Ausgangswert, keine Zusage.** Sie stammen von einem
> Entwicklungsrechner mit 8 Kernen und 16 GB, auf dem parallel der reguläre
> Stack lief (Docker, dieselbe Maschine). Für eine Dimensionierung auf der
> Zielhardware wird derselbe Harness dort erneut gefahren — das Verhalten
> (Verhältnisse, Grenzen, Fehlerbilder) ist übertragbar, die absoluten
> Millisekunden nicht.

## 1. Harness

`mwl-broker/scripts/loadtest.py` — zwei Szenarien:

```bash
# C-FIND: N Modalitäten-Clients × M Abfragen mit wählbarer Nebenläufigkeit
python3 mwl-broker/scripts/loadtest.py cfind --host 127.0.0.1 --port 11123 \
    --api http://127.0.0.1:19081 --clients 40 --queries 5 --concurrency 10 \
    --json /tmp/cfind.json

# C-STORE: N Instanzen (füllt den Spool, wenn das Ziel nicht erreichbar ist)
python3 mwl-broker/scripts/loadtest.py cstore --host 127.0.0.1 --port 11123 \
    --api http://127.0.0.1:19081 --instances 200 --concurrency 8 --payload-kb 64
```

Beide melden Latenz-Perzentile (p50/p95/p99/max), Durchsatz, Fehlerbilder und —
während der Last — die Antwortzeiten der **Monitoring-Endpunkte**. Das ist die
Frage, die der DB-Pool-Vorfall aufgeworfen hat: bleibt die Oberfläche
antwortfähig, während der DIMSE-Pfad arbeitet?

Gemessen wird gegen den **isolierten Test-Stack** (`test-stack.sh`, Projekt
`mwl-test`, Ports 19xxx), nicht gegen eine Anlage im Betrieb: der Lasttest füllt
Spools und schreibt Daten.

## 2. Messwerte (Entwicklungsrechner, 8 Kerne)

### 2.1 C-FIND, zwei gesunde Quellen (je 3 Antworten)

| Nebenläufigkeit | Abfragen | Fehler | Durchsatz | p50 | p95 | max | REST p95 |
|---|---|---|---|---|---|---|---|
| 5 | 200 | 0 | 4,4 q/s | 669 ms | 3 486 ms | 6 129 ms | 19 ms |
| 10 | 200 | 0 | 6,2 q/s | 1 105 ms | 3 949 ms | 5 161 ms | 59 ms |
| 20 | 200 | 81 (Abweisung) | 5,7 q/s | 3 339 ms | 5 910 ms | 6 546 ms | 111 ms |
| 40 | 200 | 182 (Abweisung) | 3,3 q/s | 5 398 ms | 5 480 ms | 5 495 ms | 269 ms |

### 2.2 Wo die Zeit steckt

Aufgeschlüsselt im Container gegen dieselbe Quelle (eine Assoziation):

| Phase | Dauer |
|---|---|
| Association aufbauen (`associate`) | **6 ms** |
| **C-FIND-Runde** (Abfrage + Antworten) | **90 ms** |
| Association abbauen (`release`) | 13 ms |

Der Broker protokolliert seine eigene Aggregationsdauer (`duration_ms` im
Query-Log) — sie folgt der Zahl der Quellen, nicht der Nebenläufigkeit:

| Situation | Broker-intern p50 |
|---|---|
| sequenziell, 1 Quelle | 122 ms |
| 1 Quelle, 10 gleichzeitig | 550 ms (max 4,2 s) |
| 2 Quellen, 10 gleichzeitig | 1 021 ms |

Zum Vergleich: derselbe Mock-RIS allein, direkt abgefragt, antwortet mit
**99 ms pro Abfrage** (p50) — dieselben ~90–100 ms pro C-FIND. Die Kosten sitzen
also in der DIMSE-Runde selbst, nicht in der Aggregation, den Datenbank-Schreib-
vorgängen oder der Antwortaufbereitung.

### 2.3 Der Cache kostet ein Viertel

| Konfiguration | Durchsatz |
|---|---|
| 2 Quellen, 10 gleichzeitig, Cache an | 6,2 q/s |
| 2 Quellen, 10 gleichzeitig, Cache aus | 8,4 q/s |

Der Snapshot-Schreibvorgang ist ~25 % des Durchsatzes wert. Bewusst so: der
Cache ist die Ausfallbrücke.

## 3. Was der Lasttest gefunden hat

### 3.1 Zwei echte Fehler unter Nebenläufigkeit (behoben)

Beide sind Read-then-Insert-Races — geprüft, dann eingefügt. Bei zehn
gleichzeitigen Abfragen kollidieren sie:

1. **`source_breaker`**: zwei Threads legen dieselbe Breaker-Zeile an →
   `IntegrityError: source_breaker_pkey`. Die Exception lief aus dem
   C-FIND-Handler heraus, pynetdicom antwortete der Modalität **`0xC311`** —
   eine Arbeitslisten-Abfrage, die der Broker hätte beantworten können, kam als
   Fehler zurück.
2. **`worklist_cache`**: zwei Threads schreiben denselben Snapshot →
   `IntegrityError: uq_cache_source_item`. Eine **erfolgreiche** Quellantwort
   wurde dadurch als Fehler protokolliert.

Behoben über `db.upsert` (`INSERT … ON CONFLICT DO UPDATE`, Postgres und SQLite
gleich): der zweite Schreiber aktualisiert die Zeile. Der Breaker-Zähler wird
jetzt **von der Datenbank** erhöht (`failures = failures + 1`) — sonst ginge
unter einem Ausfall-Burst ein Inkrement verloren und der Breaker öffnete später
als eingestellt. Regressionstests: `tests/test_concurrency.py` (7).

Nachweis: dieselbe Messreihe danach — **0 `0xC311`, 0 Handler-Exceptions, 0
UniqueViolations** im Log (vorher: 2 Fehler schon bei Nebenläufigkeit 5).

### 3.2 Das Assoziationslimit ist die harte Grenze (nicht behoben, bewusst)

`max_associations` (Default **20**) ist eine **Abweisung**, keine Warteschlange:
oberhalb von 20 gleichzeitigen Verbindungen antwortet der Broker nicht mehr
„später", sondern lehnt ab. Bei 40 gleichzeitigen Clients kamen 182 von 200
Abfragen als „association rejected" zurück.

Für die Dimensionierung heißt das: **es kommt nicht darauf an, wie viele
Modalitäten konfiguriert sind, sondern wie viele gleichzeitig verbunden sind.**
Ein Haus mit 100+ Geräten, die um 8:00 alle ihre Arbeitsliste holen, trifft
dieses Limit — die Geräte müssen wiederholen, oder das Limit muss steigen.
Empfehlung: `BROKER_MAX_ASSOCIATIONS` auf die Zahl der *gleichzeitig* arbeitenden
Konsolen setzen (jede Abfrage ist ~0,1 s, die Verbindungen sind also teuer im
Aufbau, nicht im Halten) — und das im Conformance Statement nennen, weil AET und
Port dort schon stehen.

### 3.3 Der Mock-RIS war selbst der Flaschenhals

`mock_ris.py` nutzte pynetdicom's Default `maximum_associations = 1`: das
Demo-RIS bediente **eine** Verbindung gleichzeitig und wies den parallelen
Fan-out des Brokers ab (21 von 200 Abfragen bei Nebenläufigkeit 10 kamen durch).
Ein Lasttest gegen einen solchen Upstream misst den Mock, nicht den Broker.
Behoben: `--max-associations` (Default 20), gemessen danach 200/200.

**Lehre für jede künftige Messung:** erst die Gegenstelle messen, dann den Broker.

## 4. Offene Frage

Warum eine C-FIND-Runde ~90 ms kostet, ist **nicht** isoliert. Ausgeschlossen
ist: die Aggregation, die Datenbank-Schreibvorgänge, die Antwortaufbereitung, die
Timeout-Einstellungen (A/B mit/ohne `acse_timeout`/`dimse_timeout`/
`network_timeout`: kein Unterschied) und der Hostname (IP-Quelle: gleiche
Latenz). In Frage kommen der DIMSE-Client in pynetdicom oder die Gegenseite —
und genau das lässt sich ohne Fremdsystem nicht entscheiden. Es gehört damit zu
**E1** (Interop-Nachweis): ein fremdes RIS oder eine echte Modalität auf der
anderen Seite beantwortet die Frage und ist ohnehin überfällig.

Kandidat für die Optimierung danach: **Assoziationen wiederverwenden** statt je
Abfrage eine neue aufzubauen (der Aufbau kostet 6 ms, die Runde 90 ms — der
Gewinn läge also in der Runde, nicht im Aufbau).

## 5. Was nicht getestet wurde

Ehrlich benannt, damit die Zahlen nicht mehr versprechen als sie zeigen:

- **Keine echten Modalitäten und kein fremdes RIS** — alle Gegenstellen sind
  unser eigener Code (siehe E1). Matching-Feinheiten, andere Timeouts und
  herstellerspezifische Identifier sind damit ungeprüft.
- **Kein Spool am Kapazitätslimit** (20 000 Einträge / 10 GiB). Gemessen wurde
  der Durchsatz der Annahme, nicht das Verhalten bei vollem Budget; die
  Abweisungssemantik ist separat getestet (`tests/test_spool.py`).
- **Keine Bilddaten** in den C-STORE-Instanzen (Metadaten + konfigurierbares
  Pixel-Padding): der Broker fasst Pixel nicht an, aber Netzwerk- und
  Schreibzeit echter Bilder sind nicht enthalten.
- **Keine Dauerlast** (Minuten bis Stunden) — gemessen wurden Bursts. Für
  Speicher-/Verbindungs-Leaks bräuchte es einen Soak-Test.
- **Kein HA-Szenario im Lasttest** — die Nebenläufigkeit zweier Instanzen
  prüft `deploy/ha-smoke.sh` (Claim, keine Doppelzustellung), aber nicht unter
  Last. Siehe [`ha.md`](ha.md).
