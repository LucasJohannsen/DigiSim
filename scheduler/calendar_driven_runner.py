import datetime
from collections.abc import Callable
from enum import Enum

from events.domain_event_bus import DomainEventBus
from models.domain_events import (
    create_crop_cycle_started,
    create_daily_tick_completed,
    create_daily_tick_started,
    create_harvest_completed,
    create_operation_applied,
)
from models.planting_plan import FieldOperationEvent, FieldOperationPhases, FieldOperationStatus
from models.sim_context import SimContext
from scheduler.decision_manager import CycleContext, DeadlineAwarePriorityStrategy, DecisionManager
from scheduler.guard_rule_loader import GuardRuleLoader
from services.irrigation_service import IrrigationSimulator
from services.isip_pressure_service import ISIPPressureService
from services.moisture_service import MoistureDataService
from services.planting_plan_service import PlantingPlanService
from services.protection_plan_service import ProtectionPlanService
from services.providers.dwd_weather_provider import DWDWeatherDataProvider
from services.weather_service import WeatherDataService
from utils.event_logger import EventLogger
from utils.logger import get_logger

# Type alias für die optionale Moisture-Service-Factory (P2-5 C, Issue #71).
# Erlaubt Tests, einen synthetischen Moisture-Service zu injizieren, ohne
# den Runner-Constructor von einer Service-Instanz abhängig zu machen
# (Event-Driven-Core: Factory wird erst in _initialize_services aufgerufen).
MoistureServiceFactory = Callable[[], MoistureDataService]

# Type alias für die optionale Weather-Service-Factory (P3-1, Issue #79).
# Analog zu moisture_service_factory: Factory wird erst in
# _initialize_services aufgerufen, nicht im Constructor.
WeatherServiceFactory = Callable[[], WeatherDataService]

logger = get_logger("calendar_driven_runner")


class CropCycleState(Enum):
    """Terminal states of a crop cycle within the CalendarDrivenRunner."""

    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"


