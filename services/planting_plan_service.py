import random
from datetime import datetime, timedelta

from services.planting_plan_loader import PlantingPlanLoader
from models.planting_plan import (
    FieldOperationStatus,
    FieldOperation,
    FieldOperationEvent,
    FieldOperationPhases
)
import models.sim_context as sim_context
from utils import sim_helper


class PlantingPlanService:

    def __init__(self, context: sim_context.SimContext, start_date:datetime):
        self.context = context
        
        self.start_date = start_date
        self.planting_plan = None

        self.active_phase = None
        self.planned_planting_date: datetime = None  # Planned date for planting operations

        self.initialize_planting_plan()

    def initialize_planting_plan(self):
        """
        Initialize the planting plan by loading it from the PlantingPlanLoader.
        """
        self.planting_plan = PlantingPlanLoader(
            crop_type=self.context.crop_type,
            variety=self.context.variety
        ).get_planting_plan()

        if not self.planting_plan:
            print("No planting plan found. Exiting simulation.")
            return
        print(f"Loaded planting plan for crop type: {self.planting_plan.crop_type}, variety: {self.planting_plan.variety}")

        self.planned_planting_date = sim_helper.get_random_date(
            self.planting_plan.planting_period_months[0],
            self.planting_plan.planting_period_months[1],
            self.start_date.year+1
        )

        print(f"Planned planting date: {self.planned_planting_date.strftime('%Y-%m-%d')}")

        # Set the planting date for the first phase
        self.configure_planting_timeline(FieldOperationPhases.SOIL_PREPARATION, target_date=self.planned_planting_date)

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
            operation.planned_date = sim_helper.get_random_date_in_range(min_offset, max_offset, operation_date)
            #print(f"Operation '{operation.operation}' planned for date: {operation.planned_date}")



    def configure_planting_timeline(self, target_phase: FieldOperationPhases, target_date: datetime = None):
        """
        Defines the start date for the given target phase in the planting plan.
        """

        if not self.planting_plan:
            print("No planting plan loaded. Exiting.")
            return

        phase = next((p for p in self.planting_plan.phases if p.phase_name == target_phase.value), None)

        if target_phase == FieldOperationPhases.SOIL_PREPARATION:
            min_target_interval = min(op.min_days_to_target for op in phase.operations)
            
            # update dates for all operations in the phase
            self.update_planned_operations_startdates(phase.phase_name, target_date)

            #phase.start_date = min(op.planned_date for op in phase.operations if op.planned_date)
            
            #print(f"Phase '{phase.phase_name}' start date: {phase.start_date}")
        
       


    def update_phase_status(self, date: datetime):
        """
        Update the status of the active phase based on the completed operations.
        """

        if not self.active_phase:
            # check if another phase can be set to active
            for phase in self.planting_plan.phases:
                if phase.start_date and phase.start_date <= date and phase.status == FieldOperationStatus.NOT_STARTED:
                    self.active_phase = phase
                    phase.status = FieldOperationStatus.IN_PROGRESS
                    print(f"Active phase set to: {phase.phase_name}")
                    break
        
        # if all operations in the active phase are completed, set the phase status to COMPLETED
        if self.active_phase:
            all_completed = all(op.actual_date is not None for op in self.active_phase.operations)
            if all_completed:
                self.active_phase.status = FieldOperationStatus.COMPLETED
                #print(f"Phase '{self.active_phase.phase_name}' completed on {date.strftime('%Y-%m-%d')}")
                self.active_phase = None

                # plan the next phase if available
                next_phase = next((p for p in self.planting_plan.phases if p.status == FieldOperationStatus.NOT_STARTED), None)
                if next_phase:

                    if next_phase.phase_name == FieldOperationPhases.PLANTING.value:
                        self.update_planned_operations_startdates(next_phase.phase_name, date)

                    elif next_phase.phase_name == FieldOperationPhases.CROP_MANAGEMENT.value:
                        # get the last operation in the planting phase
                        last_planting_op_date = max(op.actual_date for op in sim_helper.get_operations_by_phase(self.planting_plan, "sowing_planting") if op.actual_date)

                        self.update_planned_operations_startdates(next_phase.phase_name, last_planting_op_date)

                        #print(f"Next phase '{next_phase.phase_name}' will start on {next_phase.start_date.strftime('%Y-%m-%d')}")

                    elif next_phase.phase_name == FieldOperationPhases.HARVESTING.value:
                        # get actual planting date of last op in the planting phase
                        actual_planting_date = max(op.actual_date for op in sim_helper.get_operations_by_phase(self.planting_plan, "sowing_planting"))

                        # set harvest date from planting date plus the harvest period
                        harvest_date = actual_planting_date + timedelta(days=self.planting_plan.grow_duration)
                        
                        #print(f"Next phase '{next_phase.phase_name}' will start on {harvest_date.strftime('%Y-%m-%d')}")

                        self.update_planned_operations_startdates(next_phase.phase_name, harvest_date)
                    
    def get_phase_status(self, phase_name: FieldOperationPhases) -> FieldOperationStatus:
        """
        Get the status of a specific phase in the planting plan.
        """
        phase = next((p for p in self.planting_plan.phases if p.phase_name == phase_name.value), None)
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
            #print("No active phase found. Exiting.")
            return []

        next_operations = []
        for operation in self.active_phase.operations:
            if operation.planned_date and operation.planned_date <= date and operation.actual_date is None:
                # add the operation to the next operations
                next_operations.append(operation)


        if not next_operations:
            #print("No next operations found for the active phase.")
            return []
        #print(f"Next operations for phase '{self.active_phase.phase_name}':")
  
        return next_operations
    

    def get_events_for_ops(self, operations: list[FieldOperation], date:datetime) -> list[FieldOperationEvent]:
        
        # get the variation factor for fuel consumption
        fuel_variation_factor = random.uniform(1 - self.context.fuel_variation, 1 + self.context.fuel_variation)

        # get active phase 
        events = []

        for operation in operations:
            # Process the operation
            
            # Update the actual date of the operation
            operation.actual_date = date
            print(f"    {operation.operation}: {operation.actual_date.strftime('%Y-%m-%d %H:%M:%S')}")

            event = FieldOperationEvent()

            # add a random time between 6:00 and 18:00 to the actual date and cast as datetime
            operation.actual_datetime = datetime.combine(
                operation.actual_date,
                (datetime.min + timedelta(seconds=random.randint(0,7*60*60) + 6*60*60)).time() # irgendwas zwischen 6:00 und 13:00 Uhr
            )
            event.start_date = operation.actual_datetime.strftime('%Y-%m-%d %H:%M:%S')
            event.end_date = (operation.actual_datetime + timedelta(hours=operation.duration_per_ha * self.context.field_size)).strftime('%Y-%m-%d %H:%M:%S')
            event.area = self.context.field_size
            event.fuel =  round(self.context.field_size * operation.fuel_consumption,2)
            event.worktype = operation.worktype
            event.worktype_text = operation.operation
            event.duration = round(operation.duration_per_ha * self.context.field_size*60*60,2) # Umrechnung in Sekunden
            event.durationWorked = round(event.duration * 0.95,2)
            event.distance = round(self.context.field_size * 10/ operation.working_width,2) if operation.working_width > 0 else 0
            event.distanceWorked = round(event.distance * 0.95,2)
            event.application_type = operation.application_type
            event.application_name = operation.application_name
            event.application_category = operation.application_category
            event.application_amount = round(operation.application_amount * self.context.field_size, 2)
            event.application_unit = operation.application_unit
            

            # variations for e.g. fuel consumption (in the range of 0.9 to 1.1 if set to 0.1 --> 10% variation in both directions)
            event.fuel = round(event.fuel * fuel_variation_factor, 2)

            events.append(event)
        
        return events
