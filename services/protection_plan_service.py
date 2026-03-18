import random
from datetime import datetime, timedelta
from typing import Tuple

from services.planting_plan_loader import PlantingPlanLoader
from models.planting_plan import (
    FieldOperationStatus,
    FieldOperationCycle,
    FieldOperation,
    FieldOperationEvent,
    TargetDates,
    FieldOperationPhases,
    PlantingPlan
)
import models.sim_context as sim_context
from utils import sim_helper


class ProtectionPlanService:

    def __init__(self, context: sim_context.SimContext, start_date:datetime, planting_plan:PlantingPlan=None):
        self.context = context
        
        self.start_date = start_date  # Planned date for planting operations
        self.planting_plan = planting_plan

        self.operations = []

        self.plan_protections()

  
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


        # Schadensereignis
        target_date_diff = protection_plan.days_to_target
        protection_target_date = self.start_date + timedelta(days=target_date_diff)

        print(f"Planned protection date: {protection_target_date.strftime('%Y-%m-%d')}")

        # erstelle die Schutzoperationen
        for protection in protection_plan.protections:
            protection_operation_date = protection_target_date + timedelta(days=protection.day)

            # Calculate the sum if protection.amount contains '+'
            # Sonderfall Spritzmischung -> Mengenangaben wie "1.5+0.5" müssen zu 2.0 addiert werden         
            application_amount = sum(float(x) for x in protection.amount.split('+'))

            #get the category from the protection categories
            category_item = next((c for c in protection_categories if c['id'] == protection.type), None)
            application_type_text = category_item['category'] if category_item else "unknown"
 
            spritz_operation = FieldOperation(
                operation="Spritzen",
                worktype=14,
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

            #print(f"Planned protection operation: {spritz_operation.operation} on {spritz_operation.planned_date.strftime('%Y-%m-%d')}")
            
            self.operations.append(spritz_operation)

    def get_next_operations(self, date: datetime) -> list[FieldOperation]:
        """
        Get the next operations for the protection plan based on the current date.
        :param date: The current date in the simulation.

        """
        if not self.operations:
            print("No protection operations planned.")
            return []
        next_operations = []
        for operation in self.operations:
            if operation.planned_date <= date and not operation.actual_date:
                next_operations.append(operation)
        if not next_operations:
            #print("No next operations found for the protection plan.")
            return []

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
            print(f"    {operation.operation}: {operation.actual_date.strftime("%Y-%m-%d")}")

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
            event.field = self.context.field_id

            # variations for e.g. fuel consumption (in the range of 0.9 to 1.1 if set to 0.1 --> 10% variation in both directions)
            event.fuel = round(event.fuel * fuel_variation_factor, 2)

            events.append(event)
        
        return events
