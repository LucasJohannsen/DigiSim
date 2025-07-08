import datetime
from dataclasses import dataclass
@dataclass
class SimContext:
    """
    Parameters for the SimPy simulation environment.
    """
    field_size: float = 10.0  # Default field size for the simulation
    soil_type: str = 'sand'  # Default soil type for the simulation
    harvest_date: datetime.date = datetime.date(2025, 9, 15)  # Default harvest date
    start_date: datetime.date = datetime.date(2024, 10, 1)  # Default start date for the simulation
    crop_type: str = 'Potato'  # Default crop type for the simulation
    variety: str = 'Belana'  # Default crop variety

    def collect(self, defaults=None):

        if defaults is None:
            defaults = {
                "field_size": self.field_size,
                "soil_type": self.soil_type,
                "start_date": self.start_date,
                "harvest_date": self.harvest_date,
                "crop_type": self.crop_type,
                "variety": self.variety
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

        self.field_size = get_input(
            f"Enter field size [{defaults['field_size']}]: ",
            float,
            validator=lambda x: x > 0,
            default=float(defaults["field_size"])
        )
        self.soil_type = get_input(
            f"Enter soil type (sand, clay) [{defaults['soil_type']}]: ",
            str,
            choices=["sand", "clay"],
            default=defaults["soil_type"]
        )
        self.start_date = get_input(
            f"Enter start date (YYYY-MM-DD) [{defaults['start_date']}]: ",
            lambda s: datetime.datetime.strptime(s, "%Y-%m-%d").date(),
            default=defaults["start_date"] if isinstance(defaults["start_date"], datetime.date) else datetime.datetime.strptime(defaults["start_date"], "%Y-%m-%d").date()
        )
        def harvest_validator(harvest_date):
            return harvest_date > self.start_date

        self.harvest_date = get_input(
            f"Enter harvest date (YYYY-MM-DD) [{defaults['harvest_date']}]: ",
            lambda s: datetime.datetime.strptime(s, "%Y-%m-%d").date(),
            validator=harvest_validator,
            default=defaults["harvest_date"] if isinstance(defaults["harvest_date"], datetime.date) else datetime.datetime.strptime(defaults["harvest_date"], "%Y-%m-%d").date()
        )
        self.crop_type = get_input(
            f"Enter crop type [{defaults['crop_type']}]: ",
            str,
            default=defaults["crop_type"]
        )
        self.variety = get_input(
            f"Enter crop variety [{defaults['variety']}]: ",
            str,
            default=defaults["variety"]
        )

        return self
