# Hochverfügbarkeit (B1)

Stand: 22.09.2026 · Ergebnis von **B1** aus [`next-steps.md`](next-steps.md)

Ein einzelner Broker ist ein Single Point of Failure für **alle** Modalitäten des
Hauses. Dieses Dokument beschreibt, was hier unter Hochverfügbarkeit verstanden
wird, was geteilt wird und was nicht, wie der Betrieb aussieht — und wo die
Grenzen liegen.

## 1. Was „hochverfügbar" hier heißt — und was nicht

**Zwei Instanzen dürfen gleichzeitig arbeiten; keine Arbeit darf doppelt
passieren.** Es gibt bewusst **keine Leader-Wahl**: Der Broker hält keinen
Zustand, der einen einzelnen Eigentümer braucht. Breaker, Worklist-Cache,
Spool-Metadaten, Routing-Herkunft und Änderungsprotokoll liegen in der
Datenbank; die DIMSE-Listener sind unabhängig. Die ehrliche Konstruktion ist
deshalb nicht „einer aktiv, einer wartet", sondern:

| Frage | Antwort |
|---|---|
| Dürfen beide Instanzen C-FIND beantworten? | **Ja.** Beide lesen dieselben Quellen und dieselbe Datenbank — die Antwort ist identisch. |
| Dürfen beide spoolen? | **Ja.** Der Spool liegt auf einem gemeinsamen Volume, die Metadaten in der gemeinsamen Datenbank. |
| Dürfen beide zustellen? | **Ja — aber nur mit Claim.** Genau das verhindert Doppelzustellungen (§3). |
| Wer ist „der" Broker für die Modalität? | Die Instanz, die die Modalität gerade erreicht (§4). Der Broker kann das nicht entscheiden. |

Was das **nicht** ist: kein Cluster-Manager, kein Quorum, kein automatisches
Umschalten von IP-Adressen. Das gehört auf die Netzwerkebene (§4).

## 2. Was geteilt wird — und was pro Instanz bleibt

| Zustand | Wo | Warum |
|---|---|---|
| Quellen, Ziele, Regeln, Stationsregeln, Transforms | Datenbank (**geteilt**) | Konfiguration ist für alle Instanzen dieselbe |
| Circuit-Breaker je Quelle | Datenbank (**geteilt**) | Eine tote Quelle ist für beide tot |
| Worklist-Cache | Datenbank (**geteilt**) | Ausfallbrücke — beide sehen denselben Snapshot |
| Routing-Herkunft (`seen_items`), MPPS-Schritte, Patienten-Zusammenführungen | Datenbank (**geteilt**) | Sonst routete die zweite Instanz anders als die erste |
| Spool-Metadaten (`store_spool`) | Datenbank (**geteilt**) | Inklusive Claim (§3) |
| **Spool-Payloads** | Volume (**geteilt — muss es sein**) | Die Datei liegt auf Platte; ohne gemeinsames Volume findet die zweite Instanz die Bilder nicht |
| Änderungsprotokoll, HL7-Log, Query-/Store-Log | Datenbank (**geteilt**) | Eine gemeinsame Geschichte |
| **Instanz-Heartbeat** (`broker_instance`) | Datenbank (**geteilt**) | Damit sich die Instanzen sehen (§5) |
| Echo-Zustand (`ECHO_STATUS`) | **Prozess** (pro Instanz) | Jede Instanz prüft ihre eigenen Verbindungen — zwei Instanzen melden dieselbe Quelle zweimal |
| Metrik-Zähler (Prometheus) | **Prozess** (pro Instanz) | Prometheus scrapt jede Instanz einzeln; Zähler werden **pro Instanz** summiert |
| DIMSE-Listener, MLLP-Listener | **Prozess** (pro Instanz) | Jede Instanz ist erreichbar, wer sie erreicht, wird bedient |

> **Die eine Falle:** zwei Instanzen auf einer Datenbank, aber **ohne**
> gemeinsames Spool-Volume. Dann findet die zweite Instanz die gepufferten
> Bilder nicht und macht sie zu Dead Letters. Die Health-Prüfung warnt bei
> mehreren aktiven Instanzen (`ha_multiple_instances`) — sehen kann der Broker
> das Volume nicht, prüfen muss es der Betreiber.

