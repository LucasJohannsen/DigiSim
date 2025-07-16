import json
import simpy
from services.planting_plan_loader import PlantingPlanLoader
from typing import cast

from models.planting_plan import PlantingPlan, FieldOperationStatus, FieldPhases, FieldOperation, FieldOperationEvent, TargetDates

from datetime import datetime, timedelta
from utils import sim_helper

import models.sim_context as sim_context
import random


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
        # Sort operations by their sequence property
        operations = sorted(operations, key=lambda op: op.sequence)

        operation_date = target_date
    
        for operation in operations:
            min_offset = operation.min_days_to_target
            max_offset = operation.max_days_to_target

            # calculate the planned date for the operation
            operation.planned_date = sim_helper.get_random_date_in_range(min_offset, max_offset, operation_date)
            print(f"Operation '{operation.operation}' planned for date: {operation.planned_date}")



    def plan_dates(self, target_date_type: TargetDates = TargetDates.NONE):
        """
        Plan the dates for each operation in the planting plan.
        """
        if not self.planting_plan:
            print("No planting plan loaded. Exiting.")
            return

        # bestimmt das Ziel-Datum für jede Phase im Pflanzplan
        for phase in self.planting_plan.phases:
            # get the target date for the phase
            target_date_name = phase.target_date_name
            if target_date_type == TargetDates.PLANTING:
                # use the planting date for planting phases

                planting_date = sim_helper.get_random_date(
                    self.planting_plan.planting_period_months[0],
                    self.planting_plan.planting_period_months[1],
                    self.start_date.year+1
                )
                self.update_planned_dates(phase.phase_name, planting_date)
            elif target_date_name == target_date_type and target_date_name == TargetDates.HARVESTING:
                # use the harvest date for harvesting phases

                                # Calculate the harvest date based on the planting plan
                operations = sim_helper.get_operations_by_phase(self.planting_plan, "sowing_planting")

                planned_dates = [op.planned_date for op in operations if op.planned_date]
                if not planned_dates:
                    print("No planned dates found for operations in phase 'sowing_planting'. Exiting.")
                    return
                last_planned_date = max(planned_dates) # geplante Aussaat- oder Pflanztermine
                grow_duration_days = self.planting_plan.grow_duration

                harvest_date = last_planned_date + timedelta(days=grow_duration_days)

                self.update_planned_dates(phase.phase_name, harvest_date)


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
        self.plan_dates(TargetDates.PLANTING)

        # plan the dates for harvesting operations
        self.plan_dates(TargetDates.HARVESTING)


    def get_harvest_date(self) -> datetime:
        """
        Get the harvest date from the planting plan.
        """
        if not self.planting_plan or not self.planting_plan.harvest_period_months:
            print("No harvest date available in the planting plan.")
            return None

        # Calculate the harvest date based on the planting plan
        operations = sim_helper.get_operations_by_phase(self.planting_plan, "harvesting")

        # die letzte Operation in der Phase "harvesting" ist die Ernte
        if not operations:
            print("No harvesting operations found in the planting plan.")
            return None
        
        last_planned_date = max(op.planned_date for op in operations if op.planned_date)
        harvest_date = last_planned_date
        
        return harvest_date

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

                    # add a random time between 6:00 and 18:00 to the actual date and cast as datetime
                    operation.actual_datetime = datetime.combine(
                        operation.actual_date,
                        (datetime.min + timedelta(seconds=random.randint(0,7*60*60) + 6*60*60)).time() # irgendwas zwischen 6:00 und 13:00 Uhr
                    )
                    event.start_date = operation.actual_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
                    event.end_date = (operation.actual_datetime + timedelta(hours=operation.duration_per_ha * self.context.field_size)).strftime("%Y-%m-%dT%H:%M:%SZ")
                    event.area = self.context.field_size
                    event.distance = round(operation.working_width * self.context.field_size,2)
                    event.distanceWorked = round(operation.working_width * self.context.field_size * 0.95, 2)
                    event.fuel =  self.context.field_size * operation.fuel_consumption
                    event.worktype = operation.worktype
                    event.worktype_text = operation.operation
                    event.duration = round(operation.duration_per_ha * self.context.field_size,2)
                    event.durationWorked = round(event.duration * 0.95,2)
                    event.distance = round(self.context.field_size/ operation.working_width if operation.working_width > 0 else 0,2)
                    event.distanceWorked = round(event.distance * 0.95,2)

                    events.append(event)
        
        return events    


