# MFA-Testumgebung: der Broker aus Sicht eines unbedarften Anwenders

**Szenario:** Eine MFA, die das Tool noch nie gesehen hat, soll den Broker von
vorne bis hinten einrichten und bedienen. Die Testumgebung macht genau das, was
ein Neuling tut: Sie tippt Unsinn, speichert zu früh, korrigiert, geht im
Browser zurück, lädt neu — und prüft, ob die Oberfläche das abfängt, erklärt und
die Eingaben behält.

**Aufruf:**

```bash
./mfa-test.sh            # Test-Stack hochfahren + Journey (Desktop + Mobile) + Bericht
./mfa-test.sh --keep     # Stack danach laufen lassen
```

**Ergebnis:** `orthanc-explorer-3-usable/e2e/stack/screenshots/mfa-journey-*.md`
(wird während des Laufs geschrieben, ein Abbruch verliert also nichts).
Der Bericht ist zugleich das Protokoll: pro Prüfung „OK" oder „**LÜCKE**" mit
dem beobachteten Text.

---

## 1. Was die Journey durchspielt

| Teil | Schritte | Prüfungen |
|---|---|---|
| 1 (Desktop + Mobile) | Orientierung, Quelle anlegen mit typischen Anfängerfehlern, korrigieren, speichern, doppelte AET, **Zurück-Taste**, **F5**, lokale Worklist | 20 |
| 2 (Desktop) | Routing-Regel ohne Auswahl und als Duplikat, Stationsregel, die alles verbirgt, Einstellungen (Buchstaben, Bereich, Speichern) | 6 |

Die Fehler, die die Journey absichtlich macht:

