# Mängelbericht Baseline-Audit (Kartoffel)

**Datum des Audits:** siehe Git-Historie · **Regelwerk:** `documentation/fachregeln/kartoffel.md` (KAR-001 … KAR-047)

## Datengrundlage

Analysiert wurden die vorhandenen FastForwardRunner-Exporte unter `export/fast_forward/`:

| Datei | Feld | Zeitraum | Events |
|---|---|---|---|
| `fast_forward_2025100_365days_20260321_101045.json` | 2025100 | 365 Tage ab 2025-01-01 | **0** |
| `fast_forward_2026100_365days_20260321_101104.json` | 2026100 | 365 Tage ab 2026-01-01 | **0** |
| `fast_forward_2026200_500days_20260321_101125.json` | 2026200 | 500 Tage ab 2026-01-01 (Events 2027-03-25 … 2027-05-16) | **13** |
| `audit_baseline_990001_760days.json` | 990001 | 760 Tage ab 2026-01-01, Seed 42, inkl. Ernte + Lagerung | **34** (+ 1795 Domain Events) |

Ergänzend: statische Analyse von `config/planting_plan_potato.json`, `scheduler/decision_manager.py`, `scheduler/calendar_driven_runner.py`, `services/planting_plan_service.py`, `services/protection_plan_service.py`, `services/irrigation_service.py`, `services/moisture_service.py`.

**Nachtrag:** Der empfohlene 760-Tage-Lauf wurde inzwischen ausgeführt (Feld 990001, Belana, 20 ha, Start 2026-01-01, Seed 42) und deckt die volle Saison inkl. Sikkation, Roden und Lagerung ab. Die ursprünglich „statisch" (nur aus Konfiguration/Code) abgeleiteten Befunde B5, B6 und B12 sind damit **durch Event-Belege verifiziert** (siehe Abschnitt „Verifikation durch 760-Tage-Lauf"). Zusätzlich wurden zwei neue Befunde aufgenommen (B13, B14).

---

## Befunde (priorisiert nach Schweregrad)

