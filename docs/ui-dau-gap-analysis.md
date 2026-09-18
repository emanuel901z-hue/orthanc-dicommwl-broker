# Gap-Analyse: DAU-Sicherheit der MWL-Broker-Oberfläche

**Gegenstand:** das gesamte Broker-UI in OE3 (`/broker`, `/broker/*`, Settings-Karten)
**Frage:** Wo kann ein durchschnittlicher Anwender (DAU, kein DICOM-/Netzwerk-Spezialist)
etwas falsch eingeben, etwas Wichtiges übersehen — und erfährt er es?
**Stand:** Sprint 8 (RBAC/Retention) — alle Broker-Funktionen umgesetzt

---

## 1. Vorgehen

Zwei Quellen, damit die Befunde belegbar sind:

1. **Code-Review** aller Broker-UI-Dateien (`src/features/broker/**`, 5 584 Zeilen
   Produktivcode ohne Tests): Formulare, Dialoge, Fehlerpfade, Zustände.
2. **Live-Prüfung** im laufenden Stack mit Chromium (Desktop 1280×900, Mobil
   375×812, Locale `de-DE`): echte Eingaben, echte Requests, gemessene
   Geometrie/DOM. Die Live-Messungen sind unten mit „gemessen" markiert.

Schweregrade:

| Grad | Bedeutung |
|---|---|
| **P1** | Der DAU kann etwas kaputt machen, etwas geht still schief, oder eine Aufgabe ist gar nicht erfüllbar |
| **P2** | Reibung/Umwege, Missverständnis möglich, aber korrigierbar |
| **P3** | Kosmetik, Konsistenz, Barrierefreiheit, Komfort |

---

## 2. Zusammenfassung

**Positiv:** Die Broker-Oberfläche ist überdurchschnittlich DAU-freundlich
aufgebaut — überall Bestätigungsdialoge mit benannter Konsequenz, Pflicht-
Begründung beim Verwerfen, Trockenlauf bei Import/HL7/Simulation, ein
Health-Panel mit Deep-Links ins betroffene Formular, Mobile-Cards statt
abgeschnittener Tabellen, klare Empty-States und Erklärtexte unter fast jedem
Feld.

**Die drei wichtigsten Lücken:**

| # | Befund | Grad |
|---|---|---|
| 1 | **Einstellungen schlagen fehl, ohne dass es jemand sieht.** Alle Nicht-Bool-Settings (Seite *Broker settings* sowie die Karten TLS/ATNA/Alerting) werden als **Freitext ohne Typ** gerendert; der Fehler der Server-Validierung (422) wird **nirgends angezeigt** (gemessen: „abc" für `echo_interval_s` → keine Meldung, Feld behält „abc"). | **P1** |
| 2 | **Der Dialog „Lokale Worklist" ist auf dem Handy nicht bedienbar.** Kein `max-h`/`overflow` (anders als alle anderen Dialoge): gemessen 1 282 px hoch bei 812 px Viewport, erstes Feld bei y = −62, Speichern-Button bei y = 942, **nicht scrollbar**. | **P1** |
| 3 | **Gefährliche Fehlkonfiguration ohne Warnung:** eine Stationsregel mit Modus `allow` und **leerer** Quellenliste verbirgt *alle* Quellen — die Konsole sieht eine leere Arbeitsliste. Die UI warnt nicht. | **P1** |

---

## 3. Befunde im Detail

### A. Rückmeldung — stilles Scheitern

| ID | Befund | Beleg | Auswirkung | Empfehlung |
|---|---|---|---|---|
| A1 | **Kein Fehlerfeedback bei Einstellungs-Writes.** `SettingRow` ruft `setValue.mutate` und rendert nur `pending`, nie `error`. Gleiches Muster in `TlsCard`, `AtnaCard`, `NotificationsCard`. | `pages/BrokerSettingsPage.tsx:58–70` (Input ohne `type`, kein Fehlerblock); gemessen: `echo_interval_s="abc"` → keine sichtbare Meldung, Feld behält den Wert | Der Anwender glaubt, gespeichert zu haben. Besonders kritisch bei Zahlen/Pfaden/URLs — die Wirkung tritt nie ein, ohne Hinweis | Fehlerblock (`role="alert"`) je Setting + Karte, wie in den Dialogseiten bereits üblich |
| A2 | **Kein Erfolgsfeedback.** Kein Toast/„Gespeichert"-Hinweis im gesamten Broker-UI (0 Treffer für `toast`). | Code-Review; sichtbar auch live: nach dem Speichern ändert sich nur der Button-Zustand | Der DAU fragt sich, ob der Klick gewirkt hat — typischer Auslöser für Doppelklicks | Toast oder Inline-„Gespeichert" mit Zeitstempel |
| A3 | **Validierungsfehler erst nach dem Absenden** (Transforms-Tag, Case-Check, Stations-AET): keine Live-Prüfung. | `components/OperationsEditor.tsx` (nur `placeholder`), `pages/TransformsPage.tsx:413` (Serverfehler erst nach Submit); gemessen: ungültiger Tag `0010-0010` → keine Inline-Meldung | Umweg: erst ausfüllen, absenden, Fehler lesen, korrigieren | Feld-Prüfung beim Verlassen (`onBlur`) mit derselben Regel wie der Server |

