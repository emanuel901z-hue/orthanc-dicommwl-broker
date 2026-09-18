# Gap-Analyse: DAU-Sicherheit der MWL-Broker-Oberfläche

**Gegenstand:** das gesamte Broker-UI in OE3 (`/broker`, `/broker/*`, Settings-Karten)
**Frage:** Wo kann ein durchschnittlicher Anwender (DAU, kein DICOM-/Netzwerk-Spezialist)
etwas falsch eingeben, etwas Wichtiges übersehen — und erfährt er es?
**Stand:** Sprint 9 (UI-Härtung P1) umgesetzt — siehe Abschnitt 7
**Status der Befunde:** **alle 19 Befunde bearbeitet** — A1–A3, B1–B5, C1–C3,
D1, D2, E1–E5 ✅ behoben (Sprint 9–11); F1 bewusst dokumentiert (englischer
Fallback greift)

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
| A1 ✅ | **Kein Fehlerfeedback bei Einstellungs-Writes.** `SettingRow` ruft `setValue.mutate` und rendert nur `pending`, nie `error`. Gleiches Muster in `TlsCard`, `AtnaCard`, `NotificationsCard`. | `pages/BrokerSettingsPage.tsx:58–70` (Input ohne `type`, kein Fehlerblock); gemessen: `echo_interval_s="abc"` → keine sichtbare Meldung, Feld behält den Wert | Der Anwender glaubt, gespeichert zu haben. Besonders kritisch bei Zahlen/Pfaden/URLs — die Wirkung tritt nie ein, ohne Hinweis | Fehlerblock (`role="alert"`) je Setting + Karte, wie in den Dialogseiten bereits üblich |
| A2 ✅ | **Kein Erfolgsfeedback.** Kein Toast/„Gespeichert"-Hinweis im gesamten Broker-UI (0 Treffer für `toast`). | Code-Review; sichtbar auch live: nach dem Speichern ändert sich nur der Button-Zustand | Der DAU fragt sich, ob der Klick gewirkt hat — typischer Auslöser für Doppelklicks | Toast oder Inline-„Gespeichert" mit Zeitstempel |
| A3 ✅ | **Validierungsfehler erst nach dem Absenden** (Transforms-Tag, Case-Check, Stations-AET): keine Live-Prüfung. | `components/OperationsEditor.tsx` (nur `placeholder`), `pages/TransformsPage.tsx:413` (Serverfehler erst nach Submit); gemessen: ungültiger Tag `0010-0010` → keine Inline-Meldung | Umweg: erst ausfüllen, absenden, Fehler lesen, korrigieren | Feld-Prüfung beim Verlassen (`onBlur`) mit derselben Regel wie der Server |

### B. Eingabevalidierung — was man falsch eingeben kann

