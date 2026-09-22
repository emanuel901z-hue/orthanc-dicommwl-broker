# Beispielnachrichten für die externe Validierung (E1, Teil 2)

Diese Dateien sind **Beispielnachrichten**, mit denen eine *fremde* Validierung
(Gazelle HL7 Validator / EVSClient, oder ein anderer Validator) geprüft werden
kann — die Kodierung unserer Schnittstellen, nicht unser eigener Parser.

| Datei | Nachricht | Erwartung |
|---|---|---|
| `order-orm-o01.hl7` | `ORM^O01` — Auftrag (klassisch) | **angenommen**: lokaler Arbeitslisten-Eintrag |
| `order-omg-o19.hl7` | `OMG^O19` — Auftrag (General Clinical Order) | **angenommen**: derselbe Pfad wie ORM |
| `order-omi-o23.hl7` | `OMI^O23` — **Imaging Order** (die moderne Radiologie-Auftragsnachricht) | **angenommen**: derselbe Pfad wie ORM |
| `patient-adt-a08.hl7` | `ADT^A08` — Patientendaten aktualisiert | **angenommen**: Demografie der eigenen Einträge |
| `patient-adt-a31.hl7` | `ADT^A31` — Update Person Information (Variante von A08) | **angenommen**: wie A08 |
| `patient-adt-a24.hl7` | `ADT^A24` — Verknüpfung | **angenommen**: beide IDs bleiben gültig |
| `patient-adt-a40.hl7` | `ADT^A40` — Zusammenführung | **angenommen**: alte ID entfällt |
| `patient-adt-a47.hl7` | `ADT^A47` — Verknüpfung zurücknehmen | **angenommen** |
| `report-oru-r01.hl7` | `ORU^R01` — **Befundmeldung** | **abgelehnt** (HTTP 422 / MLLP-NAK): ein Befund darf keinen Auftrag erzeugen |

## Wie man sie prüft

**Gegen den eigenen Broker** (Verhalten, nicht Kodierung):

```bash
curl -s -X POST 'http://127.0.0.1:18081/api/v1/hl7/orm?dry_run=true' \
  -H 'Content-Type: text/plain' --data-binary @order-orm-o01.hl7 | python3 -m json.tool
```

**Gegen einen fremden Validator** (Kodierung): Die Nachrichten in den
Gazelle-HL7-Validator bzw. EVSClient hochladen (siehe `docs/interop.md` §4) und
den Prüfbericht ablegen. Erwartung: die Auftrags- und Patienten-Ereignisse sind
gültiges HL7 v2.5 für den jeweiligen IHE-Anwendungsfall; die `ORU^R01` ist
gültiges HL7, aber **kein** Auftrag — sie gehört auf den Befundpfad, nicht in die
Arbeitsliste.

> Die Beispiele enthalten **fiktive** Patientendaten (`Muster^Max`,
> `P-1001`). Wer sie gegen einen öffentlichen Validator schickt, sollte sie
> vorher durch eigene Testdaten ersetzen — der Validator ist fremde
> Infrastruktur, und Patientendaten gehören dort nicht hin.
