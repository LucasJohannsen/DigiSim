import json
import os

from models.planting_plan import (
    FieldOperation,
    FieldOperationCycle,
    PlantingPlan,
    Protection,
    ProtectionPlan,
    TargetDates,
)


class PlantingPlanLoader:
    config_dir = os.path.join(os.path.dirname(__file__), "..", "config")

    def __init__(self, crop_type=None, variety=None):
        """
        Initialize the PlantingPlanLoader with optional crop type and variety.
        :param crop_type: The type of crop (e.g., 'potato').
        :param variety: The specific variety of the crop (e.g., 'early').
        """
        self.config_dir = PlantingPlanLoader.config_dir
        self.crop_type = crop_type
        self.variety = variety
        self.planting_plan = None

    def load_planting_plan(self, file_path):
        """
        Load the planting plan from a JSON file.
        :param file_path: Path to the JSON file containing the planting plan.
        :return: PlantingPlan object or None if loading fails.
        """
        try:
            with open(file_path, encoding="utf-8") as file:
                planting_plan_data = json.load(file)
            return planting_plan_data
        except FileNotFoundError:
            print(f"Error: The file {file_path} was not found.")
            return None
        except json.JSONDecodeError:
            print(f"Error: The file {file_path} is not a valid JSON file.")
            return None

    def find_planting_plan(self):
        """
        Find a planting plan for a specific crop type.

        :param crop_type: The type of crop to find the planting plan for.
        :return: Dictionary representing the planting plan for the specified crop type.
        """

        # if no crop type or variety is specified, return None
        if not self.crop_type or not self.variety:
            print("Crop type and variety must be specified to find a planting plan.")
            return None

        # read all planting plans from the config directory
        # search all planting_plan* files and return the first one that matches the crop type and variety

        for file_name in os.listdir(self.config_dir):
            if file_name.startswith("planting_plan_") and file_name.endswith(".json"):
                file_path = os.path.join(self.config_dir, file_name)
                planting_plan = self.load_planting_plan(file_path)
                if (
                    planting_plan
                    and planting_plan.get("crop", "").lower() == self.crop_type.lower()
                    and planting_plan.get("variety", "").lower() == self.variety.lower()
                ):
                    return planting_plan

        print(
            f"No planting plan found for crop type '{self.crop_type}' and variety '{self.variety}'."
        )
        return None

    def get_all_planting_plans(self):
        """
        Get all available planting plans from the config directory.

        :return: List of dictionaries representing all planting plans.
        """
        planting_plans = []
        for file_name in os.listdir(self.config_dir):
            if file_name.startswith("planting_plan_") and file_name.endswith(".json"):
                file_path = os.path.join(self.config_dir, file_name)
                planting_plan = self.load_planting_plan(file_path)
                if planting_plan:
                    planting_plans.append(planting_plan)
        return planting_plans

    def get_planting_plan(self) -> PlantingPlan:
        """
        Converts the loaded JSON planting plan into a PlantingPlan object.

        :return: PlantingPlan object containing the planting plan data.
        """
        if not self.planting_plan:
            # load the planting plan from a file
            self.planting_plan = self.find_planting_plan()

        if not self.planting_plan:
            print("No planting plan found. Exiting simulation.")
            return None

        phases = []
        for phase in self.planting_plan.get("phases"):
            phase_name = list(phase.keys())[0]  # Get the phase name (e.g., 'soil_preparation')

            operations = [
                FieldOperation(**op) for op in phase.get(phase_name, {}).get("operations", [])
            ]
            # phase is a dict like {'soil_preparation': {...}}

            # Convert the target date name to an enum value
            target_date_name = phase.get(phase_name, {}).get("target_date_name", "NONE").upper()
            target_date_name = (
                TargetDates[target_date_name]
                if target_date_name in TargetDates.__members__
                else TargetDates.NONE
            )

            phases.append(
                FieldOperationCycle(
                    phase_name=phase_name, operations=operations, target_date_name=target_date_name
                )
            )

        # protection plans
        protection_plans = []
        for protection_plan in self.planting_plan.get("protection_plans", []):
            protections = [Protection(**p) for p in protection_plan.get("protections", [])]
            protection_plans.append(
                ProtectionPlan(
                    name=protection_plan.get("name"),
                    description=protection_plan.get("description"),
                    days_to_target=protection_plan.get("days_to_target", 0),
                    protections=protections,
                )
            )

        return PlantingPlan(
            crop_type=self.crop_type,
            variety=self.variety,
            planting_period_months=tuple(self.planting_plan["planting_period_months"]),
            harvest_period_months=tuple(self.planting_plan["harvest_period_months"]),
            grow_duration=self.planting_plan.get(
                "growth_duration", 90
            ),  # Default to 90 days if not specified
            phases=phases,
            protection_plans=protection_plans,
        )
