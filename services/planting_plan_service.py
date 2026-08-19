import random
from datetime import datetime, time, timedelta
from math import ceil

import models.sim_context as sim_context
from models.domain_events import create_crop_cycle_scheduled
from models.planting_plan import (
    FieldOperation,
    FieldOperationEvent,
    FieldOperationPhases,
    FieldOperationStatus,
)
from services.planting_plan_loader import PlantingPlanLoader
from utils import sim_helper
from utils.logger import get_logger

_DEFAULT_LEAD_TIME_DAYS = 30

logger = get_logger("planting_plan_service")


class PlantingPlanService:
    def __init__(
        self,
        context: sim_context.SimContext,
        start_date: datetime,
        event_bus: object | None = None,
        skip_scheduling_event: bool = False,
    ):
        self.context = context
        self.start_date = start_date
        self.event_bus = event_bus

        self.active_phase = None
        self.planting_plan = None
        self.planned_planting_date: datetime = None  # Planned date for planting operations

        # Intra-Tages-Sequenz-Cursor (Befund B7, Issue #66 / P2-2):
        # Pro Kalendertag wird der zuletzt vergebene Event-Zeitpunkt
        # gespeichert, damit aufeinanderfolgende Einzel-Calls von
        # get_events_for_ops() für dasselbe Datum strikt monoton steigende
        # Zeitstempel erhalten. Der Cursor wirkt NICHT über Tagesgrenzen.
        self._last_assigned_time: dict[datetime.date, datetime] = {}

        self.initialize_planting_plan(skip_scheduling_event=skip_scheduling_event)

    def initialize_planting_plan(self, skip_scheduling_event=False):
        """
        Initialize the planting plan by loading it from the PlantingPlanLoader.

        When *skip_scheduling_event* is ``True`` (Restore-Pfad, P2-5 B /
        Issue #70), wird der Legetermin **nicht** neu gewürfelt und kein
        ``CropCycleScheduled`` emittiert. Der restaurierte Termin wird
        nachträglich via :meth:`set_planned_planting_date` gesetzt.
        """
        self.planting_plan = PlantingPlanLoader(
            crop_type=self.context.crop_type, variety=self.context.variety
        ).get_planting_plan()

        if not self.planting_plan:
            print("No planting plan found. Exiting simulation.")
            return
        print(
            f"Loaded planting plan for crop type: {self.planting_plan.crop_type}, variety: {self.planting_plan.variety}"
        )

        if skip_scheduling_event:
            # Restore-Pfad: Termin + Timeline werden via
            # set_planned_planting_date() durch apply_state_snapshot gesetzt.
            return

        self._schedule_planting_date()

    def _schedule_planting_date(self):
        """Würfelt den Legetermin, emittiert ``CropCycleScheduled`` und
        konfiguriert die ``SOIL_PREPARATION``-Timeline.

        Wird beim Fresh-Start aus :meth:`initialize_planting_plan` und beim
        Bestandsschutz-Restore (alter Snapshot ohne ``planned_planting_date``)
        aus :meth:`set_planned_planting_date` aufgerufen.
        """
        if not self.planting_plan:
            return

        lead_time_days = self._compute_lead_time_days()

        self.planned_planting_date = sim_helper.get_random_planting_date(
            self.start_date,
            self.planting_plan.planting_period_months,
            lead_time_days,
        )

        print(f"Planned planting date: {self.planned_planting_date.strftime('%Y-%m-%d')}")

        # Publish CropCycleScheduled so the scheduling decision is traceable
        # (Styleguide: fachliches Ereignis zuerst benennen).
        if self.event_bus is not None:
            self.event_bus.publish(
                create_crop_cycle_scheduled(
                    field_id=str(self.context.field_id),
                    date=self.start_date,
                    planned_planting_date=self.planned_planting_date,
                    crop_type=self.context.crop_type,
                )
            )

        # Set the planting date for the first phase
        self.configure_planting_timeline(
            FieldOperationPhases.SOIL_PREPARATION, target_date=self.planned_planting_date
        )

    def set_planned_planting_date(self, planned_planting_date: datetime | None) -> None:
        """Setzt den restaurierten Legetermin und re-konfiguriert die
        ``SOIL_PREPARATION``-Phase (P2-5 B, Issue #70).

        Ist *planned_planting_date* ``None`` (Bestandsschutz: alter Snapshot
        ohne das Feld), wird der Termin neu gewürfelt und
        ``CropCycleScheduled`` emittiert.
        """
        if planned_planting_date is None:
            # Abwärtskompatibilität: altes Snapshot ohne planned_planting_date
            self._schedule_planting_date()
            return

        self.planned_planting_date = planned_planting_date
        self.configure_planting_timeline(
            FieldOperationPhases.SOIL_PREPARATION,
            target_date=planned_planting_date,
        )

    def _compute_lead_time_days(self) -> int:
        """Maximum lead time of the soil-preparation operations.

        ``lead_time_days`` is the absolute value of the largest
        ``min_days_to_target`` in the ``soil_preparation`` phase (i.e. the
        furthest an operation is scheduled before the planting target date).
        Fallback: :data:`_DEFAULT_LEAD_TIME_DAYS` if the phase or its
        operations cannot be determined.

        Returns:
            Lead time in days (always non-negative).
        """
        phase = next(
            (
                p
                for p in self.planting_plan.phases
                if p.phase_name == FieldOperationPhases.SOIL_PREPARATION.value
            ),
            None,
        )
        if not phase or not phase.operations:
            return _DEFAULT_LEAD_TIME_DAYS
        offsets = [
            abs(op.min_days_to_target)
            for op in phase.operations
            if op.min_days_to_target is not None
        ]
        if not offsets:
            return _DEFAULT_LEAD_TIME_DAYS
        return max(offsets)

    def update_planned_operations_startdates(self, phase_name: str, target_date: datetime):
        """
        Update the planned dates for a specific operation in the planting plan.
        """

        # get the list of operations for the specified phase
        operations = sim_helper.get_operations_by_phase(self.planting_plan, phase_name)
        # Sort operations by their sequence property
        operations = sorted(operations, key=lambda op: op.sequence)

        operation_date = target_date

        for operation in operations:
            min_offset = operation.min_days_to_target
            max_offset = operation.max_days_to_target

            # calculate the planned date for the operation
            operation.planned_date = sim_helper.get_random_date_in_range(
                min_offset, max_offset, operation_date
            )
            # print(f"Operation '{operation.operation}' planned for date: {operation.planned_date}")

    def configure_planting_timeline(
        self, target_phase: FieldOperationPhases, target_date: datetime = None
    ):
        """
        Defines the start date for the given target phase in the planting plan.
        """

        if not self.planting_plan:
            print("No planting plan loaded. Exiting.")
            return

        phase = next(
            (p for p in self.planting_plan.phases if p.phase_name == target_phase.value), None
        )

        if target_phase == FieldOperationPhases.SOIL_PREPARATION:
            min(op.min_days_to_target for op in phase.operations)

            # update dates for all operations in the phase
            self.update_planned_operations_startdates(phase.phase_name, target_date)

            # phase.start_date = min(op.planned_date for op in phase.operations if op.planned_date)

            # print(f"Phase '{phase.phase_name}' start date: {phase.start_date}")

    def update_phase_status(self, date: datetime):
        """
        Update the status of the active phase based on the completed operations.
        """

        if not self.active_phase:
            # check if another phase can be set to active
            for phase in self.planting_plan.phases:
                if (
                    phase.start_date
                    and phase.start_date <= date
                    and phase.status == FieldOperationStatus.NOT_STARTED
                ):
                    self.active_phase = phase
                    phase.status = FieldOperationStatus.IN_PROGRESS
                    print(f"Active phase set to: {phase.phase_name}")
                    break

        # if all operations in the active phase are completed, set the phase status to COMPLETED
        if self.active_phase:
            all_completed = all(op.actual_date is not None for op in self.active_phase.operations)
            if all_completed:
                self.active_phase.status = FieldOperationStatus.COMPLETED
                # print(f"Phase '{self.active_phase.phase_name}' completed on {date.strftime('%Y-%m-%d')}")
                self.active_phase = None

                # plan the next phase if available
                next_phase = next(
                    (
                        p
                        for p in self.planting_plan.phases
                        if p.status == FieldOperationStatus.NOT_STARTED
                    ),
                    None,
                )
                if next_phase:
                    if next_phase.phase_name == FieldOperationPhases.PLANTING.value:
                        self.update_planned_operations_startdates(next_phase.phase_name, date)

                    elif next_phase.phase_name == FieldOperationPhases.CROP_MANAGEMENT.value:
                        # get the last operation in the planting phase
                        last_planting_op_date = max(
                            op.actual_date
                            for op in sim_helper.get_operations_by_phase(
                                self.planting_plan, "sowing_planting"
                            )
                            if op.actual_date
                        )

                        self.update_planned_operations_startdates(
                            next_phase.phase_name, last_planting_op_date
                        )

                        # print(f"Next phase '{next_phase.phase_name}' will start on {next_phase.start_date.strftime('%Y-%m-%d')}")

                    elif next_phase.phase_name == FieldOperationPhases.HARVESTING.value:
                        # get actual planting date of last op in the planting phase
                        # (P3-7, Issue #85): Filter gegen None actual_date, damit
                        # max() nicht bei fehlenden Actuals abstürzt.
                        actual_planting_date = max(
                            (
                                op.actual_date
                                for op in sim_helper.get_operations_by_phase(
                                    self.planting_plan, "sowing_planting"
                                )
                                if op.actual_date
                            ),
                            default=None,
                        )

                        if actual_planting_date is None:
                            # Ohne actual_planting_date kann kein Erntetermin
                            # berechnet werden – Harvest-Phase bleibt ungeplant.
                            pass
                        else:
                            # P3-7 (Issue #85): growth_duration primär,
                            # harvest_period_months als Validierung (Korrektur
                            # nur nach hinten, nicht unter biologische Reife).
                            harvest_date = self._compute_harvest_date(actual_planting_date)
                            self.update_planned_operations_startdates(
                                next_phase.phase_name, harvest_date
                            )

    def _compute_harvest_date(self, actual_planting_date: datetime) -> datetime:
        """Berechnet den Erntetermin (P3-7, Issue #85, Befund B12).

        ``growth_duration`` ist die **primäre Quelle**:
        ``harvest_date = actual_planting_date + grow_duration``.

        ``harvest_period_months`` dient als **Validierung**: fällt der
        berechnete Erntetermin außerhalb des konfigurierten Erntefensters,
        wird er auf das früheste zulässige Datum im ersten Fenstermonat
        verschoben. Die Korrektur erfolgt **ausschließlich nach hinten** –
        ein Termin wird nie vor die biologische Reife (growth_duration-
        Mindesttermin) verlegt. Liegt der berechnete Termin nach dem Fenster
        (z. B. November bei Fenster [9,10]), bleibt er unverändert.

        Args:
            actual_planting_date: Tatsächliches Legedatum (datetime).

        Returns:
            Geplanter Erntetermin (datetime), ggf. korrigiert.
        """
        assert self.planting_plan is not None  # type narrowing (s. update_phase_status)
        # PRIMÄR: harvest_date aus growth_duration
        harvest_date = actual_planting_date + timedelta(days=self.planting_plan.grow_duration)

        # VALIDIERUNG: harvest_period_months als Korrektur-Fenster
        harvest_period_months = self.planting_plan.harvest_period_months
        if not harvest_period_months:
            return harvest_date

        harvest_months_list = list(harvest_period_months)  # Tuple → List
        if harvest_date.month in harvest_months_list:
            return harvest_date

        # Erntetermin liegt außerhalb des Fensters → verschieben
        target_month = harvest_months_list[0]
        harvest_year = actual_planting_date.year
        if target_month < actual_planting_date.month:
            harvest_year += 1
        # Frühestes zulässiges Datum im Zielmonat
        corrected = datetime(harvest_year, target_month, 1)
        # Nur verschieben, wenn es NACH dem growth_duration-Mindest-
        # termin liegt (nicht vorverlegen unter biologische Reife).
        if corrected > harvest_date:
            logger.info(
                "Erntetermin aus growth_duration (%s) außerhalb "
                "harvest_period_months %s -> korrigiert auf %s",
                harvest_date,
                harvest_months_list,
                corrected,
            )
            return corrected
        # Termin liegt nach dem Fenster → keine Rück-Korrektur (nur nach
        # hinten), biologische Reife bleibt gewahrt.
        return harvest_date

    def get_phase_status(self, phase_name: FieldOperationPhases) -> FieldOperationStatus:
        """
        Get the status of a specific phase in the planting plan.
        """
        phase = next(
            (p for p in self.planting_plan.phases if p.phase_name == phase_name.value), None
        )
        if not phase:
            print(f"Phase '{phase_name.value}' not found in the planting plan.")
            return FieldOperationStatus.NOT_STARTED

        return phase.status

    def get_next_operations(self, date: datetime) -> FieldOperation:
        """
        Get the next operation to be performed based on the current date.
        """

        self.update_phase_status(date)

        # get next operation in the active phase
        if not self.active_phase:
            # print("No active phase found. Exiting.")
            return []

        next_operations = []
        for operation in self.active_phase.operations:
            if (
                operation.planned_date
                and operation.planned_date <= date
                and operation.actual_date is None
            ):
                # add the operation to the next operations
                next_operations.append(operation)

        if not next_operations:
            # print("No next operations found for the active phase.")
            return []

        # Sort by sequence to ensure correct execution order
        next_operations.sort(key=lambda op: op.sequence)
        # print(f"Next operations for phase '{self.active_phase.phase_name}':")

        return next_operations

    # P3-5 (Issue #83): Arbeitszeiten begrenzen – mehrtägige Aufteilung.
    # Arbeitsfenster [05:00, 22:00], max. 18 h/Tag. Lange Operationen
    # werden auf mehrere Tage aufgeteilt (Befund B10, KAR-045).
    WORK_START_HOUR = 5
    WORK_END_HOUR = 22
    MAX_DURATION_HOURS = 18
    # KAR-046 (hard): Genau 1 Event mit wt=26 (Legen) und wt=27 (Roden)
    # pro Zyklus. Diese Operationen dürfen nicht aufgeteilt werden, da
    # sonst die Event-Anzahl steigt. Die Dauer bleibt > 18 h (KAR-045
    # soft), aber ein hard-Regelverstoß wird vermieden.
    _SINGLE_EVENT_WORKTYPES: set[int] = {26, 27}

    def get_events_for_ops(
        self, operations: list[FieldOperation], date: datetime
    ) -> list[FieldOperationEvent]:

        # get active phase
        events = []

        # Intra-Tags-Sequenz-Cursor (Befund B7, Issue #66 / P2-2):
        # date wird vom CalendarDrivenRunner als datetime übergeben; der
        # Cursor-Key ist das Kalenderdatum, damit der Zustand nicht über
        # Tagesgrenzen wirkt.
        date_key = date.date() if isinstance(date, datetime) else date

        for operation in operations:
            # get the variation factor for fuel consumption (individual per operation)
            fuel_variation_factor = random.uniform(
                1 - self.context.fuel_variation, 1 + self.context.fuel_variation
            )
            # Process the operation

            # Update the actual date of the operation
            operation.actual_date = date
            print(
                f"    {operation.operation}: {operation.actual_date.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            # P3-5 (Issue #83): Gesamtdauer berechnen und ggf. aufteilen
            total_duration_hours = operation.duration_per_ha * self.context.field_size

            if (
                total_duration_hours > self.MAX_DURATION_HOURS
                and operation.worktype not in self._SINGLE_EVENT_WORKTYPES
            ):
                # Mehrtägige Aufteilung (Befund B10, KAR-045)
                num_days = ceil(total_duration_hours / self.MAX_DURATION_HOURS)
                duration_per_day = total_duration_hours / num_days

                for day_idx in range(num_days):
                    op_date = date + timedelta(days=day_idx)
                    op_date_key = op_date.date() if isinstance(op_date, datetime) else op_date

                    # Sequenzkonforme Uhrzeit pro Tag via Cursor.
                    # P3-5: Nur der erste Aufteilungs-Tag verbraucht Zufalls-
                    # Zahlen (wie die ursprüngliche Einzel-Op). Folgende Tage
                    # erhalten einen deterministischen Start (06:00), um den
                    # Zufallszustand für ProtectionPlanService nicht zu
                    # verschieben (KAR-021).
                    last_dt = self._last_assigned_time.get(op_date_key)
                    if day_idx == 0:
                        min_start = last_dt.time() if last_dt is not None else time(6, 0)
                        op_datetime = sim_helper.assign_sequential_time(
                            op_date, min_start=min_start
                        )
                    else:
                        # Deterministisch: 06:00 (kein Zufallsverbrauch)
                        base = last_dt.time() if last_dt is not None else time(6, 0)
                        op_datetime = datetime.combine(
                            op_date.date() if isinstance(op_date, datetime) else op_date,
                            base,
                        )
                    self._last_assigned_time[op_date_key] = op_datetime

                    # Proportionaler Anteil für diesen Tag
                    fraction = duration_per_day / total_duration_hours
                    event = self._create_event_for_day(
                        operation, op_datetime, duration_per_day, fraction, fuel_variation_factor
                    )
                    events.append(event)
            else:
                # Einzelne Operation (bestehende Logik)
                last_dt = self._last_assigned_time.get(date_key)
                min_start = last_dt.time() if last_dt is not None else time(6, 0)
                operation.actual_datetime = sim_helper.assign_sequential_time(
                    date, min_start=min_start
                )
                self._last_assigned_time[date_key] = operation.actual_datetime

                event = self._create_single_event(operation, fuel_variation_factor)
                events.append(event)

        return events

    def _create_single_event(
        self,
        operation: FieldOperation,
        fuel_variation_factor: float,
    ) -> FieldOperationEvent:
        """Erstellt ein einzelnes Event für eine Operation ≤ 18 h (bestehende Logik)."""
        event = FieldOperationEvent()
        event.start_date = operation.actual_datetime.strftime("%Y-%m-%d %H:%M:%S")
        event.end_date = (
            operation.actual_datetime
            + timedelta(hours=operation.duration_per_ha * self.context.field_size)
        ).strftime("%Y-%m-%d %H:%M:%S")
        event.area = self.context.field_size
        event.fuel = round(self.context.field_size * operation.fuel_consumption, 2)
        event.worktype = operation.worktype
        event.worktype_text = operation.operation
        event.duration = round(
            operation.duration_per_ha * self.context.field_size * 60 * 60, 2
        )  # Sekunden
        event.durationWorked = round(event.duration * 0.95, 2)
        event.distance = (
            round(self.context.field_size * 10 / operation.working_width, 2)
            if operation.working_width > 0
            else 0
        )
        event.distanceWorked = round(event.distance * 0.95, 2)
        event.application_type = operation.application_type
        event.application_name = operation.application_name
        event.application_category = operation.application_category
        event.application_amount = round(operation.application_amount * self.context.field_size, 2)
        event.application_unit = operation.application_unit
        event.field = self.context.field_id
        event.fuel = round(event.fuel * fuel_variation_factor, 2)
        return event

    def _create_event_for_day(
        self,
        operation: FieldOperation,
        op_datetime: datetime,
        duration_hours: float,
        fraction: float,
        fuel_variation_factor: float,
    ) -> FieldOperationEvent:
        """Erstellt ein Event für einen Teil einer mehrtägigen Operation.

        P3-5 (Issue #83): Proportionale Aufteilung von Fläche, Menge und
        Kraftstoff auf die einzelnen Tage.

        Args:
            operation: Die ursprüngliche FieldOperation.
            op_datetime: Start-Zeitpunkt für diesen Tag.
            duration_hours: Dauer dieses Teil-Events in Stunden.
            fraction: Anteil an der Gesamtdauer (0 < fraction ≤ 1).
            fuel_variation_factor: Zufallsvariation für Kraftstoffverbrauch.

        Returns:
            FieldOperationEvent mit proportionalen Werten.
        """
        event = FieldOperationEvent()
        event.start_date = op_datetime.strftime("%Y-%m-%d %H:%M:%S")
        end_datetime = op_datetime + timedelta(hours=duration_hours)
        event.end_date = end_datetime.strftime("%Y-%m-%d %H:%M:%S")
        event.area = round(self.context.field_size * fraction, 2)
        event.fuel = round(self.context.field_size * operation.fuel_consumption * fraction, 2)
        event.worktype = operation.worktype
        event.worktype_text = operation.operation
        event.duration = round(duration_hours * 60 * 60, 2)  # Sekunden
        event.durationWorked = round(event.duration * 0.95, 2)
        event.distance = (
            round(self.context.field_size * 10 / operation.working_width * fraction, 2)
            if operation.working_width > 0
            else 0
        )
        event.distanceWorked = round(event.distance * 0.95, 2)
        event.application_type = operation.application_type
        event.application_name = operation.application_name
        event.application_category = operation.application_category
        event.application_amount = round(
            operation.application_amount * self.context.field_size * fraction, 2
        )
        event.application_unit = operation.application_unit
        event.field = self.context.field_id
        event.fuel = round(event.fuel * fuel_variation_factor, 2)
        return event
