import datetime
from typing import List

from models.sim_context import SimContext
from models.planting_plan import FieldOperationEvent, FieldOperationPhases, FieldOperationStatus
from services.planting_plan_service import PlantingPlanService
from services.protection_plan_service import ProtectionPlanService
from services.irrigation_service import IrrigationSimulator
from services.moisture_service import MoistureDataService
from scheduler.decision_manager import DecisionManager, WorkTypePriorityStrategy
from utils.event_logger import EventLogger
from utils.logger import get_logger

logger = get_logger("calendar_driven_runner")


class CalendarDrivenRunner:
    def __init__(self, context: SimContext) -> None:
        self.context = context
        self.event_logger = EventLogger()
        self.decision_manager = DecisionManager(WorkTypePriorityStrategy())
        
        self.planting_plan_service = PlantingPlanService(
            context=self.context,
            start_date=self.context.start_date
        )
        
        self.protection_plan_service: ProtectionPlanService = None
        self.irrigation_service: IrrigationSimulator = None

    def tick(self, date: datetime.date) -> List[FieldOperationEvent]:
        """
        Execute one simulation tick for the given date.
        
        Unified decision pipeline:
        1. Collect candidate operations from all services (planting, protection, irrigation)
        2. Pass all candidates to DecisionManager for prioritization
        3. Execute selected operations and apply side-effects
        
        Args:
            date: The simulation date to process
            
        Returns:
            List of executed FieldOperationEvents
        """
        all_events = []
        
        if isinstance(date, datetime.date) and not isinstance(date, datetime.datetime):
            date = datetime.datetime.combine(date, datetime.time())
        
        if self._is_phase_completed(FieldOperationPhases.HARVESTING):
            if self.irrigation_service or self.protection_plan_service:
                self._reset_services()
        
        if self._should_initialize_services():
            self._initialize_services(date)
        
        # Collect candidate operations from all services
        planting_ops = self.planting_plan_service.get_next_operations(date)
        protection_ops = (
            self.protection_plan_service.get_next_operations(date)
            if self.protection_plan_service else []
        )
        
        # Add irrigation candidates to the unified pipeline
        irrigation_candidates = []
        if self.irrigation_service:
            day_of_year = date.timetuple().tm_yday
            try:
                irrigation_candidates = self.irrigation_service.get_candidate_operations(day_of_year)
            except Exception as e:
                logger.warning("Irrigation candidate generation failed", day=day_of_year, error=str(e))
        
        # Unified candidate list - all operations compete equally
        all_candidate_ops = planting_ops + protection_ops + irrigation_candidates
        
        # DecisionManager decides which operations to execute
        selected_ops = self.decision_manager.decide(all_candidate_ops) or []
        
        # Execute selected operations
        for op in selected_ops:
            if op in planting_ops:
                all_events.extend(
                    self.planting_plan_service.get_events_for_ops([op], date)
                )
            elif op in protection_ops:
                all_events.extend(
                    self.protection_plan_service.get_events_for_ops([op], date)
                )
            elif op in irrigation_candidates:
                # Irrigation candidate confirmed - apply side-effects
                day_of_year = date.timetuple().tm_yday
                try:
                    self.irrigation_service.apply_irrigation(
                        day=day_of_year,
                        irrigation_amount=op.application_amount
                    )
                    all_events.append(op)
                except Exception as e:
                    logger.error("Irrigation execution failed", day=day_of_year, error=str(e))
        
        for event in all_events:
            self.event_logger.log(event)
        
        return all_events

    def _is_phase_completed(self, phase: FieldOperationPhases) -> bool:
        return self.planting_plan_service.get_phase_status(phase) == FieldOperationStatus.COMPLETED

    def _reset_services(self) -> None:
        self.irrigation_service = None
        self.protection_plan_service = None

    def _should_initialize_services(self) -> bool:
        return (
            not self.protection_plan_service and
            self.planting_plan_service.active_phase and
            self.planting_plan_service.active_phase.phase_name == FieldOperationPhases.CROP_MANAGEMENT.value
        )

    def _initialize_services(self, current_date: datetime.date) -> None:
        self.protection_plan_service = ProtectionPlanService(
            context=self.context,
            start_date=current_date,
            planting_plan=self.planting_plan_service.planting_plan
        )
        
        # Extract year from current simulation date
        simulation_year = current_date.year if isinstance(current_date, datetime.datetime) else current_date.year
        
        ms = MoistureDataService(context=self.context, min_moisture_level=200)
        self.irrigation_service = IrrigationSimulator(
            context=self.context,
            moisture_data=ms.get_moisture_data(year=simulation_year, depth_range='0-10')
        )


    def get_state_snapshot(self, last_tick_date: datetime.date | None = None):
        from utils.state_manager import FieldStateSnapshot
        
        planting_ops = []
        for phase in self.planting_plan_service.planting_plan.phases:
            for op in phase.operations:
                planting_ops.append({
                    "phase": phase.phase_name,
                    "sequence": op.sequence,
                    "actual_date": op.actual_date.isoformat() if op.actual_date else None
                })
        
        protection_ops = []
        if self.protection_plan_service:
            for op in self.protection_plan_service.operations:
                protection_ops.append({
                    "actual_date": op.actual_date.isoformat() if op.actual_date else None
                })
        
        irrigation_state = None
        if self.irrigation_service:
            irrigation_state = self.irrigation_service.get_state()
        
        return FieldStateSnapshot(
            field_id=self.context.field_id,
            last_tick_date=last_tick_date,
            context=self.context,
            planting_ops=planting_ops,
            protection_ops=protection_ops,
            irrigation_state=irrigation_state
        )

    def apply_state_snapshot(self, snapshot) -> None:
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
