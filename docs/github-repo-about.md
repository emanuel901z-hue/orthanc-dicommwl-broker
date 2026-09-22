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
DICOM Modality Worklist broker for hospitals: queries several RIS/KIS sources,
merges and caches their worklists, serves them to the modalities, and routes the
stored images to the right PACS. Optional OHIF viewer and OE3 configuration UI
included — Docker deployment, Prometheus metrics, audit trail, TLS/mTLS.
```

**Topics:**

```text
dicom  dcm4che  pynetdicom  modality-worklist  mwl  worklist-broker  ris  kis
pacs  c-find  c-store  hl7  orm  mllp  atna  ihe  tls  mtls  prometheus
fastapi  postgresql  docker  orthanc  ohif  python
```

**Homepage:** leer lassen (interne Installation) — oder die Doku verlinken:
`https://github.com/emanuel901z-hue/orthanc-dicommwl-broker/blob/main/docs/roadmap-worklist-broker.md`

**Kurzbeschreibung für ein Release („What's new"):**

```text
Sprint 1–8 der Roadmap: Circuit Breaker, Worklist-Cache, C-STORE-Spool,
Simulation/Config-Audit, Alerting, lokale Worklist + HL7-ORM, Stationsregeln,
ATNA-Export, DICOM-TLS/mTLS, RBAC und Aufbewahrungskonzepte. 605 Backend-Tests.
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

- `npm run test` — 594 Unit-Tests (Vitest), `npm run i18n:check`, `tsc`, ESLint
- Playwright: 55 Stack-Tests (Desktop + Mobile), `verify-ui.cjs`: 149 Checks
- Backend des Brokers: 605 pytest-Tests (96 % Coverage) im Schwester-Repo
```
