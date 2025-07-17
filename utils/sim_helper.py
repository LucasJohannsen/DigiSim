import random
from datetime import datetime, timedelta
import json

from models.planting_plan import PlantingPlan, FieldPhases, FieldOperation

# get random date between start and end period
def get_random_date(start_month, end_month, year):

    # Convert month to a date in the year 2023 (or any arbitrary year)
    start_date = datetime(year, start_month, 1)
    end_date = datetime(year, end_month+1, 1)

    # Calculate the number of days between the two dates
    delta_days = (end_date - start_date).days

    # Generate a random number of days to add to the start date
    random_days = random.randint(0, delta_days)

    # Return the random date
    return start_date + timedelta(days=random_days) + timedelta(hours=random.randint(0, 23), minutes=random.randint(0, 59), seconds=random.randint(0, 59))

def get_random_date_in_range(min_days_offset, max_days_offset, target_date) -> datetime:
    
    """
    Get a random date within a specified range of days from a target date.
    
    :param min_days_offset: Minimum number of days to offset from the target date.
    :param max_days_offset: Maximum number of days to offset from the target date.
    :param target_date: The target date to offset from.
    :return: A random datetime object within the specified range.
    """
    days_offset = random.randint(min_days_offset, max_days_offset)
    return target_date + timedelta(days=days_offset)


def get_operations_by_phase(planting_plan: PlantingPlan, phase_name: str) -> list[FieldOperation]:
    """
    Get the operations for a specific phase in the planting plan.
    
    :param planting_plan: The PlantingPlan object containing the phases and operations.
    :param phase_name: The name of the phase to retrieve operations for.
    :return: A list of FieldOperations for the specified phase.
    """
    for phase in planting_plan.phases:
        if phase.phase_name == phase_name:
            return phase.operations
    return []

def get_protection_categories():
    # read the file in config/categories.json
    
    with open('config/category.json', 'r') as file:
        data = json.load(file)
        # If data is a list of categories, just return it
        return data
    