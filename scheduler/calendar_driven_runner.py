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
        all_events = []
        
        if isinstance(date, datetime.date) and not isinstance(date, datetime.datetime):
            date = datetime.datetime.combine(date, datetime.time())
        
        if self._is_phase_completed(FieldOperationPhases.HARVESTING):
            if self.irrigation_service or self.protection_plan_service:
                self._reset_services()
        
        if self._should_initialize_services():
            self._initialize_services(date)
        
        planting_ops = self.planting_plan_service.get_next_operations(date)
        protection_ops = (
            self.protection_plan_service.get_next_operations(date)
            if self.protection_plan_service else []
        )
        all_candidate_ops = planting_ops + protection_ops
        
        selected_ops = self.decision_manager.decide(all_candidate_ops) or []
        
        for op in selected_ops:
            if op in planting_ops:
                all_events.extend(
                    self.planting_plan_service.get_events_for_ops([op], date)
                )
            elif op in protection_ops:
                all_events.extend(
                    self.protection_plan_service.get_events_for_ops([op], date)
                )
        
        if self.irrigation_service:
            has_high_prio = any(
                getattr(op, 'worktype', None) not in [14, 15]
                for op in selected_ops
            )
            if not has_high_prio:
                all_events.extend(self._handle_irrigation(date))
        
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
        
        ms = MoistureDataService(context=self.context, min_moisture_level=200)
        self.irrigation_service = IrrigationSimulator(
            context=self.context,
            moisture_data=ms.get_moisture_data(year=2022, depth_range='0-10')
        )

    def _handle_irrigation(self, date: datetime.date) -> List[FieldOperationEvent]:
        irrigation_events = []
        
        day_of_year = date.timetuple().tm_yday
        
        try:
            irrigation_status = self.irrigation_service.get_status_for_day(day_of_year)
            if irrigation_status["irrigation_needed"] >= 5:
                event = self.irrigation_service.trigger_irrigation(
                    day_of_year, 
                    irrigation_amount=irrigation_status["irrigation_needed"]
                )
                if event:
                    irrigation_events.append(event)
        except Exception:
            pass
        
        return irrigation_events