### B. Eingabevalidierung — was man falsch eingeben kann

| ID | Befund | Beleg | Auswirkung | Empfehlung |
|---|---|---|---|---|
| B1 | **Lokale Worklist: 13 Freitextfelder**, darunter Datum, Uhrzeit, Geburtsdatum, Modalität, Station-AET, SPS-Status, Study-UID. Kein Datums-/Zeit-Picker, kein Format-Hinweis, keine Prüfung. | `pages/LocalWorklistPage.tsx:325–338` (alle Felder als `<Input>` ohne `type`) | Ein Tippfehler (z. B. `17.09.2026` statt `2026-09-17`) führt dazu, dass der Eintrag **still nie** in einer C-FIND-Antwort auftaucht — der Notfall wäre nicht sichtbar | `type="date"`/`type="time"`, Auswahl für Modalität/SPS-Status/Sex, AET- und UID-Musterprüfung |
| B2 | **Zahlenfelder ohne Grenzen.** 10 `type="number"`-Felder, nur 4 mit `min`; u. a. TLS-Port, Zertifikats-Gültigkeit, Alerting-Intervall, Prioritäten. | `components/TlsCard.tsx:312,385`; `pages/StationsPage.tsx:320`; `pages/RulesPage.tsx:317` | Werte außerhalb des erlaubten Bereichs werden erst vom Server abgewiesen — und bei Settings unsichtbar (siehe A1) | `min`/`max` aus der Server-Range spiegeln, plus Hinweistext |
| B3 | **Einstellungen ohne Typ.** Auch Integer-Settings rendern als Textfeld. | `pages/BrokerSettingsPage.tsx:58` | „30 Tage" als „3o" ist nicht unterscheidbar von einer gültigen Eingabe | `type="number"` + `min`/`max` aus der API-Beschreibung |
| B4 | **Pfade, URLs, AETs ohne Musterprüfung** (TLS-Zertifikatspfade, ATNA-Host/Port, Webhook-URL, Stations-AET). Serverseitig validiert (`path`/`url`/`enum`), clientseitig frei. | `components/TlsCard.tsx`, `components/AtnaCard.tsx`, `components/NotificationsCard.tsx` | Fehleingaben werden erst spät erkannt (kombiniert mit A1 sogar gar nicht sichtbar) | Client-Regeln aus denselben Konstanten wie der Server |
| B5 | **Doppelte Knoten/AET-Kollisionen** werden nicht im Formular geprüft. | `components/NodeFormDialog.tsx:72–82` prüft Format, nicht Eindeutigkeit; Health-Panel meldet Kollisionen erst danach | Zwei Quellen mit derselben AET → schwer zu findende Fehlkonfiguration | Hinweis beim Tippen („diese AET ist bereits vergeben") |

### C. Gefährliche Konfigurationen ohne Warnung

| ID | Befund | Beleg | Auswirkung | Empfehlung |
|---|---|---|---|---|
| C1 | **Stationsregel `allow` mit leerer Quellenliste** verbirgt alle Quellen. Kein Hinweis im Dialog. | `pages/StationsPage.tsx:305–315` (Modus-Auswahl, keine Bedingung); Server-Semantik dokumentiert in `station_rules.py` | Eine Konsole sieht plötzlich **nichts** mehr — der Betrieb sucht am Gerät statt in der Regel | Warnhinweis im Dialog („verbirgt alle Quellen") + Health-Finding |
| C2 | **Löschen des Standard-Ziels** wird wie jedes Ziel bestätigt („abhängige Regeln werden entfernt"), ohne den eigentlichen Effekt zu nennen. | `pages/TargetsPage.tsx:228` (generische Warnung) | Neue Bilder ohne Regel landen **nirgendwo** (unrouted) — das ist ein Betriebsausfall | Konsequenz explizit nennen („danach haben unzugeordnete Bilder kein Ziel") |
| C3 | **Prioritäts-Änderung ohne Wirkungserklärung.** Bei Regeln/Quellen/Zielen ist nicht sichtbar, was „Priorität 10 vs. 20" praktisch bedeutet. | `pages/RulesPage.tsx`, `SourcesPage.tsx`, `StationsPage.tsx` | Der DAU setzt Werte, ohne die Wirkung (Reihenfolge der Deduplizierung) zu kennen | Ein Satz Hilfe + Verweis auf die Fall-Prüfung |

### D. Mobile/Layout

| ID | Befund | Beleg | Auswirkung | Empfehlung |
|---|---|---|---|---|
| D1 | **Worklist-Dialog nicht scrollbar** (siehe Zusammenfassung). | gemessen 375×812: Höhe 1 282 px, `overflowY: visible`, erstes Feld y = −62, Speichern y = 942 | Aufgabe auf dem Handy **nicht erfüllbar** | `max-h-[90vh] overflow-y-auto` wie in allen anderen Dialogen |
| D2 | Dialoge ohne Höhenbegrenzung: nur `LocalWorklistPage` (D1) und `StationsPage` (`max-w-xl`, gemessen 746 px — grenzwertig, bei mehr Feldern kippt es) | `pages/LocalWorklistPage.tsx:317`, `pages/StationsPage.tsx:276` | Bei kleinen Geräten/Hochformat abgeschnitten | Einheitliche Dialog-Hülle mit Höhenbegrenzung |

### E. Konsistenz und Bedienfluss

| ID | Befund | Beleg | Auswirkung | Empfehlung |
|---|---|---|---|---|
| E1 | **Keine Warnung bei ungespeicherten Eingaben**: Esc/Klick daneben schließt jeden Dialog und verwirft die Eingabe. | kein `beforeunload`/Dirty-Guard in `NodeFormDialog`, `LocalWorklistPage`, `StationsPage` | Datenverlust bei versehentlichem Schließen | Dirty-Guard im Dialog („Änderungen verwerfen?") |
| E2 | **Gemischte Button-Beschriftungen** für dieselbe Aktion (`common.save` „Save" vs. `broker.save` „Speichern"). | `pages/TransformsPage.tsx:345`, `RulesPage.tsx:127`, `NodeFormDialog.tsx:99` … | In Sprachen, in denen nur einer der Schlüssel gepflegt ist, stehen zwei verschiedene Wörter für „Speichern" | Ein Schlüssel für „Speichern" |
| E3 | **Kein „Zurücksetzen" im Formular** (nur beim Bearbeiten eines Knotens existiert „Reset to default" für Settings). | `NodeFormDialog`, `LocalWorklistPage` | Falsche Eingaben muss man manuell rückgängig machen | „Zurücksetzen"-Knopf mit Bestätigung |
| E4 | **Kein Hinweis bei Duplikaten**: eine zweite Regel mit gleicher Quelle+Ziel ist erlaubt und sieht wie die erste aus. | `pages/RulesPage.tsx` | Doppelte Regeln → unklare Wirkung | Duplikat-Warnung beim Anlegen |
| E5 | **Fehlermeldungen sind nicht mit dem Feld verknüpft** (kein `aria-invalid`/`aria-describedby`). | 0 Treffer in `src/features/broker/**` | Screenreader liest den Fehler nicht am Feld | `aria-invalid` + `aria-describedby` setzen |

### F. Sprache

| ID | Befund | Beleg | Auswirkung | Empfehlung |
|---|---|---|---|---|
| F1 | **Broker-UI nur auf Deutsch und Englisch** — der Fork verspricht 9 Sprachen; `es, fr, ja, zh, ru, tr, ar` haben **0** Broker-Schlüssel. | Zählung der `broker`-Schlüssel je Locale: de/en 469, übrige 0; `fallbackLng: 'en'` ist gesetzt | Wer die UI z. B. auf Französisch stellt, sieht den Broker-Bereich auf Englisch (Fallback greift, kein Rohschlüssel) | Bewusst dokumentieren **oder** die wichtigsten ~40 Schlüssel übersetzen |

---

## 4. Was bereits gut ist (bewusst nicht als Lücke gezählt)

- **Löschen immer bestätigt**, mit benannter Konsequenz; Verwerfen von Spool-Einträgen
  verlangt eine Begründung; Cache leeren, Retention-Purge, Rollback und
  „Alle erneut senden" sind bestätigt.
- **Trockenlauf überall, wo es gefährlich wäre**: Konfigurations-Import (Pflicht-Dry-Run
  mit Diff), HL7-ORM („Prüfen" vs. „Anwenden"), Routing/Transform-Simulation,
  Stations-Vorschau, TLS-Endpunkt-Prüfung, ATNA-Beispielnachricht.
- **Health-Panel mit Deep-Links** ins betroffene Formular; Sidebar-Badge.
- **Lesemodus wird erklärt** (RBAC-Banner) statt 403er.
- **Mobile:** Tabellen werden unter `md` zu Cards; Actions bleiben erreichbar.
- **Empty-States** auf allen Listen, **Erklärtexte** unter fast jedem Feld,
  `role="alert"` für Dialogfehler, genau ein `<h1>` pro Seite.
- **Kein PHI in der Oberfläche**, wo es nicht hingehört (Cache/Logs zeigen Metadaten).

---

## 5. Vorschlag: Maßnahmen in einem Sprint („UI-Härtung")

| Prio | Maßnahme | Aufwand | Betroffene Dateien |
|---|---|---|---|
| 1 | Fehler- und Erfolgsfeedback für Einstellungs-Writes (A1, A2) | klein | `BrokerSettingsPage`, `TlsCard`, `AtnaCard`, `NotificationsCard` |
| 2 | Dialog-Hülle mit Höhenbegrenzung/Scroll (D1, D2) | klein | `LocalWorklistPage`, `StationsPage` (+ Test in `verify-ui.cjs` auf 375 px) |
| 3 | Warnung bei `allow` + leerer Quellenliste (C1) + Health-Finding | klein | `StationsPage`, `health_checks.py` |
| 4 | Typisierte Eingaben: Datum/Zeit/Modalität/Status als Auswahl bzw. Picker (B1) | mittel | `LocalWorklistPage` |
| 5 | `min`/`max`/`type=number` aus der Server-Range (B2, B3) + Musterprüfung Pfad/URL/AET (B4) | mittel | `BrokerSettingsPage`, Karten, `NodeFormDialog` |
| 6 | Konsequenz beim Löschen des Standard-Ziels (C2) | klein | `TargetsPage` |
| 7 | Dirty-Guard in Dialogen (E1) | klein | `NodeFormDialog`, `LocalWorklistPage`, `StationsPage` |
| 8 | Einheitliches „Speichern" + `aria-invalid` (E2, E5) | klein | mehrere |
| 9 | Duplikat-Hinweise (B5, E4) | klein | `NodeFormDialog`, `RulesPage` |
| 10 | i18n: Broker-Bereich dokumentieren oder Kern-Schlüssel übersetzen (F1) | klein–mittel | `src/i18n/locales/*` |

**Verifikation je Maßnahme** (wie in den bisherigen Sprints):

- vitest: Fehlerblock erscheint bei 422; Warnung bei `allow`+leer; Dirty-Guard
  fragt nach; `min`/`max` am Feld.
- `verify-ui.cjs`: zusätzlich „Dialog auf 375 px vollständig erreichbar"
  (erstes Feld `y >= 0`, Speichern-Button innerhalb des Viewports) und
  „ungültige Eingabe erzeugt eine sichtbare Meldung".
- Playwright: ein Fall je neuer Warnung.
- Backend: Health-Finding für `allow`+leer.

---

## 6. Anhang: Messprotokoll (live, Auszug)

| Prüfung | Ergebnis |
|---|---|
| Worklist-Dialog, 375×812 | Höhe 1 282 px, `overflowY: visible`, `canScroll: false`, erstes Feld y = −62, Speichern y = 942 → **nicht bedienbar** |
| Stations-Dialog, 375×812 | Höhe 746 px, top 33 → passt (grenzwertig) |
| Setting `echo_interval_s = "abc"` + Speichern | keine sichtbare Meldung, Feld behält „abc" |
| Transform-Tag `0010-0010` | keine Inline-Meldung (Prüfung erst beim Absenden) |
| Locale-Schlüssel | de/en je 469 Broker-Schlüssel, übrige 7 Sprachen 0 (Fallback Englisch greift) |