| # | Problem | Beleg (Regel-ID, Event-Auszug) | Schweregrad | Vermutete Ursache / Komponente |
|---|---|---|---|---|
| B1 | **Beregnungs-Events tragen das falsche Jahr** und zerreißen die Zeitachse des Zyklus: Beregnung „2026-05-07 / 2026-05-10 / 2026-05-16“ erscheint zwischen Operationen vom 2027-05-01 (P-Düngung) und 2027-05-10 (Fungizid Enervin). Die Beregnung fand simulativ 2027 statt, wird aber auf 2026 datiert. | KAR-015 (hart); Feld 2026200: wt=15 `start_date=2026-05-07 12:00:00` direkt nach wt=23 `2027-05-01` und vor wt=29 `2027-05-08` | **hoch** | `IrrigationSimulator._create_irrigation_event()` (services/irrigation_service.py, Z. 100): Datum = `context.start_date.year` + day_of_year, ignoriert das tatsächliche Simulationsjahr (Saison liegt wegen B2 in start_year+1) |
| B2 | **Ein volles Simulationsjahr erzeugt 0 Events**: Beide 365-Tage-Läufe sind leer; im 500-Tage-Lauf beginnt die erste Operation erst an Tag 449 (2027-03-25). Der Legetermin wird immer in `start_date.year + 1` geplant → ~15 Monate Leerlauf, Ernte erst nach ~640 Tagen erreichbar. | KAR-010/KAR-046 (je Zyklus 1 Lege-/Rode-Event erwartet); Belege: `..._365days_...json` mit `"operations": []` | **hoch** | `PlantingPlanService.initialize_planting_plan()` (services/planting_plan_service.py, Z. 48–52): `get_random_date(..., self.start_date.year+1)` |
| B3 | **Beregnungsgaben fachlich unwirksam klein** (4,8 / 6,6 / 8,4 mm statt 20–30 mm); die 4,81-mm-Gabe unterschreitet sogar den eigenen Mindestwert von 5 mm, weil die Zufallsstreuung (×0,8–1,2) NACH der Schwellwertprüfung erfolgt. | KAR-040 (hart: ≥ 10 mm); Feld 2026200: wt=15 `application_amount=4.81` (2026-05-07), `6.58` (2026-05-10), `8.43` (2026-05-16) | **hoch** | `IrrigationSimulator.get_candidate_operations()` (Z. 149–158): Gabe = exakt aktuelles Defizit × Zufall, keine Mindest-/Zielgabe (z. B. 20–25 mm) |
| B4 | **Beregnungsentscheidung ist vom Simulationswetter entkoppelt**: Bodenfeuchtedaten stammen aus einem festen Fallback-Jahr (2022, `dwd_data/...2022...nc`) und einer **zufälligen Koordinate** in Deutschland; die „Prognose“ (4 Tage) schaut in dieselben historischen Fremdjahresdaten. Für Saison 2027 existieren keine Daten → Entscheidungen basieren systematisch auf falschem Jahr/Standort. | KAR-034 (hart), KAR-031 nicht erfüllbar; Code-Beleg: `MoistureDataService.get_moisture_data()` Fallback `YEAR=2022` (services/moisture_service.py, Z. 104–110), Zufallskoordinate Z. 64–90 | **hoch** | `MoistureDataService` + Initialisierung in `CalendarDrivenRunner._initialize_services()`; fehlende Wetter-/Jahreskopplung der Entscheidungslogik |
| B5 | **Sikkation→Roden-Wartezeit systematisch verletzt** (statisch): Die Ernte-Phase plant das Sikkationsherbizid (Quickdown) auf −5…−3 Tage und Roden auf 0…+5 Tage zum Erntedatum → Abstand nur 3–10 Tage statt ≥ 14 Tage (Zulassungsauflage Quickdown/Shark, Schalenfestigkeit 2–5 Wochen). Tritt in **jeder** vollständig simulierten Saison auf. | KAR-020/KAR-024 (hart); Beleg: `config/planting_plan_potato.json` Phase `harvesting`: Herbizid `min/max_days_to_target: -5/-3`, Roden `0/+5` | **hoch** | Konfiguration `planting_plan_potato.json` + fehlende Abstandsprüfung im `DecisionManager` |
| B6 | **Pflanzenschutz nach dem Roden möglich** (statisch): Protection-Plan-Termine werden relativ zum Start der Crop-Management-Phase geplant (Tag 0…147), der Rodetermin liegt aber schon bei Legen+90…95 Tagen. Spät geplante Fungizide/Sikkationsspritzungen (z. B. Plan 1: Tag 74 ⇒ ~Legen+95) können zwischen Roden und Einlagerung ausgeführt werden; noch spätere verfallen stillschweigend. | KAR-005 (hart), KAR-042; Beleg: `growth_duration=90` vs. Protection-Tage bis 147 (`config/planting_plan_potato.json`); Terminanker `ProtectionPlanService.plan_protections()` (Z. 57–65: `self.start_date` = Datum der Service-Initialisierung, nicht Pflanzdatum) | **hoch** | `ProtectionPlanService` (falscher Zeitanker, kein Abgleich mit Erntetermin); `CalendarDrivenRunner._reset_services()` verwirft Rest-Spritzungen kommentarlos |
| B7 | **Intra-Tages-Sequenz invertiert**: Pflanzguttransport (Sequenz 1) startet am 2027-04-18 um 15:04, das Legen (Sequenz 2) am selben Tag bereits um 06:02 — der Transport des Pflanzguts erfolgt also nach dem Legen. | KAR-003 (hart); Feld 2026200: wt=18 `2027-04-18 15:04:30` vs. wt=26 `2027-04-18 06:02:14` | **mittel** | `PlantingPlanService.get_events_for_ops()`: Uhrzeit wird pro Operation zufällig (6–17 Uhr) gewürfelt, Sequenznummer wird bei der Zeitvergabe ignoriert |
| B8 | **Keine Wetter-/Bodenprüfung bei Spritzen und Bodenbearbeitung**: Der DecisionManager kennt ausschließlich eine Worktype-Priorität (Spritzen/Beregnen = low priority), keinerlei Regen-, Wind- oder Bodenfeuchteregeln. Spritzungen bei Regen/Wind sind damit nicht ausgeschlossen. | KAR-030/KAR-032 (hart, derzeit nicht aus Events prüfbar); Code-Beleg: `WorkTypePriorityStrategy.select_operation()` (scheduler/decision_manager.py, Z. 71–105) enthält keine Kontextprüfung | **mittel** | `DecisionManager`/`WorkTypePriorityStrategy`: fehlende Wetterkopplung (bekanntes Architektur-Defizit, PO-Vermutung bestätigt) |
| B9 | **Prioritätslogik verschiebt terminkritischen Pflanzenschutz**: Jede beliebige High-Prio-Operation (auch Düngung) unterdrückt am selben Tag alle Spritzungen; überfällige Spritzungen werden am nächsten freien Tag gesammelt nachgeholt (mehrere Spritzungen an einem Tag möglich). Beleg: Vorauflauf-Herbizid Bandur Artist geplant für den Tag der N-Düngung, ausgeführt erst 2027-04-22 (Folgetag). Bei Krautfäule-Fungiziden gefährdet das die 7–10-Tage-Spritzfolge. | KAR-021 (weich verletzbar); Feld 2026200: wt=23 `2027-04-21`, wt=14 Bandur Artist `2027-04-22`; Logik: `ProtectionPlanService.get_next_operations()` liefert ALLE überfälligen Ops | **mittel** | `WorkTypePriorityStrategy` (pauschale Unterdrückung, kein Nachhol-/Fälligkeitskonzept) |
| B10 | **Unplausible Arbeitsdauern/Nachtarbeit**: Separieren läuft 34,8 h durchgehend (2027-04-11 06:03 → 04-12 16:51), Grubbern 17,8 h bis 07:08 früh, Beregnung 33,7 h am Stück (121 464 s). Real würden solche Arbeiten auf mehrere Tage/Schichten aufgeteilt. | KAR-045 (weich); Feld 2026200: wt=28 `duration=125280` s; wt=15 `duration=121464` s | **niedrig** | Event-Erzeugung in `PlantingPlanService`/`IrrigationSimulator`: Dauer = ha × h/ha ohne Tagesarbeitszeit-Begrenzung |
| B11 | **Label/Worktype-Inkonsistenz**: Operation „Kreiseln“ ist als Worktype 7 (Eggen) kodiert; Kreiselegge wäre fachlich näher an Fräsen (9) bzw. eigenem Typ. Zudem Inkonsistenz beim Feuchte-Schwellwert: `CalendarDrivenRunner` übergibt `min_moisture_level=200` an den `MoistureDataService`, der `IrrigationSimulator` nutzt aber 50 (% nFK) aus dem Fallback. | KAR-034 (Konfig-Hygiene); Belege: `config/planting_plan_potato.json` (worktype 7 für „Kreiseln“), `calendar_driven_runner.py` Z. 219 vs. `irrigation_service.py` Z. 12/29 | **niedrig** | Konfiguration + tote/inkonsistente Parameter |
| B12 | **Wachstumsdauer 90 Tage zu knapp für Belana**: Roden erfolgt bei Legen+90…95 Tagen; bei Legetermin Ende April fällt die Ernte in den Juli/August statt September–Oktober (Konfig deklariert `harvest_period_months: [9,10]`, nutzt sie aber nicht — Ernte ist rein `growth_duration`-getrieben). | KAR-011/KAR-047 (weich); Beleg: `growth_duration=90` und `PlantingPlanService.update_phase_status()` Z. 147 (`harvest_date = planting + grow_duration`) | **niedrig** | `config/planting_plan_potato.json` + `PlantingPlanService` (harvest_period_months wird ignoriert) |

