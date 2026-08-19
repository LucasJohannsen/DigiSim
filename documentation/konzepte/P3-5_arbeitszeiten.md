# P3-5 — Arbeitszeiten begrenzen (Befund B10)

## Problem

Arbeitsdauern sind unplausibel lang (34,8 h am Stück, Nachtarbeit bis 07:08 Uhr). Event-Erzeugung berechnet Dauer = ha × h/ha ohne Tagesarbeitszeit-Begrenzung.

Verletzte Regel: KAR-045 (soft: Arbeitsbeginn 05:00–22:00, Einzeloperation max. 18 h Dauer).

## Zielverhalten

Operationen werden auf realistische Arbeitszeiten begrenzt (05:00–22:00, max. 18 h Dauer). Lange Operationen werden auf mehrere Tage/Schichten aufgeteilt.

## Lösungsdesign

### Änderung an PlantingPlanService.get_events_for_ops()

**Tagesarbeitszeit-Begrenzung:**

```python
# services/planting_plan_service.py


class PlantingPlanService:
    def get_events_for_ops(
        self, operations: list[FieldOperation], date: datetime
    ) -> list[FieldOperationEvent]:
        events = []
        date_key = date.date() if isinstance(date, datetime) else date

        WORK_START_HOUR = 5
        WORK_END_HOUR = 22
        MAX_DURATION_HOURS = 18

        for operation in operations:
            # ... bestehende Logik für fuel_variation ...
            operation.actual_date = date

            # Berechne Gesamtdauer
            total_duration_hours = operation.duration_per_ha * self.context.field_size

            # Wenn Dauer zu lang: auf mehrere Tage aufteilen
            if total_duration_hours > MAX_DURATION_HOURS:
                # Teile in max. 18-h-Blöcke
                num_days = ceil(total_duration_hours / MAX_DURATION_HOURS)
                duration_per_day = total_duration_hours / num_days

                for day_idx in range(num_days):
                    op_date = date + timedelta(days=day_idx)
                    op_date_key = op_date.date() if isinstance(op_date, datetime) else op_date

                    # Sequenzkonforme Uhrzeit pro Tag
                    last_dt = self._last_assigned_time.get(op_date_key)
                    min_start = last_dt.time() if last_dt is not None else time(WORK_START_HOUR, 0)
                    op_datetime = sim_helper.assign_sequential_time(
                        op_date, min_start=min_start, max_end_hour=WORK_END_HOUR
                    )
                    self._last_assigned_time[op_date_key] = op_datetime

                    # Event für diesen Tag
                    event = self._create_event_for_day(operation, op_datetime, duration_per_day)
                    events.append(event)
            else:
                # Einzelne Operation (bestehende Logik mit Zeitfenster)
                last_dt = self._last_assigned_time.get(date_key)
                min_start = last_dt.time() if last_dt is not None else time(WORK_START_HOUR, 0)
                operation.actual_datetime = sim_helper.assign_sequential_time(
                    date, min_start=min_start, max_end_hour=WORK_END_HOUR
                )
                self._last_assigned_time[date_key] = operation.actual_datetime

                event = self._create_single_event(operation)
                events.append(event)

        return events

    def _create_event_for_day(
        self, operation: FieldOperation, op_datetime: datetime, duration_hours: float
    ) -> FieldOperationEvent:
        """Erstellt ein Event für einen Teil einer mehrtägigen Operation."""
        event = FieldOperationEvent()
        event.start_date = op_datetime.strftime("%Y-%m-%d %H:%M:%S")
        end_datetime = op_datetime + timedelta(hours=duration_hours)
        event.end_date = end_datetime.strftime("%Y-%m-%d %H:%M:%S")

        # Proportionaler Anteil an Fläche/Menge
        fraction = duration_hours / (operation.duration_per_ha * self.context.field_size)
        event.area = self.context.field_size * fraction
        event.fuel = round(self.context.field_size * operation.fuel_consumption * fraction, 2)
        event.duration = round(duration_hours * 3600, 2)
        event.durationWorked = round(event.duration * 0.95, 2)

        # Worktype-spezifische Felder
        event.worktype = operation.worktype
        event.worktype_text = operation.operation
        event.application_type = operation.application_type
        event.application_name = operation.application_name
        event.application_category = operation.application_category
        event.application_amount = round(operation.application_amount * fraction, 2)
        event.application_unit = operation.application_unit
        event.field = self.context.field_id

        return event
```

### Änderung an sim_helper.assign_sequential_time()

Erweiterung um `max_end_hour`-Parameter:

