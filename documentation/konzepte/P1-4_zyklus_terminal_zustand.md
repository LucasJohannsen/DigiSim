# P1-4 — Terminal-Zustand nach Zyklusabschluss, HarvestCompleted genau 1× (Befund B13)

## Problem

`CalendarDrivenRunner.tick()` emittiert `HarvestCompleted` bei **jedem** Tick, sobald die Harvest-Phase abgeschlossen ist (`scheduler/calendar_driven_runner.py`, Z. 168–176). Beleg (Referenzlauf 990001): 170× `HarvestCompleted` (täglich vom Erntetag bis Simulationsende). Der Zyklus kennt keinen Terminal-Zustand; die Domain-Event-Historie wird verwässert, Replay/Audit unnötig teuer.

## Zielverhalten

- `HarvestCompleted` wird **genau einmal** je Anbauzyklus emittiert — an dem Tick, an dem die Harvest-Phase erstmals abgeschlossen ist
- Danach befindet sich der Zyklus in einem expliziten Terminal-Zustand („completed"); Ticks in diesem Zustand erzeugen keine Zyklus-Events mehr (DailyTick-Events bleiben)
- Der Zustand überlebt Neustarts (Persistenz), sodass der Live-Daemon nach Restart kein zweites `HarvestCompleted` sendet

## Lösungsdesign

- **Expliziter Zyklus-Zustand** im `CalendarDrivenRunner` statt verstreuter Flags:
  `CropCycleState` (Enum: `SCHEDULED`, `RUNNING`, `COMPLETED`) als leichtgewichtiger Zustandsautomat.
  - `SCHEDULED → RUNNING`: bei `CropCycleStarted` (ersetzt das bestehende `_crop_cycle_started`-Flag)
  - `RUNNING → COMPLETED`: beim ersten Erkennen der abgeschlossenen Harvest-Phase; genau hier `HarvestCompleted` publizieren (Event zuerst, dann Zustandsübergang als `apply(event)` — Styleguide-Muster)
  - Im Zustand `COMPLETED`: keine erneute Emission; `_reset_services()` wie bisher
- **Persistenz:** `FieldStateSnapshot` (utils/state_manager.py) um `crop_cycle_state: str` erweitern; `get_state_snapshot()`/`apply_state_snapshot()` entsprechend ergänzen. Abwärtskompatibel: fehlt das Feld in alten Snapshots, wird der Zustand wie bisher aus dem Phasenstatus abgeleitet.
- Out of scope (Folge-Issue, MS-übergreifend): automatischer Übergang `COMPLETED → SCHEDULED` für die nächste Saison (Mehrjahresbetrieb). Hier nur sauberer Terminal-Zustand.

## Betroffene Dateien

- `scheduler/calendar_driven_runner.py` (Zustandsautomat, Emissions-Guard)
- `utils/state_manager.py` (Snapshot-Feld)
- Tests: `tests/test_calendar_driven_runner.py`, `tests/test_state_manager.py`, `tests/test_event_integration.py`

## Akzeptanzkriterien

1. FF-Lauf über volle Saison + 100 Tage Nachlauf: Domain-Event-Historie enthält **genau 1×** `HarvestCompleted` und **genau 1×** `CropCycleStarted`
2. Snapshot nach der Ernte speichern, Runner neu instanziieren, Snapshot laden, weitere Ticks ausführen → kein weiteres `HarvestCompleted`
3. Alte Snapshots ohne `crop_cycle_state` laden fehlerfrei (Abwärtskompatibilität)
4. Plausibilitätstest xfail-B13 (P1-1) wird grün → Marker entfernen

## Testhinweise

Bestehender Referenzlauf zeigt das Fehlverhalten (170×) — als Regressionsmaßstab nutzen. Beim Umstellen von `_crop_cycle_started` auf den Enum-Zustand alle Verwendungen greppen.

## Aufwandsschätzung

S

## Abhängigkeiten

Unabhängig; kombiniert gut mit P1-2 in einem Test-Setup (365-Tage-Lauf mit vollständigem Zyklus).