## 3. Der Spool-Claim — der Kern der Sache

Ohne Claim würden zwei Worker dieselbe Zeile ziehen und dasselbe Bild zweimal an
das PACS senden. Der Claim ist deshalb **atomar**:

```sql
UPDATE store_spool
   SET claimed_by = :instance, lease_until = now() + :lease
 WHERE id IN (SELECT id FROM store_spool
               WHERE status IN ('queued','failed')
                 AND (next_attempt_at IS NULL OR next_attempt_at <= now())
                 AND (lease_until IS NULL OR lease_until <= now())
               ORDER BY created_at, id
               LIMIT :n
               FOR UPDATE SKIP LOCKED)
 RETURNING id;
```

* `FOR UPDATE SKIP LOCKED` schickt die zweite Instanz an die **nächsten** Zeilen,
  statt sie warten zu lassen. SQLite kennt das nicht — dort serialisiert der
  Schreiber ohnehin, deshalb läuft dieselbe Anweisung auch in den Tests.
* Die **Lease** (`spool_lease_s`, Default 300 s) begrenzt, wie lange eine Instanz
  einen Eintrag halten darf. Muss über dem Store-Timeout der Ziele liegen.
* Läuft die Lease ab, ist der Eintrag wieder frei: **so kommt die Arbeit einer
  abgestürzten Instanz zurück in den Pool.**
* Nach jedem Ausgang (Erfolg, Fehler, Dead Letter) wird der Claim freigegeben.
* `forward()` prüft den Besitz: Wer einen Eintrag nicht beansprucht hat, fasst
  ihn nicht an — das schützt auch den „Alle erneut versuchen"-Knopf des
  Betreibers vor einem fremden Claim (und umgekehrt: der Knopf gibt eine
  veraltete Lease frei).

**Zustellsemantik: at-least-once, nie still verloren.** Stirbt eine Instanz
*zwischen* dem erfolgreichen Senden und dem Zurückschreiben, wird der Eintrag
nach Ablauf der Lease erneut zugestellt — das PACS bekommt dasselbe Bild
zweimal. Das ist der bewusste Kompromiss: ein Duplikat ist heilbar, ein
verlorenes Bild nicht. Der `is_duplicate`-Schutz am *Eingang* (die Modalität
wiederholt ihren C-STORE) bleibt davon unberührt.

## 4. Der Endpunkt — was der Broker nicht kann

AET und Port stehen im [Conformance Statement](dicom-conformance-statement.md):
die Modalitäten sind auf **einen** AET und **einen** Host konfiguriert. Diese
Adresse muss auf die aktive Instanz zeigen. Drei Wege, alle außerhalb des
Brokers:

| Weg | Wie | Anmerkung |
|---|---|---|
| **Schwebende IP** (keepalived, VRRP) | Die VIP wandert auf den Host der aktiven Instanz | Kein zusätzliches Gerät, aber Netzwerk-Konfiguration |
| **TCP-Load-Balancer** (HAProxy, nginx `stream`, Hardware-LB) | Der LB verteilt auf beide Instanzen; Health-Check auf `/healthz/ready` | Erlaubt auch „beide aktiv" — mit dem Claim ist das korrekt |
| **Zweiter AET** | Jede Instanz mit eigenem AET, Modalitäten doppelt konfiguriert | Nur für Geräte, die zwei Worklist-Quellen können — sonst nicht praktikabel |

`/healthz/ready` ist genau für diesen Health-Check gedacht: Es antwortet nur,
wenn die Instanz die Datenbank erreicht **und** ihr DICOM-Listener läuft. Eine
Instanz ohne Datenbank ist für den LB „krank" und wird nicht angesprochen.

## 5. Betrieb

```bash
# zweite Instanz starten (gemeinsame DB und gemeinsames Spool-Volume)
docker compose --profile ha up -d
# nur die zweite Instanz neu bauen
docker compose --profile ha up -d --build mwl-broker-b
# nachsehen, wer läuft
curl -s http://127.0.0.1:18081/api/v1/status | python3 -m json.tool   # instances
```