- sofort speichern, ohne etwas auszufüllen
- AE-Titel in Kleinbuchstaben und mit Sonderzeichen (`ct 01!`)
- Buchstaben in ein Zahlenfeld (Port, Intervall)
- Port außerhalb 1–65535
- Adresse als Satz („ris server 1"), mit `http://`, mit Pfad
- zwei Knoten mit derselben AE-Titel
- eine zweite Regel für dieselbe Quelle+Ziel
- eine Stationsregel, die alle Quellen verbirgt
- Pflichtfeld (Zugangsnummer) leer lassen
- Formular halb ausfüllen, dann **Zurück** bzw. **F5**
- eine Zahleneinstellung außerhalb des erlaubten Bereichs

---

## 2. Befunde: was beim Testen durchfiel und behoben wurde

| # | Befund | Wirkung für den DAU | Fix |
|---|---|---|---|
| 1 | **Zurück-Taste und F5 löschten das ganze Formular.** Ein halb ausgefülltes Formular war nach einem Reload oder einem Ausflug in die Browser-Historie leer. | Der Klassiker: 12 Felder getippt, einmal zurück, alles weg. | Entwurf je Formular in `sessionStorage` (`use-form-draft.ts`): beim Öffnen wiederhergestellt, solange getippt, verworfen nach dem Speichern oder auf Wunsch. Zusätzlich `beforeunload`-Warnung, solange etwas ungespeichert ist. **Verifiziert:** Feld „host" überlebt Zurück (`10.0.1.50`) und F5 (`10.0.1.51`). |
| 2 | **`GET /api/v1/sources` antwortete mit 500** — die Liste war leer, obwohl Einträge existierten. | Der Anwender sieht „nichts da" und legt alles doppelt an. | Ursache war meine eigene Eingabe-Prüfung: sie lief auch auf **Antwort**-Modelle und scheiterte an Altdaten. Prüfung liegt jetzt in der API-Schicht und gilt nur für Eingaben (`validate_node_fields`, `_check_node`). **Verifiziert:** Liste 200, Unsinn 422. |
| 3 | **Erfolgsmeldungen gab es nur bei Einstellungen.** Quelle/Ziel/Regel/Station/Spool/Lokal speicherten ohne Rückmeldung. | Der Anwender klickt nochmal (Doppelanlage) oder zweifelt. | Alle Schreib-Hooks melden jetzt „Gespeichert." (`successMessage`). **Verifiziert:** Toast 400 ms nach dem Speichern. |
| 4 | **Feldmeldungen waren nicht als Fehler ausgezeichnet und kamen erst nach dem Absenden.** | Screenreader lesen sie nicht vor; der Anwender tippt weiter ins Leere. | `role="alert"` an allen Feldmeldungen, Hinweise erscheinen live beim Tippen, leeres Pflichtfeld („Pflichtfeld") wird von unsinnigem Inhalt („nur die Adresse …") unterschieden, die AET-Meldung nennt das Feld. |
| 5 | **Unsinnige Adressen und AETs akzeptierte der Server.** „ris server 1" oder `ris_a` landeten in der Konfiguration — die Quelle kann nie funktionieren. | Stille Fehlkonfiguration, die erst am Gerät auffällt. | Server prüft jetzt Host (kein Schema, keine Leerzeichen/SchRägstriche, gültiger Name/IP) und AET (1–16 Zeichen, A–Z 0–9 _ -, Großbuchstaben) mit Klartext-Meldung. **Verifiziert:** 422. |

---

## 3. Was die Journey bestätigt (alles OK)

| Frage aus dem Auftrag | Ergebnis |
|---|---|
| Fängt das Programm falsche Eingaben vorher ab? | **Ja.** Buchstaben in Zahlenfeldern werden gar nicht angenommen; Port/Intervall außerhalb des Bereichs werden vor dem Senden gemeldet; Datum/Uhrzeit sind Picker; AET wird automatisch groß geschrieben und geprüft; UID auf Ziffern/Punkte |
| Gibt es Dialoge, die den Fehler für einen DAU verständlich benennen? | **Ja.** „Pflichtfeld", „AET: 1–16 Zeichen, nur A–Z 0–9 _ - (Großbuchstaben)", „Nur die Adresse eingeben: keine Leerzeichen, keine Schrägstriche, kein http://.", „Erlaubt: 5 bis 3600", „Modus allow ohne Quelle verbirgt alle Quellen — diese Konsole würde eine leere Arbeitsliste erhalten" |
| Kann man nach einem Fehler sinnvoll wiederholen/korrigieren? | **Ja.** Der Dialog bleibt mit allen Eingaben stehen, die Meldung verschwindet nach der Korrektur, Speichern geht durch; danach erscheint die Erfolgsmeldung |
| Bleiben Masken bei Zurück/Browser-Tasten erhalten? | **Ja** (nach Fix 1) — plus Warnung, wenn man die Seite mit ungespeicherten Eingaben verlassen will |
| Werden gefährliche Konfigurationen vor dem Speichern erklärt? | **Ja.** Stationsregel, die alles verbirgt; doppelte AET; doppelte Quelle+Ziel (Speichern gesperrt); Standard-Ziel-Löschung (in `broker-config.spec.ts`) |
| Sieht der Anwender, dass etwas gespeichert wurde? | **Ja.** Toast „Gespeichert." + die Zeile erscheint in der Liste |

---

## 4. Umgesetzte Empfehlungen

| Empfehlung | Umsetzung |
|---|---|
| Entwürfe auch für die kurzen Regel-/Transform-Formulare | **Umgesetzt.** Routing- und Transform-Regeln nutzen jetzt denselben Entwurfsmechanismus (`rule-*`, `transform-*`), inklusive Laden beim Öffnen und Verwerfen nach dem Speichern. |
| Entwurf nach einer Stunde verwerfen | **Umgesetzt.** Der Entwurf liegt als `{value, savedAt}` in `sessionStorage`; `loadDraft` ignoriert und entfernt alles, was älter als `DRAFT_TTL_MS` (1 h) ist — und auch Altbestände aus früheren Versionen. |
| „Was ist das?"-Hilfe je Seite | **Umgesetzt.** Jede der zehn Broker-Seiten (inklusive Übersicht) hat einen „Was ist das?"-Knopf mit drei Abschnitten: *Worum geht es?*, *Was trage ich ein?*, *Was geht am häufigsten schief?* — deutsch und englisch, mit den konkreten Fallstricken (Adresse als Satz, `allow` ohne Quelle, Standard-Ziel löschen …). |
| Mobile: Regel-/Transform-Dialoge | Teil 1 der Journey läuft mobil grün; die Select-lastigen Dialoge werden zusätzlich über `verify-ui.cjs` bei 375 px geprüft (inklusive der neuen Hilfe). |

---

## 5. Test-Stack-Hinweis

`mfa-test.sh` benutzt **denselben** isolierten Stack wie `test-stack.sh`
(Projekt `mwl-test`, eigene Ports, `.env.test`) und räumt ihn am Ende wieder ab.
Wichtig: Nach Änderungen am Frontend/Backend muss der Stack **neu gebaut**
werden — ein `up -d` ohne `--build` fährt sonst die alten Images und der Bericht
zeigt Fehler, die es im Code nicht mehr gibt (genau das ist beim ersten Lauf
passiert und hat zwei vermeintliche Befunde erzeugt).
