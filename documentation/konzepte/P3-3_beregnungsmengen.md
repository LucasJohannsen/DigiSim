# P3-3 — Beregnungsmengen fachlich korrigieren (Befund B3)

## Problem

Beregnungsgaben sind fachlich unwirksam klein (4–8 mm statt 20–30 mm). `IrrigationSimulator.get_candidate_operations()` berechnet die Gabe als exaktes Defizit × Zufall (0.8–1.2), ohne Mindest-/Zielgabe. Die Schwellwertprüfung (`irrigation_needed >= 5`) erfolgt **vor** der Randomisierung, sodass eine 5-mm-Anforderung nach ×0.8 auf 4 mm fallen kann (unter dem eigenen Mindestwert).

Verletzte Regeln: KAR-040 (hart: 10–40 mm, plausibel 20–30 mm), KAR-041 (soft: saisonale Summe 30–180 mm).

## Zielverhalten

Beregnungsgaben liegen im fachlich plausiblen Bereich (20–30 mm mit Zufallsstreuung). Die Schwellwertprüfung erfolgt **nach** der Mengenberechnung. Nach einer Beregnung wird für **10 Tage** keine weitere Beregnung geplant (Block-Frist). Die saisonale Summe ist auf **max. 170 mm** begrenzt – nach Erreichen der Obergrenze werden keine weiteren Beregnungs-Kandidaten erzeugt.

## Lösungsdesign

### Änderung an IrrigationSimulator

**Konfiguration:** Zielgabe und Toleranz aus Konfiguration oder Parametern:

```python
# services/irrigation_service.py


class IrrigationSimulator:
    def __init__(
        self,
        context: SimContext,
        moisture_data: dict,
        target_application_mm: float = 25.0,  # Zielgabe (Mitte 20-30 mm)
        target_tolerance_pct: float = 0.2,  # ±20% Toleranz → 20-30 mm
        min_application_mm: float = 10.0,  # KAR-040 Mindestwert
        max_application_mm: float = 40.0,  # KAR-040 Maximalwert
        seasonal_max_mm: float = 170.0,  # PO: max 170 mm/Saison
        post_irrigation_block_days: int = 10,  # PO: 10 Tage Block nach Beregnung
    ):
        self.context = context
        self.moisture_data = moisture_data
        self.target_application_mm = target_application_mm
        self.target_tolerance_pct = target_tolerance_pct
        self.min_application_mm = min_application_mm
        self.max_application_mm = max_application_mm
        self.seasonal_max_mm = seasonal_max_mm
        self.post_irrigation_block_days = post_irrigation_block_days
        # ... rest wie bisher
```

**Neue Logik in `get_candidate_operations()`:**

```python
def get_candidate_operations(self, date: datetime.date) -> List[FieldOperationEvent]:
    # 1. Saisonsummen-Limit: keine weiteren Beregnungen, wenn Obergrenze erreicht
    if self.seasonal_sum_mm >= self.seasonal_max_mm:
        return []

    # 2. Post-Irrigation-Block: 10 Tage nach letzter Beregnung keine neue
    if self._last_irrigation_date is not None:
        block_until = self._last_irrigation_date + timedelta(days=self.post_irrigation_block_days)
        if date < block_until:
            return []

    try:
        status = self.get_status_for_day(date)
    except IndexError:
        return []

    # Trigger-Prüfung: Defizit >= 5 % nFK UND keine Prognose über Threshold
    if not status["needs_irrigation"]:
        return []

    # NEUE LOGIK: Feste Zielgabe statt Defizit-basiert
    # Berechne Zielgabe mit Zufallsstreuung (20-30 mm)
    base_amount = self.target_application_mm
    random_factor = np.random.uniform(
        1.0 - self.target_tolerance_pct, 1.0 + self.target_tolerance_pct
    )
    irrigation_amount = base_amount * random_factor

    # Begrenzung auf KAR-040-Grenzen
    irrigation_amount = max(self.min_application_mm, irrigation_amount)
    irrigation_amount = min(self.max_application_mm, irrigation_amount)

    # Saisonsummen-Begrenzung: nicht über 170 mm kippen
    remaining_budget = self.seasonal_max_mm - self.seasonal_sum_mm
    if irrigation_amount > remaining_budget:
        # Letzte Gabe auf Restbudget begrenzen (mind. min_application_mm)
        if remaining_budget >= self.min_application_mm:
            irrigation_amount = remaining_budget
        else:
            return []  # Budget erschöpft

    # Schwellwertprüfung NACH der Randomisierung
    if irrigation_amount < self.min_application_mm:
        return []

    event = self._create_irrigation_event(date, irrigation_amount)
    return [event]
```