class CalendarDrivenRunner:
    def __init__(
        self,
        context: SimContext,
        event_bus: DomainEventBus | None = None,
        skip_scheduling_event: bool = False,
        moisture_service_factory: MoistureServiceFactory | None = None,
        weather_service_factory: WeatherServiceFactory | None = None,
        isip_service: ISIPPressureService | None = None,
    ) -> None:
        self.context = context
        self.event_logger = EventLogger()
        self.event_bus = event_bus if event_bus is not None else DomainEventBus()
        # RuleGuard als Sicherheitsnetz (P2-4, Issue #68). Fail-open:
        # bei Konfigurationsfehlern wird ein leerer Guard geladen.
        rule_guard = GuardRuleLoader.load_default()
        # P3-4 (Issue #82): DeadlineAwarePriorityStrategy ist Standard
        # (kein optionaler Schalter, kein Fallback). Erweitert die
        # WorkTypePriority-Logik um Fälligkeitsberücksichtigung für
        # terminkritische Operationen (Fungizide).
        self.decision_manager = DecisionManager(
            strategy=DeadlineAwarePriorityStrategy(),
            event_bus=self.event_bus,
            rule_guard=rule_guard,
        )

        self.planting_plan_service = PlantingPlanService(
            context=self.context,
            start_date=self.context.start_date,
            event_bus=self.event_bus,
            skip_scheduling_event=skip_scheduling_event,
        )

        self.protection_plan_service: ProtectionPlanService = None
        self.irrigation_service: IrrigationSimulator = None
        self.weather_service: WeatherDataService | None = None
        self.isip_service = isip_service  # P4: ISIP-Druck-Gating (optional)
        self._crop_cycle_state = CropCycleState.SCHEDULED
        # P2-5 C (Issue #71): Optionale Factory für den Moisture-Service.
        # Falls gesetzt, wird sie in _initialize_services() statt der
        # Hart-Instanziierung von MoistureDataService verwendet. Ohne
        # Factory verhält sich der Runner unverändert (Abwärtskompatibilität).
        self._moisture_service_factory = moisture_service_factory
        # P3-1 (Issue #79): Optionale Factory für den Weather-Service.
        # Falls gesetzt, wird sie in _initialize_services() statt der
        # Default-Instanziierung mit DWDWeatherDataProvider verwendet.
        # Ohne Factory wird DWD-Provider verwendet (der auf Synthetic fällt,
        # falls keine DWD-Daten vorhanden). Ohne Factory und ohne
        # WeatherService bleibt weather_service=None (Abwärtskompatibilität).
        self._weather_service_factory = weather_service_factory

    def tick(self, date: datetime.date) -> list[FieldOperationEvent]:
        """
        Execute one simulation tick for the given date.

        Unified decision pipeline:
        1. Emit DailyTickStarted event
        2. Collect candidate operations from all services (planting, protection, irrigation)
        3. Pass all candidates to DecisionManager for prioritization
        4. Execute selected operations and apply side-effects
        5. Emit DailyTickCompleted event

        Args:
            date: The simulation date to process

        Returns:
            List of executed FieldOperationEvents
        """
        all_events = []

        # Emit DailyTickStarted event
        self.event_bus.publish(
            create_daily_tick_started(field_id=str(self.context.field_id), date=date)
        )
        logger.debug("Daily tick started", field_id=self.context.field_id, date=date)

        if isinstance(date, datetime.date) and not isinstance(date, datetime.datetime):
            date = datetime.datetime.combine(date, datetime.time())

        if self._should_initialize_services():
            self._initialize_services(date)

            # State transition: SCHEDULED -> RUNNING when entering crop management phase
            crop_cycle_started_event = create_crop_cycle_started(
                field_id=str(self.context.field_id), date=date, crop_type=self.context.crop_type
            )
            self.event_bus.publish(crop_cycle_started_event)
            self._crop_cycle_state = CropCycleState.RUNNING
            logger.debug(
                "Crop cycle started",
                field_id=self.context.field_id,
                crop_type=self.context.crop_type,
                date=date,
            )

        # Collect candidate operations from all services
        planting_ops = self.planting_plan_service.get_next_operations(date)
        protection_ops = (
            self.protection_plan_service.get_next_operations(date)
            if self.protection_plan_service
            else []
        )

        # Add irrigation candidates to the unified pipeline
        irrigation_candidates = []
        if self.irrigation_service:
            try:
                irrigation_candidates = self.irrigation_service.get_candidate_operations(date)
            except Exception as e:
                logger.warning("Irrigation candidate generation failed", date=date, error=str(e))

        # Unified candidate list - all operations compete equally
        all_candidate_ops = planting_ops + protection_ops + irrigation_candidates

        # DecisionManager decides which operations to execute
        cycle_context = self._build_cycle_context(date)
        selected_ops = (
            self.decision_manager.decide(
                all_candidate_ops,
                field_id=str(self.context.field_id),
                date=date,
                cycle_context=cycle_context,
            )
            or []
        )

        # Execute selected operations
        # P3-5 (Issue #83): Irrigation kann mehrere Teil-Events (Tage)
        # umfassen. Diese werden als Gruppe behandelt: apply_irrigation
        # wird einmal mit der Gesamtmenge aufgerufen, alle Teil-Events
        # werden geloggt.
        irrigation_selected = [op for op in selected_ops if op in irrigation_candidates]
        if irrigation_selected:
            total_irrigation_amount = sum(op.application_amount for op in irrigation_selected)
            try:
                self.irrigation_service.apply_irrigation(
                    date=date,
                    irrigation_amount=total_irrigation_amount,
                )
                all_events.extend(irrigation_selected)
            except Exception as e:
                logger.error("Irrigation execution failed", date=date, error=str(e))

        for op in selected_ops:
            if op in planting_ops:
                all_events.extend(self.planting_plan_service.get_events_for_ops([op], date))
            elif op in protection_ops:
                all_events.extend(self.protection_plan_service.get_events_for_ops([op], date))
            # Irrigation wurde oben als Gruppe behandelt.

        # Log integration events and emit OperationApplied domain events
        for event in all_events:
            self.event_logger.log(event)

            # Emit OperationApplied domain event
            self.event_bus.publish(
                create_operation_applied(
                    field_id=str(self.context.field_id),
                    date=date,
                    operation_type=event.worktype_text or f"Worktype {event.worktype}",
                    worktype=event.worktype,
                    integration_event_id=str(event.exa_id) if event.exa_id else None,
                )
            )

        # State transition: RUNNING -> COMPLETED after last harvest op (Issue #69).
        # Die Prüfung erfolgt NACH der Op-Ausführung, damit HarvestCompleted
        # im selben Tick emittiert wird wie die letzte Harvest-Operation
        # (date=X, nicht X+1). Vor P2-5 A stand die Prüfung am Tick-Anfang
        # und erkannte den Abschluss erst im Folgetick.
        #
        # update_phase_status() aktualisiert phase.status auf COMPLETED,
        # sobald alle Ops der aktiven Phase ein actual_date haben. Da die
        # letzte Op in diesem Tick gerade erst ausgeführt wurde, ist der
        # Status noch IN_PROGRESS – der Refresh ist zwingend erforderlich.
        if self._crop_cycle_state == CropCycleState.RUNNING:
            self.planting_plan_service.update_phase_status(date)
            if self._is_phase_completed(FieldOperationPhases.HARVESTING):
                harvest_completed_event = create_harvest_completed(
                    field_id=str(self.context.field_id), date=date, yield_estimate=None
                )
                self.event_bus.publish(harvest_completed_event)
                self._crop_cycle_state = CropCycleState.COMPLETED
                if self.irrigation_service or self.protection_plan_service:
                    self._reset_services()
                logger.debug("Harvest completed", field_id=self.context.field_id, date=date)

        # Emit DailyTickCompleted event
        self.event_bus.publish(
            create_daily_tick_completed(
                field_id=str(self.context.field_id), date=date, events_dispatched=len(all_events)
            )
        )
        logger.debug(
            "Daily tick completed",
            field_id=self.context.field_id,
            date=date,
            events_dispatched=len(all_events),
        )

        return all_events

    def _is_phase_completed(self, phase: FieldOperationPhases) -> bool:
        return self.planting_plan_service.get_phase_status(phase) == FieldOperationStatus.COMPLETED

    def _reset_services(self) -> None:
        self.irrigation_service = None
        self.protection_plan_service = None
        self.weather_service = None

    def _should_initialize_services(self) -> bool:
        return (
            self._crop_cycle_state == CropCycleState.SCHEDULED
            and not self.protection_plan_service
            and self.planting_plan_service.active_phase
            and self.planting_plan_service.active_phase.phase_name
            == FieldOperationPhases.CROP_MANAGEMENT.value
        )

    def _compute_harvest_date(self) -> datetime.datetime:
        """Erntetermin = Pflanzdatum + grow_duration (P2-3, Befund B6).

        Konsistent mit PlantingPlanService.update_phase_status() (Z. 193),
        der harvest_date = actual_planting_date + grow_duration berechnet.
        Hier wird der geplante Pflanztermin verwendet, da der
        Protection-Plan vor dem Legen geplant wird.
        """
        return self.planting_plan_service.planned_planting_date + datetime.timedelta(
            days=self.planting_plan_service.planting_plan.grow_duration
        )

    def _build_cycle_context(self, date: datetime.datetime | None = None) -> CycleContext:
        """Baut den CycleContext für die Guard-Prüfung (P2-4, Issue #68).

        Sammelt Zyklus-Daten aus den Services, ohne direkte Service-
        Abhängigkeiten in den Guard einzuführen (Event-Driven-Core).
        ``last_siccation_date``/``siccation_count`` aus bereits
        ausgeführten Protection-Operationen (``actual_date is not None``
        + ``application_category == 26``).

        P3-1 (Issue #79): Falls ``weather_service`` aktiv und ``date``
        gegeben, werden ``current_weather`` und ``weather_forecast``
        befüllt. Ohne WeatherService bleiben sie None (Abwärts-
        kompatibilität, Wetter-Guards deaktiviert).
        """
        planting_date = self.planting_plan_service.planned_planting_date
        harvest_date = None
        if planting_date is not None:
            try:
                harvest_date = self._compute_harvest_date()
            except (TypeError, AttributeError):
                harvest_date = None

        harvest_completed = self._crop_cycle_state == CropCycleState.COMPLETED

        # Sikkationsgaben (Kat. 26) aus Protection-Operationen.
        last_siccation_date: datetime.datetime | None = None
        siccation_count = 0
        if self.protection_plan_service:
            for op in self.protection_plan_service.operations:
                if op.actual_date is not None and op.application_category == 26:
                    siccation_count += 1
                    if last_siccation_date is None or op.actual_date > last_siccation_date:
                        last_siccation_date = op.actual_date

        # Letzte Ernte-Operation aus der Harvesting-Phase.
        last_harvest_op_date: datetime.datetime | None = None
        try:
            phases = self.planting_plan_service.planting_plan.phases  # type: ignore[attr-defined]
            for phase in phases:
                if phase.phase_name == FieldOperationPhases.HARVESTING.value:
                    for op in phase.operations:
                        if op.actual_date is not None:
                            if (
                                last_harvest_op_date is None
                                or op.actual_date > last_harvest_op_date
                            ):
                                last_harvest_op_date = op.actual_date
        except (AttributeError, TypeError):
            pass

        # P3-1 (Issue #79): Wetterdaten in CycleContext füllen, falls
        # WeatherService aktiv und Datum gegeben. Ohne WeatherService
        # bleiben die Felder None (Wetter-Guards deaktiviert).
        current_weather = None
        weather_forecast: list | None = None
        if self.weather_service is not None and date is not None:
            weather_date = date.date() if isinstance(date, datetime.datetime) else date
            try:
                current_weather = self.weather_service.get_weather_for_date(weather_date)
                weather_forecast = self.weather_service.get_forecast(weather_date, 7)
            except (IndexError, ValueError) as exc:
                logger.warning(
                    "Weather data lookup failed",
                    date=weather_date,
                    error=str(exc),
                )

        return CycleContext(
            planting_date=planting_date,
            harvest_date=harvest_date,
            harvest_completed=harvest_completed,
            last_siccation_date=last_siccation_date,
            siccation_count_this_cycle=siccation_count,
            last_harvest_op_date=last_harvest_op_date,
            current_weather=current_weather,
            weather_forecast=weather_forecast,
        )

    def _initialize_services(self, current_date: datetime.date) -> None:
        # P2-3 (Befund B6): Protection-Termine am Pflanzdatum verankern
        # (nicht am Crop-Management-Start) und am Erntetermin beschneiden.
        # P4: ISIP-Druck-Gating – isip_service wird injiziert (optional).
        self.protection_plan_service = ProtectionPlanService(
            context=self.context,
            start_date=self.planting_plan_service.planned_planting_date,
            planting_plan=self.planting_plan_service.planting_plan,
            harvest_date=self._compute_harvest_date(),
            event_bus=self.event_bus,
            isip_service=self.isip_service,
        )

        # Extract year from current simulation date
        simulation_year = (
            current_date.year if isinstance(current_date, datetime.datetime) else current_date.year
        )

        # P2-5 C (Issue #71): Nutze die injizierte Factory, falls gesetzt
        # (z. B. DryMoistureDataService-Stub in der Plausibilitätssuite);
        # sonst Hart-Instanziierung wie bisher (Abwärtskompatibilität).
        if self._moisture_service_factory is not None:
            ms = self._moisture_service_factory()
        else:
            # P3-6 (Issue #84): min_moisture_level=200 entfernt – toter
            # Parameter. MoistureDataService speichert ihn, nutzt ihn aber
            # nicht. IrrigationSimulator nutzt 50 % nFK (Fallback), da
            # SimContext kein min_moisture_level-Feld hat.
            ms = MoistureDataService(context=self.context)
        self.irrigation_service = IrrigationSimulator(
            context=self.context,
            moisture_data=ms.get_moisture_data(year=simulation_year, depth_range="0-10"),
        )

        # P3-1 (Issue #79): Weather-Service initialisieren.
        # Falls Factory gesetzt: verwende sie. Sonst: Default mit
        # DWDWeatherDataProvider (fällt auf Synthetic zurück, falls keine
        # DWD-Daten vorhanden).
        if self._weather_service_factory is not None:
            self.weather_service = self._weather_service_factory()
        else:
            provider = DWDWeatherDataProvider(cache_folder="dwd_data")
            self.weather_service = WeatherDataService(
                context=self.context, provider=provider, event_bus=self.event_bus
            )

    def get_state_snapshot(self, last_tick_date: datetime.date | None = None):
        from utils.state_manager import FieldStateSnapshot

        planting_ops = []
        for phase in self.planting_plan_service.planting_plan.phases:
            for op in phase.operations:
                planting_ops.append(
                    {
                        "phase": phase.phase_name,
                        "sequence": op.sequence,
                        "actual_date": op.actual_date.isoformat() if op.actual_date else None,
                    }
                )

        protection_ops = []
        if self.protection_plan_service:
            for op in self.protection_plan_service.operations:
                protection_ops.append(
                    {"actual_date": op.actual_date.isoformat() if op.actual_date else None}
                )

        irrigation_state = None
        if self.irrigation_service:
            irrigation_state = self.irrigation_service.get_state()

        return FieldStateSnapshot(
            field_id=self.context.field_id,
            last_tick_date=last_tick_date,
            context=self.context,
            planting_ops=planting_ops,
            protection_ops=protection_ops,
            irrigation_state=irrigation_state,
            crop_cycle_state=self._crop_cycle_state.value,
            planned_planting_date=self.planting_plan_service.planned_planting_date,
        )

    def apply_state_snapshot(self, snapshot) -> None:
        # P2-5 B (Issue #70): planned_planting_date restaurieren, bevor Ops
        # wiederhergestellt werden. Bei skip_scheduling_event=True wurde der
        # Termin beim Constructor nicht gewürfelt. Ist das Feld im Snapshot
        # nicht vorhanden (alter Snapshot), würfelt set_planned_planting_date
        # neu + emittiert CropCycleScheduled (Bestandsschutz).
        self.planting_plan_service.set_planned_planting_date(snapshot.planned_planting_date)

        for op_data in snapshot.planting_ops:
            phase_name = op_data["phase"]
            sequence = op_data["sequence"]
            actual_date_str = op_data.get("actual_date")

            for phase in self.planting_plan_service.planting_plan.phases:
                if phase.phase_name == phase_name:
                    for op in phase.operations:
                        if op.sequence == sequence:
                            if actual_date_str:
                                op.actual_date = datetime.datetime.fromisoformat(actual_date_str)
                            break

        if snapshot.protection_ops:
            if not self.protection_plan_service:
                self._initialize_services(self.context.start_date)
            if self.protection_plan_service:
                for idx, op_data in enumerate(snapshot.protection_ops):
                    actual_date_str = op_data.get("actual_date")

                    if idx < len(self.protection_plan_service.operations):
                        op = self.protection_plan_service.operations[idx]
                        if actual_date_str:
                            op.actual_date = datetime.datetime.fromisoformat(actual_date_str)

        if snapshot.irrigation_state:
            if not self.irrigation_service:
                self._initialize_services(self.context.start_date)
            if self.irrigation_service:
                self.irrigation_service.apply_state(snapshot.irrigation_state)

        # Restore or derive crop cycle state for backward compatibility
        if snapshot.crop_cycle_state is not None:
            self._crop_cycle_state = CropCycleState(snapshot.crop_cycle_state)
        else:
            if self._is_phase_completed(FieldOperationPhases.HARVESTING):
                self._crop_cycle_state = CropCycleState.COMPLETED
                self._reset_services()
            elif (
                self.planting_plan_service.active_phase
                and self.planting_plan_service.active_phase.phase_name
                == FieldOperationPhases.CROP_MANAGEMENT.value
            ):
                self._crop_cycle_state = CropCycleState.RUNNING
                if not self.protection_plan_service:
                    self._initialize_services(self.context.start_date)
            else:
                self._crop_cycle_state = CropCycleState.SCHEDULED