---

## Verifikation durch 760-Tage-Lauf (Feld 990001, Seed 42)

Event-Belege aus `export/fast_forward/audit_baseline_990001_760days.json` (Saison 2027: Grubbern 2027-04-17 → Lagerung 2027-08-13):

| Befund | Status | Beleg aus dem Lauf |
|---|---|---|
| B1 (Jahreszahl Beregnung) | **bestätigt** | Alle 7 Beregnungs-Events datiert 2026-06-05 … 2026-07-22, obwohl die Saison 2027 läuft (Legen 2027-05-10). Im Export erscheinen sie dadurch VOR dem Legen → verletzt zusätzlich KAR-006/KAR-015. |
| B3 (Beregnungsgaben zu klein) | **bestätigt** | Gaben 4,13 / 5,51 / 5,75 / 5,82 / 6,35 / 6,69 / 7,66 mm — alle unter der harten 10-mm-Grenze (KAR-040); 4,13 mm unterschreitet erneut den eigenen 5-mm-Mindestwert. |
| B5 (Sikkation→Roden < 14 Tage) | **bestätigt, jetzt Event-Beleg** | Quickdown 2027-08-05 → Roden 2027-08-10 = **5 Tage** statt ≥ 14 (KAR-020). |
| B6 (Pflanzenschutz nach Roden) | **bestätigt, jetzt Event-Beleg** | Roden 2027-08-10; danach Spritzen 2027-08-11 (Shaktis 10:27 **und** zweite Quickdown-Sikkation 12:54 — Sikkation NACH der Ernte) (KAR-005). |
| B7 (Intra-Tages-Sequenz) | **bestätigt** | 2027-05-10: Pflanzen 14:10 vor Pflanzguttransport 15:55 — Transport des Pflanzguts nach dem Legen (KAR-003). |
| B10 (Dauerbetrieb) | **bestätigt** | Roden 50,0 h am Stück, Separieren 34,8 h, Beregnung 22–31 h (KAR-045). |
| B12 (Erntetermin zu früh) | **bestätigt, jetzt Event-Beleg** | Roden am 2027-08-10 (Monat 8, weiche Verletzung KAR-011); `harvest_period_months: [9,10]` wird ignoriert. |

