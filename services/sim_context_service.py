import datetime
from services.farms_service import FarmLoaderService
from services.planting_plan_loader import PlantingPlanLoader  
from models.sim_context import SimContext
import random

def collect(context: SimContext, defaults=None):

    if defaults is None:
        defaults = {
            "field_size": context.field_size,
            "soil_type": context.soil_type,
            "start_date": context.start_date,
            "crop_type": context.crop_type,
            "variety": context.variety,
            "field_id": context.field_id,
            "field_name": context.field_name,
        }

    def get_input(prompt, param_type=str, choices=None, validator=None, default=None):
        while True:
            user_input = input(prompt)
            if not user_input and default is not None:
                return default
            try:
                value = param_type(user_input)
                if choices and value not in choices:
                    print(f"Please choose from: {choices}")
                    continue
                if validator and not validator(value):
                    print("Invalid value.")
                    continue
                return value
            except Exception as e:
                print(f"Error: {e}")

    context.field_id = get_input(
        f"Enter field ID [{defaults['field_id']}]: ",
        int,
        default=defaults["field_id"]
    )
    context.field_name = get_input(
        f"Enter field name [{defaults['field_name']}]: ",
        str,
        default=defaults["field_name"]
    )
    context.field_size = get_input(
        f"Enter field size [{defaults['field_size']}]: ",
        float,
        validator=lambda x: x > 0,
        default=float(defaults["field_size"])
    )
    context.soil_type = get_input(
        f"Enter soil type (sand, clay) [{defaults['soil_type']}]: ",
        str,
        choices=["sand", "clay"],
        default=defaults["soil_type"]
    )
    context.start_date = get_input(
        f"Enter start date (YYYY-MM-DD) [{defaults['start_date'].strftime('%Y-%m-%d')}]: ",
        lambda s: datetime.datetime.strptime(s, "%Y-%m-%d"),
        default=defaults["start_date"] if isinstance(defaults["start_date"], datetime.datetime) else datetime.datetime.strptime(defaults["start_date"], "%Y-%m-%d")
    )
    context.crop_type = get_input(
        f"Enter crop type [{defaults['crop_type']}]: ",
        str,
        default=defaults["crop_type"]
    )
    context.variety = get_input(
        f"Enter crop variety [{defaults['variety']}]: ",
        str,
        default=defaults["variety"]
    )
    return context

def get_simulation_context():
    """
    Collects simulation parameters from the user and returns a SimContext object.
    This function allows the user to select a farm and field, and then collect parameters for the simulation.
    """

    print('Select a farm from the list')
    farm_loader = FarmLoaderService()
    farms = farm_loader.get_farms()
    # Print farm table header
    print(f"{'Farm ID':<10} {'Name':<20}")
    print('-' * 30)
    for farm in farms:
        print(f"{farm.id:<10} {farm.name:<20}")

    farm_id = input('\nEnter the Farm ID to select: ')
    selected_farm = next((f for f in farms if f.id == int(farm_id)), None)
    if not selected_farm:
        print("Invalid Farm ID selected.")
        return

    # List fields in the selected farm
    print('\nFields in the selected farm:')
    print(f"{'Field ID':<10} {'Name':<25} {'Distance to Barn (km)':<22} {'Area (ha)':<10}")
    print('-' * 70)
    for field in selected_farm.fields:
        print(f"{field.id:<10} {field.name:<25} {field.distance_to_barn:<22} {field.area:<10}")

    field_id = input('\nEnter the Field ID to select: ')
    selected_field = next((f for f in selected_farm.fields if f.id == int(field_id)), None)
    if not selected_field:
        print("Invalid Field ID selected.")
        return
    
    return selected_field
    
def get_batch_simulation_context() -> list[SimContext]:
    """
    Collects simulation contexts for all fields in all farms.
    Returns a list of SimContext objects for each field.
    """

    # Collect all farms
    farm_loader = FarmLoaderService()
    farms = farm_loader.get_farms()

    batch_contexts = []
    print(f"{'Farm ID':<10} {'Name':<20}")
    print('-' * 30)
    for farm in farms:
        print(f"{farm.id:<10} {farm.name:<20}")

    farm_id = input('\nEnter the Farm ID to select: ')
    farm = next((f for f in farms if f.id == int(farm_id)), None)
    if not farm:
        print("Invalid Farm ID selected.")
        return
    
    print(f"\nProcessing farm: {farm.name} (ID: {farm.id})")
    for field in farm.fields:
        print(f"  Field: {field.name} (ID: {field.id}, Area: {field.area} ha)")

        plans = PlantingPlanLoader().get_all_planting_plans()
        if not plans:
            print("No planting plans available for this field.")
            continue
        planting_plan = random.choice(plans)

        context = SimContext(
            field_size=field.area,
            field_id=field.id,
            field_name=field.name,
            soil_type=field.soil_type,
            start_date=datetime.datetime.now(),  # Default or random choice
            crop_type=planting_plan.get('crop_type', 'Potato'),  # Default or random choice
            variety=planting_plan.get('variety', 'Belana'),  # Default or random choice
            fuel_variation=random.uniform(0.05, 0.15)  # Random variation in fuel consumption
        )
        batch_contexts.append(context)
    
    return batch_contexts
    