import json
import simpy
from services.planting_plan_loader import PlantingPlanLoader
from typing import cast

from models.planting_plan import PlantingPlan, FieldOperationStatus, FieldPhases, FieldOperation, FieldOperationEvent

from datetime import datetime, timedelta
from utils import sim_helper

import models.sim_context as sim_context


class PlantingPlanService:

    def __init__(self, context: sim_context.SimContext, start_date:datetime):
        self.context = context
        
        self.start_date = start_date

        self.planting_plan = None
        

    def update_planned_dates(self, phase_name: str, target_date: datetime):
        """
        Update the planned dates for a specific operation in the planting plan.
        """
 
        # get the list of operations for the specified phase
        operations = sim_helper.get_operations_by_phase(self.planting_plan, phase_name)

        operation_date = target_date
    
        for operation in operations:
            min_offset = operation.min_days_to_target
            max_offset = operation.max_days_to_target

            # calculate the planned date for the operation
            operation.planned_date = sim_helper.get_random_date_in_range(min_offset, max_offset, operation_date)
            print(f"Operation '{operation.operation}' planned for date: {operation.planned_date}")



    def plan_dates(self):
        """
        Plan the dates for each operation in the planting plan.
        """
        if not self.planting_plan:
            print("No planting plan loaded. Exiting.")
            return

        # determine the target dates based on the planting plan
        planting_date = sim_helper.get_random_planting_date(self.planting_plan, self.start_date.year + 1)
        harvest_date = sim_helper.get_random_harvest_date(self.planting_plan, self.start_date.year + 1)

        print(f"Planting date: {planting_date}, Harvest date: {harvest_date}")


        # soil preparation operations
        self.update_planned_dates("soil_preparation", planting_date)
        
        # sowing/planting operations
        self.update_planned_dates("sowing_planting", planting_date)

        # crop management operations
        self.update_planned_dates("crop_management", planting_date)

        # harvesting operations
        self.update_planned_dates("harvesting", planting_date)


    def prepare_planting_plan(self):

        # get the planting plan from the loader
        self.planting_plan = PlantingPlanLoader(
            crop_type=self.context.crop_type,
            variety=self.context.variety
        ).get_planting_plan()

        if not self.planting_plan:
            print("No planting plan found. Exiting simulation.")
            return
        
        # plan the dates for each operation in the planting plan
        self.plan_dates()


    def handle_next_operation(self, timestamp: datetime):

        """
        Handle the next operation based on the current timestamp.
        """
        # Check if there are any operations to process
        if not self.planting_plan or not self.planting_plan.phases:
            print("No planting plan phases available.")
            return

        # Iterate through each phase and its operations
        events = []
        for phase in self.planting_plan.phases:  
            for operation in phase.operations:
                if operation.planned_date and operation.planned_date.date() <= timestamp and operation.actual_date is None:
                    # Process the operation
                    
                    # Update the actual date of the operation
                    operation.actual_date = timestamp
                    print(f"    {operation.operation}: {operation.actual_date.strftime("%Y-%m-%dT%H:%M:%SZ")}")

                    event = FieldOperationEvent()
                    event.start_date = operation.actual_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                    event.end_date = (operation.actual_date + timedelta(hours=operation.duration_per_ha*self.context.field_size)).strftime("%Y-%m-%dT%H:%M:%SZ")
                    event.area = self.context.field_size
                    event.distance = operation.working_width * self.context.field_size
                    event.distanceWorked = operation.working_width * self.context.field_size * 0.95
                    event.fuel =  self.context.field_size * operation.fuel_consumption
                    event.worktype = operation.worktype
                    event.worktype_text = operation.operation
                    event.duration = operation.duration_per_ha * self.context.field_size
                    event.durationWorked = event.duration * 0.95
                    event.distance = self.context.field_size/ operation.working_width if operation.working_width > 0 else 0
                    event.distanceWorked = event.distance * 0.95

                    events.append(event)
        
        return events    


