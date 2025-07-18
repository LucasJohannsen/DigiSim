import datetime
from dataclasses import dataclass

@dataclass
class SimContext:
    """
    Parameters for the SimPy simulation environment.
    """
    field_size: float = 10.0  # Default field size for the simulation
    soil_type: str = 'sand'  # Default soil type for the simulation
    start_date: datetime.date = datetime.date(2024, 10, 1)  # Default start date for the simulation
    crop_type: str = 'Potato'  # Default crop type for the simulation
    variety: str = 'Belana'  # Default crop variety
    field_id: int = 1
    field_name: str = 'Kiel'
    fuel_variation: float = 0.1  # Default variation in fuel consumption for batch simulations

    


    