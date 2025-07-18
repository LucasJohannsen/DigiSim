import random
from datetime import datetime, timedelta
from typing import Tuple

from services.planting_plan_loader import PlantingPlanLoader
from models.planting_plan import (
    FieldOperationStatus,
    FieldPhases,
    FieldOperation,
    FieldOperationEvent,
    TargetDates,
)
import models.sim_context as sim_context
from utils import sim_helper


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


    def get_min_max_dates_of_phase(self, phase_name: str) -> Tuple[datetime, datetime]:
        """
        Get the last planned date of a specific phase in the planting plan.
        """
        # Find the phase by name
        phase = next((p for p in self.planting_plan.phases if p.phase_name == phase_name), None)
        
        # Get the last planned date from the operations in the phase
        last_date = max((op.planned_date for op in phase.operations if op.planned_date), default=None)
        first_date = min((op.planned_date for op in phase.operations if op.planned_date), default=None)
        
        return first_date, last_date


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


    def plan_protections(self):
        """
        Plan the protection operations for the planting plan.
        """
        if not self.planting_plan or not self.planting_plan.protection_plans:
            print("No protection plans available in the planting plan.")
            return


        # read categories from config
        protection_categories = sim_helper.get_protection_categories()

        # Iterate through each protection plan and apply protections

        # pick random protection plan
        protection_plan = random.choice(self.planting_plan.protection_plans)
        print(f"Selected protection plan: {protection_plan.name}")

        # get the last planned date from the planting phase
        _, planting_date = self.get_min_max_dates_of_phase("sowing_planting")
        harvest_date, _ = self.get_min_max_dates_of_phase("harvesting")

        # Schadensereignis
        target_date_diff = protection_plan.days_to_target
        protection_target_date = planting_date + timedelta(days=target_date_diff)

        print(f"Planned protection date: {protection_target_date.strftime('%Y-%m-%d')}")

        # erstelle die Schutzoperationen
        for protection in protection_plan.protections:
            protection_operation_date = protection_target_date + timedelta(days=protection.day)

            if protection_operation_date >= harvest_date:
                print(f"Protection operation date {protection_operation_date.strftime('%Y-%m-%d')} is after harvest date. Skipping.")
                continue

            # Calculate the sum if protection.amount contains '+'
            # Sonderfall Spritzmischung -> Mengenangaben wie "1.5+0.5" müssen zu 2.0 addiert werden         
            application_amount = sum(float(x) for x in protection.amount.split('+'))

            #get the category from the protection categories
            category_item = next((c for c in protection_categories if c['id'] == protection.type), None)
            application_type_text = category_item['category'] if category_item else "unknown"
 
            spritz_operation = FieldOperation(
                operation="Spritzen",
                worktype=0,
                duration_per_ha=0.2,  
                working_width=18,
                fuel_consumption=1,  
                planned_date=protection_operation_date,
                application_type=application_type_text,
                application_category=protection.type,
                application_name=f"{protection.name} ({protection.amount})",
                application_amount=application_amount,
                application_unit=2
            )

            print(f"Planned protection operation: {spritz_operation.operation} on {spritz_operation.planned_date.strftime('%Y-%m-%d')}")
            # add the operation to the planting plan, phase crop_management
            phase = next((p for p in self.planting_plan.phases if p.phase_name == "crop_management"), None)
            if not phase:
                print("No phase 'crop_management' found in the planting plan. Creating a new phase.")
                phase = FieldPhases(phase_name="crop_management", operations=[], status=FieldOperationStatus.NOT_STARTED)
                self.planting_plan.phases.append(phase)
            
            phase.operations.append(spritz_operation)


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

        # protections
        self.plan_protections()


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
        
        # get the variation factor for fuel consumption
        fuel_variation_factor = random.uniform(1 - self.context.fuel_variation, 1 + self.context.fuel_variation)

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


