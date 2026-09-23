# GitHub: Repository-Beschreibungen und -Themen

Diese Datei enthält die **fertigen Texte für die GitHub-„About"-Bereiche** der
beiden Repositories. Sie lassen sich nicht per Skript setzen (in dieser Umgebung
gibt es weder `gh` noch einen API-Zugang), deshalb hier zum Kopieren — entweder
über die Weboberfläche (Repo → Zahnrad neben „About") oder mit:

```bash
gh repo edit emanuel901z-hue/orthanc-dicommwl-broker \
  --description "..." --homepage "" --add-topic dicom --add-topic worklist ...
```

---

## 1. `orthanc-dicommwl-broker` (Broker + Deployment)

**Description** (GitHub erlaubt ~350 Zeichen):

```text
DICOM Modality Worklist broker for hospitals: aggregates several RIS/KIS
worklists, serves them to the modalities, reports MPPS back to the RIS, takes HL7
orders (ORM/OMG/OMI) and ADT patient updates (incl. PIR), and routes the images
to the right PACS. Postgres-backed and HA-capable, audited, with an optional OE3
console and OHIF viewer — Docker deployment, Prometheus metrics, TLS/mTLS.
Verified against DCMTK, dcm4che and DVTk.
```

**Topics:**

```text
dicom  dcm4che  dcmtk  dvtk  pynetdicom  modality-worklist  mwl  mpps
worklist-broker  ris  kis  pacs  c-find  c-store  hl7  orm  adt  mllp  atna
ihe  ihe-swf  pir  tls  mtls  prometheus  fastapi  postgresql  docker  orthanc
ohif  high-availability  python  interop
```

**Homepage:** die Dokumentationsübersicht verlinken:
`https://github.com/emanuel901z-hue/orthanc-dicommwl-broker/blob/main/README.md`
(alternativ der Runbook-Einstieg: `…/blob/main/docs/runbook.md`)

**Kurzbeschreibung für ein Release („What's new"):**

```text
MWL-Aggregation über mehrere RIS/KIS mit Cache und Circuit Breaker, C-STORE-
Routing mit Spool, MPPS-SCP mit Statusmeldung an das RIS, HL7 (ORM/OMG/OMI) und
ADT/PIR, lokale Worklist, Stationsregeln, ATNA, DICOM-TLS/mTLS, RBAC,
Aufbewahrung, Statistik, UPS-RS-Subset, Auftragskontext für MADO-Manifeste,
Hochverfügbarkeit auf gemeinsamer DB — 626 Backend-Tests, extern verifiziert mit
DCMTK, dcm4che und DVTk (23/23 bzw. fünf PASSED-Szenarien).
```

---

## 2. `orthanc-explorer-3-usable` (OE3-Fork)

**Description:**

```text
Orthanc Explorer 3 — usable fork: backend-proxy auth, RBAC feature flags,
study/series merge with patient-safe matching, smart search, 9-language i18n,
full A11y and BEFORE+AFTER audit events on every write. Adds the MWL broker UI:
worklist proxy, routing rules, DICOM transforms, TLS, retention and monitoring.
```

**Topics:**

```text
orthanc  dicom  dicomweb  ohif  viewer  react  typescript  vite  tailwind
i18next  a11y  rbac  audit  pacs  ris  worklist  mwl-broker  docker
```

**Homepage:** `https://github.com/emanuel901z-hue/orthanc-explorer-3-usable`

**Release-Notiz (v2.4.0):**

```text
MWL broker UI: configuration pages for sources, targets, routing and modify
rules, runtime settings, worklist cache and C-STORE spool monitoring, ATNA and
TLS cards, RBAC banner, retention overview — plus DAU hardening (input guidance,
page help, form drafts) and translations for all nine languages.
```

---

## 3. Pull-Request-Beschreibung (Fork → upstream/main)

Falls der Fork als PR angeboten wird, passt dieser Text:

```markdown
## Was dieser Fork hinzufügt

- **Backend-Proxy-Auth + RBAC**: `authMode: "none"` mit Cookie-Flow, Feature-Flags
  für alle Schreibaktionen, `AuthGate` vor jedem API-Aufruf
- **Audit**: BEFORE+AFTER-Events auf allen Schreibwegen (kein Schreibzugriff
  direkt aus Komponenten)
- **Merge/Migrate** mit patientensicherem Matching, **Smart Search**,
  konfigurierbare Spalten, Mobile-Card-Ansichten, Tastaturkürzel
- **9-Sprachen-i18n** über react-i18next (kein eigenes `t()`),
  `npm run i18n:check` prüft die Abdeckung in CI
- **MWL-Broker-UI** (`/broker`): Worklist-Proxy-Konfiguration, Routing- und
  Modify-Regeln, lokale Worklist + HL7-ORM, Stationsregeln, Worklist-Cache,
  C-STORE-Spool, ATNA, DICOM-TLS, Aufbewahrung, Health/Alerting
- **DAU-Härtung**: typisierte Eingaben mit Vorprüfung, verständliche
  Fehlermeldungen, „Was ist das?"-Hilfe je Seite, Formular-Entwürfe über
  Zurück/F5

## Tests

- `npm run test` — 606 Unit-Tests (Vitest), `npm run i18n:check`, `tsc`, ESLint
- Playwright: 30 Tests im Stack-Lauf (Desktop + Mobile), `verify-ui.cjs`: 154 Checks
- Backend des Brokers: 626 pytest-Tests (95 % Coverage) im Schwester-Repo
```

---

## 2. `orthanc-explorer-3-usable` (OE3-Fork mit Broker-Konsole)

Das Fork-About steht heute noch auf dem **Upstream-Text** („Modernes
React/TypeScript-Frontend …") — es nennt den MWL-Broker inzwischen zwar, aber
nicht die Rollen, die dazugekommen sind (MPPS, HL7/ADT+PIR, IID, UPS-RS) und
nicht die Betriebsseite (Vorbelegung/Sperre, Interop-Nachweis). Empfehlung:
ersetzen durch:

**Description** (GitHub erlaubt ~350 Zeichen):

```text
Production-ready Orthanc Explorer 3 fork: audited writes, RBAC, 9 languages,
mobile views, IHE image display (RAD-106) and the full MWL broker console —
worklist fan-out, MPPS, HL7, store routing, TLS, ATNA, retention. The deployment
can preset and lock its configuration for standalone use.
```

**Topics:**

```text
orthanc  dicom  dicomweb  ohif  react  typescript  vite  ihe  mwl  mpps
worklist  pacs  radiology  rbac  i18n  playwright  vitest  pwa  audit
```

**Homepage:** `https://github.com/emanuel901z-hue/orthanc-dicommwl-broker`
(der Broker-Stack, zu dem diese Oberfläche gehört)

**Befehl (falls `gh` verfügbar):**

```bash
gh repo edit emanuel901z-hue/orthanc-explorer-3-usable \
  --description "Production-ready Orthanc Explorer 3 fork: audited writes, RBAC, 9 languages, mobile views, IHE image display (RAD-106) and the full MWL broker console — worklist fan-out, MPPS, HL7, store routing, TLS, ATNA, retention. The deployment can preset and lock its configuration for standalone use." \
  --homepage "https://github.com/emanuel901z-hue/orthanc-dicommwl-broker" \
  --add-topic orthanc --add-topic dicom --add-topic dicomweb --add-topic ohif \
  --add-topic react --add-topic typescript --add-topic ihe --add-topic mwl \
  --add-topic mpps --add-topic worklist --add-topic pacs --add-topic rbac \
  --add-topic i18n --add-topic playwright --add-topic audit
```

### Und die **About-Seite in der App** selbst?

Sie war gepflegt (20 Fork- + 11 Broker-Fähigkeiten), nannte aber **MPPS,
HL7/ADT+PIR, IID (RAD-106) und UPS-RS nicht** und beschrieb den Broker auf dem
Stand vor diesen Rollen. Aktualisiert in allen neun Sprachen
(`about.description` + sechs neue Einträge unter `about.features`:
`mwlMpps`, `mwlPir`, `mwlIid`, `mwlUps`, `mwlStats`, `interop`).