**Legacy-Methode `trigger_irrigation()` analog anpassen.**

### Saisonale Summen-Prüfung (KAR-041)

Saisonale Summe tracken und bei Überschreitung keine weiteren Kandidaten erzeugen:

```python
class IrrigationSimulator:
    def __init__(self, ...):
        # ...
        self.seasonal_sum_mm = 0.0
        self.seasonal_max_mm = 170.0  # PO-Vorgabe
        self._last_irrigation_date: datetime.date | None = None
        self.post_irrigation_block_days = 10  # PO-Vorgabe
    
    def apply_irrigation(self, date: datetime.date, irrigation_amount: float) -> None:
        # ... bestehende Logik ...
        self.seasonal_sum_mm += irrigation_amount
        self._last_irrigation_date = date
        
        # Log bei Erreichen der Obergrenze
        if self.seasonal_sum_mm >= self.seasonal_max_mm:
            logger.info(
                "Saisonale Beregnungssumme %s mm erreicht Obergrenze %s mm – "
                "keine weiteren Beregnungen",
                self.seasonal_sum_mm, self.seasonal_max_mm
            )
```

### Konfiguration

Optional: Parameter in `config/planting_plan_potato.json` oder separater `config/irrigation_config.json`:

```json
{
  "crop": "Potato",
  "irrigation": {
    "target_application_mm": 25,
    "target_tolerance_pct": 0.2,
    "min_application_mm": 10,
    "max_application_mm": 40,
    "seasonal_max_mm": 170,
    "post_irrigation_block_days": 10
  }
}
```

## Betroffene Dateien

- Ändern: `services/irrigation_service.py` (Konstruktor, get_candidate_operations, trigger_irrigation)
- Optional: `config/planting_plan_potato.json` oder neu `config/irrigation_config.json`
- Tests: `tests/test_irrigation_candidates.py` (neue Testfälle für Zielgaben)

## Akzeptanzkriterien

1. Alle Beregnungs-Events haben `application_amount` im Bereich [10, 40] mm (KAR-040 hart)
2. Typische Gabe liegt im Bereich [20, 30] mm (KAR-040 soft)
3. Keine Gabe < 5 mm (eigener Mindestwert wird eingehalten)
4. Saisonale Summe liegt im Bereich [30, 170] mm (KAR-041 soft, Obergrenze 170 mm hard-stop)
5. Nach einer Beregnung werden für **10 Tage** keine weiteren Beregnungs-Kandidaten erzeugt (Post-Irrigation-Block)
6. Plausibilitätstest xfail-B3 (KAR-040) wird grün → Marker entfernen
7. State-Persistenz funktioniert unverändert (seasonal_sum_mm, _last_irrigation_date im Snapshot)

## Testhinweise

Unit-Test: `get_candidate_operations()` liefert Events mit Gabe im Zielbereich bei verschiedenen Defizit-Werten. Regressionstest mit Referenzlauf (Seed 42) – saisonale Summe sollte im plausiblen Bereich liegen.

## Aufwandsschätzung

S (enge Änderung an einer Klasse)

## Abhängigkeiten

P3-1 (für volle Fachlichkeit: Trigger-Logik mit korrekten Feuchtedaten aus Simulationsjahr/Standort). Kann technisch ohne P3-1 implementiert werden, aber KAR-034 (Jahres-/Standortkopplung) bleibt ohne P3-1 verletzt.

## PO-Entscheidungen (eingearbeitet)

- **Beregnungsmengen-Strategie:** Feste Zielgabe 20–30 mm (Mitte 25 mm, ±20 % Streuung)
- **Saisonale Obergrenze:** max 170 mm/Saison (hard-stop, keine weiteren Kandidaten nach Erreichen)
- **Post-Irrigation-Block:** 10 Tage nach letzter Beregnung keine neue Beregnung planen
