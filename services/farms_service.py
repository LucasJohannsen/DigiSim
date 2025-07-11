from models.farms import Farm, Field
from typing import cast


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
        #validate first

        self.validate_farm_data(self._load_farms())
        # then load farms
        farms_data = self._load_farms()
        # validate each farm
        return farms_data
    

    def _load_farms(self) -> list[Farm]:
        """
        Load farms from the JSON file and return a Farms object.
        """
        import json
        with open(self.farms_file, 'r') as file:
            data = json.load(file)

        farms = []
        for data in data['farms']:
            fields = [Field(**field) for field in data['fields']]
            farm = Farm(id=data['id'], name=data['name'], fields=fields)
            farms.append(farm)

        
        
        return farms