* Beide Instanzen erben **dieselbe Umgebung** (Anker `x-broker-environment` in
  `docker-compose.yml`) — unterschiedlich sind nur `BROKER_INSTANCE_ID` und die
  Host-Ports (`BROKER_B_*` in `.env`).
* Der **Instanzname** (`BROKER_INSTANCE_ID`) muss eindeutig und stabil sein: er
  steht im Claim und im Heartbeat. Ohne ihn wird `hostname:pid` benutzt — nach
  einem Container-Neustart ist das ein *anderer* Name, und die alte Zeile bleibt
  als „weg" stehen (bis sie aufgeräumt wird).
* In der UI zeigt die Karte **Broker-Instanzen** auf der Monitoring-Seite, wer
  sich wann zuletzt gemeldet hat. Die Health-Prüfung meldet
  `ha_multiple_instances` (mehrere aktiv) und `ha_instance_gone` (eine ist weg).

## 6. Nachweis

```bash
./deploy/ha-smoke.sh          # baut auf, prüft, räumt ab
./deploy/ha-smoke.sh --keep   # danach stehen lassen
```

Der Test bringt zwei Instanzen auf gemeinsamer DB und gemeinsamem Volume hoch,
legt 24 Instanzen in den Spool (Ziel absichtlich tot), biegt dasselbe Ziel auf
den erreichbaren Orthanc um und prüft dann:

| Prüfung | Ergebnis (Referenzlauf) |
|---|---|
| beide Instanzen melden sich mit eigenem Namen | `broker-a`, `broker-b`, beide aktiv |
| der Spool ist für beide **derselbe** | 24 Einträge, von beiden gesehen |
| jede Instanz wurde **genau einmal** zugestellt | 24 Zustellungen (12 + 12 auf beide Instanzen verteilt) |
| nichts verloren | Orthanc hat alle 24 |
| jeder Eintrag genau einmal beansprucht | Claims ≥ 24 (mehr nur bei Wiederholung nach Fehlversuch) |

Zusätzlich prüfen `tests/test_ha.py` (16 Tests) den Claim und den Herzschlag
ohne Docker, inklusive des entscheidenden Falls: zwei Worker laufen **gleichzeitig**
über dieselbe Warteschlange, und jedes Bild wird genau einmal zugestellt.

**Warum der HA-Test eigenständig läuft** (und nicht in `test-stack.sh` hängt): Er
braucht einen eigenen Stack mit dem Profil `ha` — also einen zweiten Broker auf
denselben Host-Ports, die der ephemere Test-Stack bereits belegt. Er startet
deshalb sein eigenes Projekt (`mwl-ha`) und räumt es wieder ab. Wer ihn in einer
Pipeline haben will, ruft ihn als eigenen Schritt auf; er braucht nur Docker und
ungefähr eine Minute.

**Was der Nachweis nicht zeigt:** keine echte VIP/kein LB (nur die zwei
Instanzen), kein Postgres-Failover, kein Netzwerkausfall zwischen den Instanzen.
Die Datenbank und das Spool-Volume bleiben eigene Single Points of Failure — HA
des Brokers ist nicht HA des Postgres.

## 7. Grenzen (ehrlich)

* **At-least-once** statt exactly-once (§3): ein Absturz im falschen Moment kann
  ein Duplikat erzeugen.
* **Kein Fencing:** eine Instanz, die nur „langsam" ist (z. B. einfriert, aber
  noch lebt), gibt ihre Lease erst nach Ablauf frei — bis dahin wartet der
  Eintrag.
* **Zwei Echo-Loops:** beide Instanzen prüfen alle Quellen und Ziele. Das
  verdoppelt den C-ECHO-Verkehr (harmlos, aber sichtbar im Netz).
* **Zwei Aufräum-Läufe:** Retention und Spool-Purge laufen auf beiden Instanzen.
  Die Löschungen sind idempotent, es passiert also nichts — nur doppelt.
* **Der Heartbeat ist eine Momentaufnahme:** „aktiv" heißt „hat sich innerhalb
  `ha_instance_timeout_s` gemeldet", nicht „ist gesund". Für Gesundheit ist
  `/healthz/ready` da.
* **Die Konfiguration ist geteilt** — eine Regeländerung wirkt sofort auf beide
  Instanzen (das ist gewollt, aber überraschend, wenn man es nicht weiß).
