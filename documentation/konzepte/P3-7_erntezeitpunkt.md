# P3-7 — Erntezeitpunkt mit harvest_period_months (Befund B12)

## Problem

Wachstumsdauer 90 Tage zu knapp für Belana (Ernte Juli/Aug statt Sep/Okt). `PlantingPlanService` berechnet `harvest_date = planting + grow_duration` (Z. 245). Das Konfigurationsfeld `harvest_period_months: [9,10]` wird ignoriert.

Verletzte Regeln: KAR-011 (hart: Roden September–Oktober), KAR-047 (soft: Roden 90–150 Tage nach Legen, Belana ~100–120 Tage).

## Zielverhalten

`growth_duration` bleibt die **primäre Quelle** für den Erntetermin (`harvest_date = planting + growth_duration`). `harvest_period_months` dient als **Validierung** – fällt der berechnete Erntetermin außerhalb des konfigurierten Erntefensters (z. B. September–Oktober), wird er auf das Fenster verschoben (frühestes zulässiges Datum). Für Belana wird `growth_duration` auf 110 Tage angepasst (mittelfrüh, ~100–120 Tage).

## Lösungsdesign

### Anpassung von growth_duration

**Konfiguration:**

```json
{
  "crop": "Potato",
  "variety": "Belana",
  "growth_duration": 110,  // von 90 auf 110 angepasst (mittelfrüh)
  "harvest_period_months": [9, 10]
}
```

### growth_duration primär, harvest_period_months als Validierung

**Änderung an PlantingPlanService.update_phase_status():**

```python
# services/planting_plan_service.py

class PlantingPlanService:
    def update_phase_status(self, date: datetime):
        # ... bestehende Logik ...
        
        elif next_phase.phase_name == FieldOperationPhases.HARVESTING.value:
            actual_planting_date = max(
                op.actual_date
                for op in sim_helper.get_operations_by_phase(
                    self.planting_plan, "sowing_planting"
                )
                if op.actual_date
            )
            
            # PRIMÄR: harvest_date aus growth_duration
            harvest_date = actual_planting_date + timedelta(
                days=self.planting_plan.grow_duration
            )
            
            # VALIDIERUNG: harvest_period_months als Korrektur-Fenster
            harvest_period_months = self.planting_plan.harvest_period_months
            if harvest_period_months:
                if harvest_date.month not in harvest_period_months:
                    # Erntetermin liegt außerhalb des Fensters → verschieben
                    target_month = harvest_period_months[0]
                    harvest_year = actual_planting_date.year
                    if target_month < actual_planting_date.month:
                        harvest_year += 1
                    # Frühestes zulässiges Datum im Zielmonat
                    corrected = datetime.date(harvest_year, target_month, 1)
                    # Nur verschieben, wenn es NACH dem growth_duration-Mindest-
                    # termin liegt (nicht vorverlegen unter biologische Reife)
                    if corrected > harvest_date:
                        harvest_date = corrected
                    logger.info(
                        "Erntetermin aus growth_duration (%s) außerhalb "
                        "harvest_period_months %s → korrigiert auf %s",
                        harvest_date, harvest_period_months, corrected
                    )
            
            self.update_planned_operations_startdates(
                next_phase.phase_name, harvest_date
            )
```

## Betroffene Dateien

- Ändern: `config/planting_plan_potato.json` (growth_duration: 110)
- Ändern: `services/planting_plan_service.py` (update_phase_status)
- Tests: `tests/test_planting_plan_service.py`

## Akzeptanzkriterien

1. Roden erfolgt im September oder Oktober (KAR-011)
2. Roden liegt 100–120 Tage nach dem Legen (KAR-047)
3. `growth_duration` ist primäre Quelle für den Erntetermin
4. `harvest_period_months` validiert und korrigiert bei Abweichung (nur Verschiebung nach hinten, nicht unter biologische Reife)
5. Plausibilitätstest xfail-B12 wird grün → Marker entfernen

## Testhinweise

Integrationstest: Legen am 01.05. + 110 d → Roden am ~19.08. (Monat 8, außerhalb [9,10]) → Korrektur auf 01.09. Unit-Test für update_phase_status mit verschiedenen Pflanzterminen und growth_duration-Werten.

## Aufwandsschätzung

S (enge Änderung an einer Klasse + Konfiguration)

## Abhängigkeiten

Keine (unabhängig implementierbar)

## PO-Entscheidungen (eingearbeitet)

- **Erntezeitpunkt-Strategie:** `growth_duration` primär, `harvest_period_months` als Validierung (Korrektur nur nach hinten, nicht unter biologische Reife)