### Neue Befunde

| # | Problem | Beleg | Schweregrad | Vermutete Ursache / Komponente |
|---|---|---|---|---|
| B13 | **HarvestCompleted-Event wird nach der Ernte täglich erneut emittiert** (170× statt 1×), bis zum Simulationsende — es fehlt ein Terminal-/Idle-Zustand nach Zyklusabschluss. Verwässert die Domain-Event-Historie und macht Replays/Audits unnötig teuer. | Domain-Event-Dump: 1795 Events, davon 170× `HarvestCompleted` (täglich ab 2027-08-13) | mittel | `CalendarDrivenRunner.tick()`: Harvest-Completed-Zweig feuert bei jedem Tick nach Zyklusende erneut; kein Zustandsübergang in „Zyklus abgeschlossen" |
| B14 | **Grunddüngung (P) erst NACH dem Legen**: Superphosphat am 2027-05-23, das Legen war am 2027-05-10. P/Kali gehören als Grunddüngung vor das Legen (Kali korrekt am 2027-05-08). | KAR-016; wt=23 „P Düngung" 2027-05-23 > wt=26 2027-05-10 | mittel | Planungslogik `PlantingPlanService` / `planting_plan_potato.json` (P-Düngung in Pflege-Phase statt Bodenbearbeitung) |

Weitere Beobachtung (kein eigener Befund): Der DecisionManager lehnte im gesamten Lauf nur **1 von 35** Kandidaten ab (`OperationRejected`=1) — die Entscheidungslogik ist faktisch ein Durchreicher; konsistent mit B8.

---

## Fazit — wichtigste Handlungsfelder

1. **Zeit-/Kalenderkonsistenz herstellen (B1, B2):** Beregnungs-Events müssen das reale Simulationsdatum tragen; die Legetermin-Planung in `start_year+1` führt zu leeren Jahresläufen und verschleiert alle weiteren Fehler. Ohne Fix ist jede Event-Auswertung über Jahresgrenzen unbrauchbar.
2. **Wetter-/Bodenkopplung der Entscheidungen (B4, B8):** Bodenfeuchte aus korrektem Jahr und Feldstandort beziehen; DecisionManager um Regen-/Wind-/Bodenfeuchte-Guards (KAR-030 bis KAR-034) erweitern — Kernvermutung des Product Owners bestätigt.
3. **Abstands- und Reihenfolgeregeln durchsetzen (B5, B6, B7):** Insbesondere Sikkation→Roden ≥ 14 Tage, keine Maßnahmen nach dem Roden, Sequenztreue innerhalb eines Tages; Protection-Plan am Pflanzdatum verankern und gegen den Erntetermin beschneiden.
4. **Beregnungsfachlichkeit (B3):** Zielgaben von 20–30 mm mit Mindestintervall statt täglicher Kleinstgaben; Schwellwertprüfung nach der Mengenrandomisierung.
5. **Terminkritik im Pflanzenschutz (B9):** Fungizid-Spritzfolgen (7–10 Tage) dürfen durch die pauschale Prioritätsunterdrückung nicht aufgeschoben/gestaut werden; Nachholregeln mit Fälligkeitsfenstern einführen.

6. **Zyklusabschluss sauber modellieren (B13):** Nach der Ernte muss der Zyklus in einen Terminal-Zustand übergehen; `HarvestCompleted` darf genau einmal emittiert werden.

**Status:** Der empfohlene 760-Tage-Referenzlauf (Seed 42) liegt vor und dient als Baseline für die Plausibilitäts-Testsuite. Alle harten Kernbefunde (B1–B6) sind mit Event-Belegen verifiziert.
