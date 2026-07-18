# P1-2 — Legetermin im Startjahr planen (Befund B2)

## Problem

`PlantingPlanService.initialize_planting_plan()` plant den Legetermin immer in `start_date.year + 1` (`services/planting_plan_service.py`, Z. 48–52). Folgen (Mängelbericht B2):

- Ein 365-Tage-Fast-Forward-Lauf ab 01.01. erzeugt **0 Events** (~15 Monate Leerlauf)
- Eine volle Saison benötigt ≥ 640 Simulationstage
- Der Live-Daemon simuliert nach jedem Neustart zunächst über ein Jahr lang nichts

Verletzte Regeln: KAR-010, KAR-046 (je Zyklus 1 Lege-/Rode-Event erwartet).

## Zielverhalten

Der Legetermin wird im **frühestmöglichen erreichbaren Pflanzfenster** geplant:

- Liegt `start_date` VOR oder IM Pflanzfenster (`planting_period_months`, z. B. April–Mai) und ist genügend Vorlauf für die Bodenbearbeitung vorhanden → Legetermin im **Startjahr**
- Ist das Fenster im Startjahr nicht mehr (vollständig) erreichbar → Legetermin im Folgejahr
- Ein Start am 01.01. führt zu einer vollständigen Saison im selben Kalenderjahr (Legen Apr/Mai, Roden Aug–Okt)

## Lösungsdesign

- Neue Hilfsfunktion in `PlantingPlanService` (oder `utils/sim_helper.py`):
  `resolve_planting_year(start_date, planting_period_months, lead_time_days) -> int`
  - `lead_time_days` = max. Vorlauf der Soil-Preparation-Operationen (aus dem Planting Plan ableitbar: betragsmäßig größtes `min_days_to_target` der Phase `soil_preparation`; Fallback: 30 Tage)
  - Regel: frühester zulässiger Legetermin = `start_date + lead_time_days`; liegt dieser noch vor Ende des Pflanzfensters im Startjahr → Startjahr, sonst Folgejahr. Der zufällige Termin wird dann innerhalb des verbleibenden Fensters gewürfelt (nicht vor `start_date + lead_time_days`).
- **Domain Event:** Nach Terminfindung `CropCycleScheduled` (neues Event in `models/domain_events.py`, Factory `create_crop_cycle_scheduled(field_id, date, planned_planting_date, crop_type)`) über den injizierten Event Bus publizieren (`if self.event_bus is not None`). Damit ist die Terminentscheidung nachvollziehbar (Styleguide: fachliches Ereignis zuerst benennen).
- Bestehende Persistenz (`FieldStateSnapshot`) bleibt kompatibel: `planned_planting_date` wird wie bisher aus den Operationen rekonstruiert; kein Migrationsbedarf.

## Betroffene Dateien

- `services/planting_plan_service.py` (Terminlogik)
- `models/domain_events.py` (+ `CropCycleScheduled`, Factory, `__all__`)
- ggf. `utils/sim_helper.py` (Datumshelfer)
- Tests: `tests/test_calendar_driven_runner.py`, neu `tests/test_planting_year_resolution.py`

## Akzeptanzkriterien

1. FF-Lauf 365 Tage ab 01.01. (Seed fix): Legen im Apr/Mai des **Startjahres**, Roden im selben Jahr, > 0 Events
2. Start am 15.06. (nach Fensterende inkl. Vorlauf): Legetermin im Folgejahr — bisheriges Verhalten als Spezialfall erhalten
3. Start am 01.04. (im Fenster): Legetermin ≥ `start_date + lead_time`, noch im Startjahr, sofern Fenster reicht
4. `CropCycleScheduled` wird genau 1× je Zyklus mit korrektem `planned_planting_date` emittiert
5. Plausibilitätstest „365-Tage-Lauf erzeugt vollständigen Zyklus" (P1-1, xfail-B2) wird grün → xfail-Marker entfernen

## Testhinweise

Parametrisierte Unit-Tests für `resolve_planting_year` (Grenzfälle: Start genau am Fensterende, Fenster über Jahreswechsel nicht nötig für Kartoffel). Integrationstest über `CalendarDrivenRunner` mit gemocktem MoistureDataService.

## Aufwandsschätzung

S–M

## Abhängigkeiten

P1-1 (Testsuite) sollte zuerst gemerged sein; blockiert die Aussagekraft von P1-3/P1-4-Läufen mit 365 Tagen.