| ID | Befund | Beleg | Auswirkung | Empfehlung |
|---|---|---|---|---|
| B1 ✅ | **Lokale Worklist: 13 Freitextfelder**, darunter Datum, Uhrzeit, Geburtsdatum, Modalität, Station-AET, SPS-Status, Study-UID. Kein Datums-/Zeit-Picker, kein Format-Hinweis, keine Prüfung. | `pages/LocalWorklistPage.tsx:325–338` (alle Felder als `<Input>` ohne `type`) | Ein Tippfehler (z. B. `17.09.2026` statt `2026-09-17`) führt dazu, dass der Eintrag **still nie** in einer C-FIND-Antwort auftaucht — der Notfall wäre nicht sichtbar | `type="date"`/`type="time"`, Auswahl für Modalität/SPS-Status/Sex, AET- und UID-Musterprüfung |
| B2 ✅ | **Zahlenfelder ohne Grenzen.** 10 `type="number"`-Felder, nur 4 mit `min`; u. a. TLS-Port, Zertifikats-Gültigkeit, Alerting-Intervall, Prioritäten. | `components/TlsCard.tsx:312,385`; `pages/StationsPage.tsx:320`; `pages/RulesPage.tsx:317` | Werte außerhalb des erlaubten Bereichs werden erst vom Server abgewiesen — und bei Settings unsichtbar (siehe A1) | `min`/`max` aus der Server-Range spiegeln, plus Hinweistext |
| B3 ✅ | **Einstellungen ohne Typ.** Auch Integer-Settings rendern als Textfeld. | `pages/BrokerSettingsPage.tsx:58` | „30 Tage" als „3o" ist nicht unterscheidbar von einer gültigen Eingabe | `type="number"` + `min`/`max` aus der API-Beschreibung |
| B4 ✅ | **Pfade, URLs, AETs ohne Musterprüfung** (TLS-Zertifikatspfade, ATNA-Host/Port, Webhook-URL, Stations-AET). Serverseitig validiert (`path`/`url`/`enum`), clientseitig frei. | `components/TlsCard.tsx`, `components/AtnaCard.tsx`, `components/NotificationsCard.tsx` | Fehleingaben werden erst spät erkannt (kombiniert mit A1 sogar gar nicht sichtbar) | Client-Regeln aus denselben Konstanten wie der Server |
| B5 ✅ | **Doppelte Knoten/AET-Kollisionen** werden nicht im Formular geprüft. | `components/NodeFormDialog.tsx:72–82` prüft Format, nicht Eindeutigkeit; Health-Panel meldet Kollisionen erst danach | Zwei Quellen mit derselben AET → schwer zu findende Fehlkonfiguration | Hinweis beim Tippen („diese AET ist bereits vergeben") |

### C. Gefährliche Konfigurationen ohne Warnung

| ID | Befund | Beleg | Auswirkung | Empfehlung |
|---|---|---|---|---|
| C1 ✅ | **Stationsregel `allow` mit leerer Quellenliste** verbirgt alle Quellen. Kein Hinweis im Dialog. | `pages/StationsPage.tsx:305–315` (Modus-Auswahl, keine Bedingung); Server-Semantik dokumentiert in `station_rules.py` | Eine Konsole sieht plötzlich **nichts** mehr — der Betrieb sucht am Gerät statt in der Regel | Warnhinweis im Dialog („verbirgt alle Quellen") + Health-Finding |
| C2 ✅ | **Löschen des Standard-Ziels** wird wie jedes Ziel bestätigt („abhängige Regeln werden entfernt"), ohne den eigentlichen Effekt zu nennen. | `pages/TargetsPage.tsx:228` (generische Warnung) | Neue Bilder ohne Regel landen **nirgendwo** (unrouted) — das ist ein Betriebsausfall | Konsequenz explizit nennen („danach haben unzugeordnete Bilder kein Ziel") |
| C3 ✅ | **Prioritäts-Änderung ohne Wirkungserklärung.** Bei Regeln/Quellen/Zielen ist nicht sichtbar, was „Priorität 10 vs. 20" praktisch bedeutet. | `pages/RulesPage.tsx`, `SourcesPage.tsx`, `StationsPage.tsx` | Der DAU setzt Werte, ohne die Wirkung (Reihenfolge der Deduplizierung) zu kennen | Ein Satz Hilfe + Verweis auf die Fall-Prüfung |

### D. Mobile/Layout

| ID | Befund | Beleg | Auswirkung | Empfehlung |
|---|---|---|---|---|
| D1 ✅ | **Worklist-Dialog nicht scrollbar** (siehe Zusammenfassung). | gemessen 375×812: Höhe 1 282 px, `overflowY: visible`, erstes Feld y = −62, Speichern y = 942 | Aufgabe auf dem Handy **nicht erfüllbar** | `max-h-[90vh] overflow-y-auto` wie in allen anderen Dialogen |
| D2 ✅ | Dialoge ohne Höhenbegrenzung: nur `LocalWorklistPage` (D1) und `StationsPage` (`max-w-xl`, gemessen 746 px — grenzwertig, bei mehr Feldern kippt es) | `pages/LocalWorklistPage.tsx:317`, `pages/StationsPage.tsx:276` | Bei kleinen Geräten/Hochformat abgeschnitten | Einheitliche Dialog-Hülle mit Höhenbegrenzung |

### E. Konsistenz und Bedienfluss

| ID | Befund | Beleg | Auswirkung | Empfehlung |
|---|---|---|---|---|
| E1 ✅ | **Keine Warnung bei ungespeicherten Eingaben**: Esc/Klick daneben schließt jeden Dialog und verwirft die Eingabe. | kein `beforeunload`/Dirty-Guard in `NodeFormDialog`, `LocalWorklistPage`, `StationsPage` | Datenverlust bei versehentlichem Schließen | Dirty-Guard im Dialog („Änderungen verwerfen?") |
| E2 ✅ | **Gemischte Button-Beschriftungen** für dieselbe Aktion (`common.save` „Save" vs. `broker.save` „Speichern"). | `pages/TransformsPage.tsx:345`, `RulesPage.tsx:127`, `NodeFormDialog.tsx:99` … | In Sprachen, in denen nur einer der Schlüssel gepflegt ist, stehen zwei verschiedene Wörter für „Speichern" | Ein Schlüssel für „Speichern" |
| E3 ✅ | **Kein „Zurücksetzen" im Formular** (nur beim Bearbeiten eines Knotens existiert „Reset to default" für Settings). | `NodeFormDialog`, `LocalWorklistPage` | Falsche Eingaben muss man manuell rückgängig machen | „Zurücksetzen"-Knopf mit Bestätigung |
| E4 ✅ | **Kein Hinweis bei Duplikaten**: eine zweite Regel mit gleicher Quelle+Ziel ist erlaubt und sieht wie die erste aus. | `pages/RulesPage.tsx` | Doppelte Regeln → unklare Wirkung | Duplikat-Warnung beim Anlegen |
| E5 ✅ | **Fehlermeldungen sind nicht mit dem Feld verknüpft** (kein `aria-invalid`/`aria-describedby`). | 0 Treffer in `src/features/broker/**` | Screenreader liest den Fehler nicht am Feld | `aria-invalid` + `aria-describedby` setzen |

### F. Sprache

| ID | Befund | Beleg | Auswirkung | Empfehlung |
|---|---|---|---|---|
| F1 📄 | **Broker-UI nur auf Deutsch und Englisch** — der Fork verspricht 9 Sprachen; `es, fr, ja, zh, ru, tr, ar` haben **0** Broker-Schlüssel. | Zählung der `broker`-Schlüssel je Locale: de/en 469, übrige 0; `fallbackLng: 'en'` ist gesetzt | Wer die UI z. B. auf Französisch stellt, sieht den Broker-Bereich auf Englisch (Fallback greift, kein Rohschlüssel) | Bewusst dokumentieren **oder** die wichtigsten ~40 Schlüssel übersetzen |

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

---

## 7. Umsetzungs-Log

### Sprint 9 — UI-Härtung P1 (umgesetzt)

**Behoben.**

- **A1/A2 — Rückmeldung.** `useAuditedMutation` zeigt jetzt **immer** Feedback:
  Erfolg als Toast („Gespeichert."), Fehler als Toast mit der Server-Meldung
  (`Nicht gespeichert: must be between 5 and 3600`). Zusätzlich rendern die
  Settings-Seite und die Karten TLS/ATNA/Alerting den abgelehnten Wert **inline**
  (`role="alert"`, `aria-invalid` am Feld).
- **B2/B3 — typisierte Eingaben.** `GET /settings` liefert jetzt `min`/`max`
  (Integer) und `choices` (Enums). Die Settings-Seite rendert danach:
  `bool` → Switch, `int` → `type="number"` mit `min`/`max` **plus Klartext-Hinweis
  („Erlaubt: 5 bis 3600")**, `enum` → Auswahlfeld, sonst Text (URL als `type="url"`).
  Buchstaben in Zahlenfeldern sind damit gar nicht mehr eingebbar.
- **C1 — gefährliche Stationsregel.** Der Dialog warnt bei `allow` ohne Quelle
  („…verbirgt alle Quellen — diese Konsole würde eine leere Arbeitsliste
  erhalten"), und der Health-Check meldet `station_rule_hides_all` (error).
- **D1/D2 — Dialoge auf kleinen Bildschirmen.** `LocalWorklistPage` und
  `StationsPage` haben jetzt `max-h-[90vh] overflow-y-auto` wie alle anderen
  Dialoge.
- **E5 — Barrierefreiheit.** `aria-invalid` am abgelehnten Feld.

**Verifikation.**

| Ebene | Ergebnis |
|---|---|
| pytest | 395 Tests (+3: Settings-Constraints im API, `station_rule_hides_all` positiv/negativ) |
| vitest | 449 Tests (+8: Zahlengrenzen, Enum als Auswahl, abgelehnter Wert sichtbar, Erfolgs-Toast, Dialog scrollbar, allow+leer-Warnung, Gegenprobe) |
| Playwright | 50 Tests (+2), inkl. „Stationsregel warnt bei allow ohne Quelle" |
| verify-ui.cjs | **114 Checks** (neu: Dialog passt bei 375 px, Zahleneinstellung typisiert/begrenzt, Bereich im Klartext, abgelehnter Wert sichtbar **und nicht gespeichert**) |
| Live-Messung | Worklist-Dialog bei 375×812: `top=73`, Höhe 694, `scrollbar=true` (vorher: top=−235, Höhe 1 282, nicht scrollbar) |

### Sprint 10 — Eingabeführung (umgesetzt)

**Behoben.**

- **B1 — typisierte Felder in der lokalen Worklist.** Datum und Uhrzeit sind
  echte Picker (`type="date"`/`type="time"`), Geschlecht und „nicht gesetzt"
  sind Auswahlen, Modalität hat Vorschläge (Datalist, Freitext bleibt möglich),
  Station-AET wird automatisch großgeschrieben und geprüft (1–16 Zeichen,
  A–Z 0–9 _ -), die Study-UID auf Ziffern/Punkte. Jedes Feld hat einen
  Klartext-Hinweis, ungültige Werte werden **vor** dem Speichern gemeldet und
  blockieren den Speichern-Knopf.
- **B4 — Vorprüfung wie der Server.** `lib/setting-rules.ts` spiegelt
  `settings_service.validate_value` (bool/int-Bereich/enum/url/path/aets) und
  wird von der Settings-Seite **und** den Karten genutzt: der Fehler steht am
  Feld, der Speichern-Knopf ist gesperrt, gesendet wird nichts Ungültiges.
- **B2/B3 (Nachtrag) — ein Schreibvorgang pro Änderung.** Die Karten
  speicherten bisher **bei jedem Tastendruck** (ein Pfad = sechs Requests, fünf
  davon ungültig, plus Audit-Rauschen). Jetzt gibt es einen Entwurf pro Feld
  (`use-setting-draft.ts`), gespeichert wird beim Verlassen — nur wenn gültig
  und geändert.
- **C2 — Standard-Ziel.** Der Löschdialog nennt die Folge ausdrücklich
  („ohne Routing-Regel haben eingehende Bilder danach kein Ziel mehr").
- **C3 — Priorität.** Stationsregeln haben jetzt denselben Erklärsatz wie die
  Routing-Regeln („kleinerer Wert = zuerst berücksichtigt …").

**Verifikation.**

| Ebene | Ergebnis |
|---|---|
| pytest | 395 Tests (unverändert — Sprint 10 ist reine UI-Führung) |
| vitest | 463 Tests (+14: Regelmodul 9, Entwurfs-Hook 4, Vorprüfung im Settings-Test) |
| Playwright | 50 Tests |
| verify-ui.cjs | **118 Checks** (neu: Datum/Zeit sind Picker, Format-Hinweis an der Station-AET, ungültige AET wird vorab gemeldet, ungültiger Wert wird vor dem Senden abgefangen, nichts wird gespeichert) |
| Live-Messung | Feldtypen im Worklist-Dialog: `text, date, time`; Station-AET „ct-01!" → Hinweis + Speichern gesperrt |

### Sprint 11 — Bedienfluss, Konsistenz, Barrierefreiheit (umgesetzt)

**Behoben.**

- **E1 — Dirty-Guard.** Schließen mit Esc/Klick daneben fragt jetzt nach
  („Eingaben verwerfen?" mit „Weiter bearbeiten"/„Verwerfen"), und zwar in allen
  fünf Formularen (Knoten, lokale Worklist, Stationsregeln, Routing-Regeln,
  Transform-Regeln). Ohne Änderungen schließt der Dialog sofort weiter.
- **B5/E4 — Duplikate.** Eine bereits vergebene AET wird beim Tippen gemeldet
  („wird bereits von X verwendet"). Die Vergleichsliste wird beim Öffnen
  eingefroren — beim Testen zeigte der Dialog sonst nach dem Speichern kurz
  einen Konflikt mit dem gerade angelegten Eintrag (gefunden und behoben).
  Eine zweite Regel mit gleicher Quelle+Ziel wird gemeldet und der
  Speichern-Knopf gesperrt.
- **A3 — Tag-Vorprüfung.** Der Transform-Editor prüft DICOM-Tag/Schlüsselwort
  nach derselben Regel wie der Server und meldet sofort (`aria-invalid`).
- **E2 — einheitliches Speichern.** Alle Formulare nutzen denselben Schlüssel
  (`common.save`) statt zwei verschiedener.
- **E3 — Zurücksetzen.** Der Knoten-Dialog kann die Eingaben auf den
  Ausgangszustand zurücksetzen.
- **F1 — Sprache.** Bewusst dokumentiert: der Broker-Bereich ist de/en, andere
  Sprachen fallen auf Englisch zurück (`fallbackLng: 'en'`, kein Rohschlüssel).
  Der Hinweistext liegt als `broker.i18nBrokerNote` bereit.

**Verifikation.**

| Ebene | Ergebnis |
|---|---|
| pytest | 395 Tests |
| vitest | 462 Tests (+6: Dirty-Guard, Duplikat-AET, Tag-Vorprüfung, Duplikat-Regel) |
| Playwright | 50 Tests |
| verify-ui.cjs | **122 Checks** (neu: ungespeicherte Eingaben werden nicht stillschweigend verworfen, Dialog schließt nach dem Verwerfen, doppelte AET gemeldet, doppelte Quelle+Ziel gemeldet und gesperrt) |
| Live-Messung | „discard-check" + Esc → Bestätigung; „RIS_A" im AET-Feld → Hinweis „already used by …" |

---

## 8. Abschluss

Alle drei Sprints sind umgesetzt, getestet, dokumentiert und gepusht:

| Sprint | Inhalt | Ergebnis |
|---|---|---|
| 9 | P1: Rückmeldung, typisierte Einstellungen, Dialoge, gefährliche Stationsregel | 3× P1 behoben, +8 vitest, +3 pytest, +2 Playwright |
| 10 | P2: Eingabeführung (Picker, Vorprüfung, ein Workflow pro Änderung, Konsequenzen) | +14 vitest, verify-ui +4 |
| 11 | P2/P3: Dirty-Guard, Duplikate, Tag-Vorprüfung, Konsistenz, A11y, i18n-Doku | +6 vitest, verify-ui +4 |

**Kennzahlen nach der Härtung:** 395 Backend-Tests (96 %), 462 Frontend-Tests
(98 % Broker-UI), 50 Playwright-Tests, **122 Checks** im Deep-Audit.
