# MS6/P3 Abschlussbericht – Fachliche Härtung (P3-1 bis P3-7)

**Datum:** 2026-08-19 · **Branch:** `dev` @ `15a118d` · **Baseline:** 30 Integration / 1654 Domain Events (Seed 42, Feld 990001, 760 d)

## Übersicht

MS6/P3 umfasste 7 Packages (P3-1 bis P3-7), die verbleibende fachliche Befunde (B3, B4, B8, B9, B10, B11, B12) adressieren. P3-8 (ISIP-Anbindung) wurde ins Backlog verschoben (MS7, Issue #86).

| Package | Issue | PR | Befund | KAR-Regel | Status |
|---------|-------|-----|--------|-----------|--------|
| P3-1 Wetterdaten-Service | #79 | #87 | B4 | KAR-034 | ✅ gemerged |
| P3-2 Wetter-Guards | #80 | #88 | B8 | KAR-030/031/032/035 | ✅ gemerged |
| P3-3 Beregnungsmengen | #81 | #89 | B3 | KAR-040 | ✅ gemerged |
| P3-4 Pflanzenschutz-Prio | #82 | #90 | B9 | KAR-021 | ✅ gemerged |
| P3-5 Arbeitszeiten | #83 | #91 | B10 | KAR-045 | ✅ gemerged |
| P3-6 Konfig-Hygiene | #84 | #92 | B11 | KAR-034 | ✅ gemerged |
| P3-7 Erntezeitpunkt | #85 | #93 | B12 | KAR-011/047 | ✅ gemerged |
| P3-8 ISIP-Anbindung | #86 | – | – | – | ⏳ Backlog (MS7) |

## Baseline-Entwicklung

| Schritt | Integration Events | Domain Events | Änderung |
|---------|-------------------|---------------|----------|
| Vor P3 (P2-5c) | 29 | 1613 | – |
| P3-1 (Wetterdaten-Service) | 29 | 1613 | unverändert (field_coords=None → alte Logik) |
| P3-2 (Wetter-Guards) | 27 | 1649 | -2 Ops, +36 Rejection-Events (21 Guard-Rejections) |
| P3-3 (Beregnungsmengen) | 26 | 1634 | -1 Beregnung, KAR-040 grün (feste Zielgabe 20-30 mm) |
| P3-4 (Pflanzenschutz-Prio) | 26 | 1646 | +12 Domain Events (DeadlineAwarePriorityStrategy) |
| P3-5 (Arbeitszeiten) | 28 | 1648 | +2 Integration Events (mehrtägige Aufteilung) |
| P3-6 (Konfig-Hygiene) | 28 | 1648 | unverändert (Label + Parameter-Hygiene) |
| **P3-7 (Erntezeitpunkt)** | **30** | **1654** | +2 Ops, +6 Domain Events (growth_duration 110, Ernte Sep) |

## KAR-Regel-Status nach MS6/P3

### Aktiv und grün
| KAR | Beschreibung | Geprüft durch |
|-----|--------------|---------------|
| KAR-011 | Roden September–Oktober | Plausibilitäts-Suite (seit P3-7) |
| KAR-021 | Fungizidabstände ≥ 3 Tage, 5–14 Tage | Plausibilitäts-Suite (seit P3-4) |
| KAR-040 | Beregnungsgaben 10–40 mm, plausibel 20–30 mm | Plausibilitäts-Suite (seit P3-3, war xfail) |
| KAR-045 | Arbeitsbeginn 05:00–20:00, max. 18 h Dauer | Plausibilitäts-Suite (seit P3-5) |
| KAR-047 | Roden 90–150 Tage nach Legen | Plausibilitäts-Suite (seit P3-7) |

### xfail (bekannte Verletzung)
| KAR | Beschreibung | Befund | Status |
|-----|--------------|--------|--------|
| KAR-024 | Quickdown-Abstand ≥ 14 Tage (Sikkation→Roden) | B5/B6 | xfail(strict=True) – Abstand 69 d außerhalb [4,7] |

### skipped (Wetter-Regeln, benötigen Dry-Wetter-Fixture)
| KAR | Beschreibung | Grund |
|-----|--------------|-------|
| KAR-030 | Kein Spritzen bei Regen >5 mm oder Wind >5 m/s | weather_skip (Guard arbeitet auf Decision-Level, Plausibilitäts-Checker auf Event-Sequenzen) |
| KAR-031 | Keine Beregnung bei Prognose-Niederschlag >10 mm | weather_skip |
| KAR-032 | Keine Bodenbearbeitung auf nassem Boden >90 % nFK | weather_skip |
| KAR-034 | Beregnungsauslösung bei nFK < 50 %, Jahres-/Standortkopplung | weather_skip |
| KAR-035 | Keine Sikkation bei Hitze >30°C | weather_skip |

**Hinweis:** Die Wetter-Guards (P3-2) arbeiten auf Decision-Level (OperationRejected-Events). Die Plausibilitäts-Checker prüfen Event-Sequenzen. Für aktive Plausibilitäts-Prüfung der Wetter-Regeln wird eine Dry-Wetter-Fixture benötigt (Folge-Aufgabe).

## Architektur-Änderungen in MS6/P3

### P3-1: Wetterdaten-Service (Fundament)
- **Neu:** `services/weather_service.py` – `WeatherData`, `WeatherDataProvider` (Protocol), `WeatherDataService` (Caching, get_weather_for_date, get_forecast)
- **Neu:** `services/providers/` – `DWDWeatherDataProvider` (DWD netCDF, dynamischer Jahres-Fallback), `SyntheticWeatherDataProvider` (deterministischer Stub)
- **Erweitert:** `CycleContext` um `current_weather`, `weather_forecast` (für P3-2 Wetter-Guards)
- **Erweitert:** `CalendarDrivenRunner` um `weather_service_factory` (analog `moisture_service_factory`)
- **Erweitert:** `SimContext` um `field_coords` (konfigurierbarer Feldstandort)
- **Konsolidiert:** `MoistureDataService` – dynamischer Jahres-Fallback statt hart `YEAR=2022`

### P3-2: Wetter-Guards
- **Neu:** 3 Guard-Klassen in `scheduler/decision_manager.py`:
  - `WeatherConditionGuard` (KAR-030/035): Niederschlag, Wind, Temperatur
  - `SoilConditionGuard` (KAR-032): Bodenfeuchte, Vortagesniederschlag
  - `ForecastConditionGuard` (KAR-031): Prognose-Niederschlag kumuliert
- **Erweitert:** `scheduler/guard_rule_loader.py` um 3 neue `check_type`-Handler
- **Erweitert:** `config/decision_guards_potato.json` (Version 2.0, 7 Guards gesamt)

### P3-3: Beregnungsmengen
- **Geändert:** `services/irrigation_service.py` – Feste Zielgabe 25 mm ±20 % (→ 20–30 mm), Clamping [10, 40] mm, Post-Irrigation-Block 10 Tage, saisonales Limit 170 mm
- **Entfernt:** KAR-040 xfail-Marker (Beregnungsgaben jetzt fachlich korrekt)

### P3-4: Pflanzenschutz-Priorität
- **Neu:** `DeadlineAwarePriorityStrategy` in `scheduler/decision_manager.py` (ersetzt `WorkTypePriorityStrategy` als Standard)
- **Erweitert:** `FieldOperation` um `due_date`, `due_window_days`, `is_critical`
- **Erweitert:** `config/planting_plan_potato.json` – Fungizide (type=27) als `is_critical=true` mit `due_window_days=5`
- **Erweitert:** `ProtectionPlanService` berechnet `due_date = planned_date + due_window_days`

### P3-5: Arbeitszeiten
- **Geändert:** `services/planting_plan_service.py` – Mehrtägige Aufteilung bei Dauer > 18 h (proportionale Fläche/Menge), Arbeitsfenster [05:00, 22:00]
- **Geändert:** `services/irrigation_service.py` – `_create_irrigation_events` (plural, Liste)
- **Design-Entscheidung:** wt=26 (Legen) und wt=27 (Roden) werden nicht aufgeteilt (KAR-046-Schutz: genau 1 Event/Zyklus)

### P3-6: Konfig-Hygiene
- **Geändert:** `config/planting_plan_potato.json` – Label „Kreiseln" → „Kreiseln (Eggen)"
- **Entfernt:** Toter Parameter `min_moisture_level=200` in `CalendarDrivenRunner`
- **Neu:** `utils/config_validator.py` – `validate_planting_plan()` (Fail-open Konsistenz-Check)

### P3-7: Erntezeitpunkt
- **Geändert:** `config/planting_plan_potato.json` – `growth_duration` 90 → 110 (Belana mittelfrüh)
- **Neu:** `PlantingPlanService._compute_harvest_date()` – `growth_duration` primär, `harvest_period_months` als Validierung (Korrektur nur nach hinten)

## Test-Status

- **540 passed**, 18 skipped, 2 xfailed (KAR-024 ×2: Baseline + Dry)
- **Dry-Suite:** 35 passed, 6 skipped, 1 xfailed
- **Ruff:** Keine neuen Errors (pre-existing: F841 in `fast_forward_runner.py`, F841 in `planting_plan_service.py`)
- **Mypy:** Keine neuen Errors (pre-existing: 41 in `planting_plan_service.py`, 3 in `decision_manager.py`)

## Offene Punkte

1. **KAR-024 (xfail):** Quickdown-Abstand 69 d außerhalb [4,7] – nicht durch P3 adressiert. Erfordert vermutlich Konfigurationsänderung (Sikkation früher planen) oder zusätzliche Guard-Regel.
2. **Wetter-Regeln skipped (KAR-030–035):** Plausibilitäts-Checker benötigen Dry-Wetter-Fixture für aktive Prüfung. Wetter-Guards arbeiten auf Decision-Level (OperationRejected), nicht auf Event-Sequenzen.
3. **P3-8 ISIP-Anbindung (#86):** Ins Backlog verschoben (MS7). Benötigt ISIP-API-Credentials vom PO.
4. **Vortagesniederschlag (KAR-032):** MVP nutzt Tagesniederschlag als Näherung. Echte Vortages-Prüfung benötigt WeatherService-History (Folge-Aufgabe).
5. **Dry-Wetter-Fixture:** Für aktive Plausibilitäts-Prüfung der Wetter-Regeln (Folge-Aufgabe).
