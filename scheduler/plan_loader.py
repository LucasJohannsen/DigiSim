# load the planting plan

import json


class PlantingPlanLoader:
    """
    A class to load planting plans from JSON files.
    """

    def __init__(self, crop_type, variety):
        self.crop_type = crop_type
        self.variety = variety
        self.planting_plan = self.load_planting_plan(self.find_planting_plan())

    def load_planting_plan(self, file_path):
        """
        Load the planting plan from a JSON file.

        :param file_path: Path to the JSON file containing the planting plan.
        :return: Dictionary representing the planting plan.
        """
        try:
            with open(file_path, 'r') as file:
                planting_plan = json.load(file)
            return planting_plan
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
        
        return 'config/planting_plan_potato.json'