import json
import os

from dotenv import load_dotenv
import requests

from models.farms import Farm, Field

class FarmLoaderService:
    """
    Service to load farm data from a JSON file.
    """
    def __init__(self):
        self.farms_file = "config/farms.json"

    def validate_farm_data(self, farm_data: list[Farm]):
        """
        Validates the farm data structure.
        """

        for farm in farm_data:
            

            # ensure id of each field is unique
            field_ids = [field.id for field in farm.fields]
            if len(field_ids) != len(set(field_ids)):
                # say which field ids are duplicated
                duplicates = set([x for x in field_ids if field_ids.count(x) >
                                    1])
                raise ValueError(f"Duplicate field IDs found: {', '.join(map(str, duplicates))}")


    
    def get_farms(self) -> list[Farm]:
        """
        Get a list of Farm objects.
        """
        # Load farms data once
        farms_data = self._load_farms()

        # Validate the loaded data
        self.validate_farm_data(farms_data)

        # Return the validated farms data
        return farms_data
    
    def _load_farms(self) -> list[Farm]:
        """
        Load farms from the API if .env is available, otherwise load from the JSON file.
        """
        try:
            # Attempt to load from API if .env is available
            load_dotenv()
            api_url = os.getenv("API_URL")
            if api_url:
                return self._load_farms_from_api(api_url)
        except Exception as e:
            print(f"Failed to load from API, falling back to JSON file: {e}")

        # Fallback to loading from JSON file
        return self._load_farms_from_file()

    def _load_farms_from_api(self, api_url: str) -> list[Farm]:
        """
        Load farms and fields data from the API.
        """
        farms = []
        response = requests.get(f"http://{api_url}/api/v1/enterprises")
        if response.status_code == 200:
            print("Loading farms from API....")
            data = response.json()
            for result in data['results']:
                farm = {
                    "id": result['id'],
                    "name": result['name'],
                    "fields": [],
                }
                farms.append(farm)

        response = requests.get(f"http://{api_url}/api/v1/fields")
        if response.status_code == 200:
            fields_data = []
            while response:
                data = response.json()
                for result in data['results']:
                    field = {
                        "id": result['id'],
                        "name": result['name'],
                        "area": result['area'],
                        "distance_to_barn": 0,
                        "soil_type": "sand",
                    }
                    fields_data.append(field)
                next_page = data.get('next')
                if next_page:
                    response = requests.get(next_page)
                else:
                    response = None

            # Map fields to their respective farms
            for farm in farms:
                farm['fields'] = [field for field in fields_data if field.get('enterprise') == farm['id']]

            # Convert to Farm and Field objects
            farm_objects = []
            for farm in farms:
                fields = [Field(**field) for field in farm['fields']]
                farm_obj = Farm(id=farm['id'], name=farm['name'], fields=fields)
                farm_objects.append(farm_obj)

            return farm_objects

        raise ValueError("Failed to load farms or fields from API.")

    def _load_farms_from_file(self) -> list[Farm]:
        """
        Load farms data from the JSON file.
        """
        with open(self.farms_file, 'r') as file:
            data = json.load(file)

        farms = []
        for data in data['farms']:
            fields = [Field(**field) for field in data['fields']]
            farm = Farm(id=data['id'], name=data['name'], fields=fields)
            farms.append(farm)
        return farms
