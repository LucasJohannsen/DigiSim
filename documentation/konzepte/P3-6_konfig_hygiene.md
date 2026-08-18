# P3-6 — Konfig-Hygiene (Befund B11)

## Problem

Label/Worktype-Inkonsistenz: „Kreiseln" ist als Worktype 7 (Eggen) kodiert, fachlich näher an Fräsen (9) oder eigenem Typ. Parameter `min_moisture_level=200` wird an `MoistureDataService` übergeben, aber `IrrigationSimulator` nutzt 50 (% nFK) aus dem Fallback.

Verletzte Regel: KAR-034 (Konfig-Hygiene: Datenkonsistenz).

## Zielverhalten

Worktype-Labels sind fachlich korrekt. Tote/inkonsistente Parameter werden entfernt oder genutzt.

## Lösungsdesign

### Worktype-Korrektur

**Analyse:** „Kreiseln" (Kreiselegge) ist eine Bodenbearbeitungsmaßnahme zwischen Grubbern und Eggen. In DigiZert existiert kein dedizierter Worktype. Optionen:

1. **Worktype 7 (Eggen) beibehalten** – fachlich akzeptabel, da Kreiselegge eine Eggen-Variante ist
2. **Worktype 9 (Fräsen) verwenden** – fachlich näher, aber Fräsen ist tiefergehende Bodenbearbeitung
3. **Neuer Worktype** – nicht möglich ohne DigiZert-Änderung

**PO-Entscheidung:** **Worktype 7 (Eggen) beibehalten.** Label in `config/planting_plan_potato.json` anpassen für Klarheit:

```json
{
  "operation": "Kreiseln (Eggen)",
  "worktype": 7
}
```

### Parameter-Hygiene

**`min_moisture_level=200` in `CalendarDrivenRunner`:**

Der Parameter wird an `MoistureDataService` übergeben, aber nicht verwendet (Z. 340). Optionen:

1. **Parameter entfernen** – wenn er keine Funktion hat
2. **Parameter nutzen** – wenn er eine Funktion haben soll (z. B. Schwellwert für Beregnungstrigger)

**Analyse:** `IrrigationSimulator` nutzt `min_moisture_level=50` (% nFK) aus dem Fallback. Der Wert 200 in `CalendarDrivenRunner` ist inkonsistent (Einheit? % nFK? mm?).

**Empfehlung:** Parameter entfernen und Konsistenz herstellen:

```python
# scheduler/calendar_driven_runner.py

def _initialize_services(self, current_date: datetime.date) -> None:
    # ...
    if self._moisture_service_factory is not None:
        ms = self._moisture_service_factory()
    else:
        # min_moisture_level=200 entfernt – Konsistenz mit IrrigationSimulator (50 % nFK)
        ms = MoistureDataService(context=self.context)
    # ...
```

### Konfigurations-Validierung

Optionale Validierung beim Laden der Konfiguration:

```python
# utils/config_validator.py

def validate_planting_plan(config: dict) -> list[str]:
    """Validiert planting_plan-Konfiguration auf Konsistenz."""
    warnings = []
    
    # Prüfe Worktype-Konsistenz
    for phase in config.get("phases", []):
        for op in phase.get("operations", []):
            wt = op.get("worktype")
            if wt == 7 and "Kreiseln" in op.get("operation", ""):
                warnings.append(
                    f"Worktype 7 (Eggen) verwendet für 'Kreiseln' – "
                    f"fachlich akzeptabel, aber Label sollte konsistent sein"
                )
    
    return warnings
```

## Betroffene Dateien

- Ändern: `config/planting_plan_potato.json` (Label-Anpassung für Kreiseln)
- Ändern: `scheduler/calendar_driven_runner.py` (min_moisture_level=200 entfernen)
- Optional: Neu: `utils/config_validator.py`
- Tests: `tests/test_config_validation.py` (optional)

## Akzeptanzkriterien

1. Worktype-Labels sind konsistent mit fachlicher Bedeutung (Dokumentation)
2. Toter Parameter `min_moisture_level=200` ist entfernt
3. Konsistenz-Check für Konfiguration existiert (optional)
4. Plausibilitätstest für KAR-034 (Konfig-Hygiene) wird von xfail auf aktiv umgestellt

## Testhinweise

Manuelle Prüfung der Konfiguration. Optionaler automatischer Check beim Laden.

## Aufwandsschätzung

S (einfache Konfigurationsänderung)

## Abhängigkeiten

Keine (unabhängig implementierbar)

## PO-Entscheidungen (eingearbeitet)

- **Worktype für Kreiseln:** Worktype 7 (Eggen) beibehalten, Label auf „Kreiseln (Eggen)" klarstellen