```python
# utils/sim_helper.py


def assign_sequential_time(
    date: datetime, min_start: time = time(6, 0), max_end_hour: int = 22
) -> datetime:
    """Weist eine sequenzkonforme Uhrzeit zu, berücksichtigt Arbeitszeitfenster."""
    last_time = datetime.combine(date.date(), min_start)

    # Zufällige Dauer zwischen 0.5 und 2 Stunden für den "Offset"
    offset_hours = random.uniform(0.5, 2.0)
    result_time = last_time + timedelta(hours=offset_hours)

    # Begrenzung auf Arbeitszeitfenster
    if result_time.hour >= max_end_hour:
        # Wenn über Fensterende: auf nächsten Tag zurücksetzen (nicht in dieser Funktion)
        # Für diesen Fall: clamp auf max_end_hour - 1h
        result_time = datetime.combine(date.date(), time(max_end_hour - 1, 0))

    return result_time
```

### Änderung an IrrigationSimulator

Analog für Beregnungs-Events – **mehrtägige Aufteilung** (kein MVP-Clamp):

```python
# services/irrigation_service.py


class IrrigationSimulator:
    def _create_irrigation_events(
        self, date: datetime.date, irrigation_amount: float
    ) -> list[FieldOperationEvent]:
        """Erzeugt ein oder mehrere Beregnungs-Events, aufgeteilt auf
        mehrere Tage, falls die Dauer 18 h überschreitet.
        """
        # ... bestehende Berechnung von duration ...

        MAX_DURATION_HOURS = 18
        WORK_START_HOUR = 5
        WORK_END_HOUR = 22

        if duration <= MAX_DURATION_HOURS:
            # Einzelnes Event (bestehende Logik)
            return [self._create_single_irrigation_event(date, irrigation_amount, duration)]

        # Mehrtägige Aufteilung: berechne verfügbare Stunden pro Tag
        # im Arbeitsfenster [WORK_START_HOUR, WORK_END_HOUR]
        available_hours_per_day = WORK_END_HOUR - WORK_START_HOUR  # 17 h
        if available_hours_per_day > MAX_DURATION_HOURS:
            available_hours_per_day = MAX_DURATION_HOURS

        total_hours = duration
        remaining_hours = total_hours
        remaining_amount = irrigation_amount
        events: list[FieldOperationEvent] = []
        current_date = date
        day_idx = 0

        while remaining_hours > 0:
            chunk_hours = min(remaining_hours, available_hours_per_day)
            # Proportionaler Anteil der Menge für diesen Tag
            fraction = chunk_hours / total_hours
            chunk_amount = (
                remaining_amount
                if remaining_hours <= available_hours_per_day
                else irrigation_amount * fraction
            )

            event_date = datetime.datetime.combine(current_date, datetime.time(WORK_START_HOUR, 0))
            end_datetime = event_date + timedelta(hours=chunk_hours)

            event = self._build_irrigation_event(
                event_date, end_datetime, chunk_amount, chunk_hours
            )
            events.append(event)

            remaining_hours -= chunk_hours
            current_date = current_date + timedelta(days=1)
            day_idx += 1

        return events
```

## Betroffene Dateien

- Ändern: `services/planting_plan_service.py` (get_events_for_ops, Hilfsmethoden)
- Ändern: `utils/sim_helper.py` (assign_sequential_time)
- Ändern: `services/irrigation_service.py` (_create_irrigation_event)
- Tests: `tests/test_planting_plan_service.py`, `tests/test_irrigation_candidates.py`

## Akzeptanzkriterien

1. Kein Event hat `duration` > 18 h (KAR-045)
2. Kein Event startet vor 05:00 Uhr oder endet nach 22:00 Uhr (KAR-045)
3. Lange Operationen (z. B. Separieren 34,8 h) werden auf mehrere Tage aufgeteilt
4. Aufgeteilte Operationen haben proportionale application_amount/fläche
5. Plausibilitätstest für KAR-045 wird von xfail auf aktiv umgestellt

## Testhinweise

Unit-Test: Operation mit 30 h Dauer → 2 Events (18 h + 12 h). Integrationstest mit Referenzlauf – keine Nachtarbeit mehr.

## Aufwandsschätzung

M (Logik für Aufteilung ist nicht trivial, aber klar abgegrenzt)

## Abhängigkeiten

Keine (unabhängig implementierbar)

## PO-Entscheidungen (eingearbeitet)

- **Aufteilungsstrategie:** Mehrtägige Aufteilung (kein MVP-Clamp) – lange Operationen werden auf mehrere Tage aufgeteilt, jeder Tag im Arbeitsfenster [05:00, 22:00], max. 18 h/Tag. Proportionale Aufteilung von Menge und Fläche.
