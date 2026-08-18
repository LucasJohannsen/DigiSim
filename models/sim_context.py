import datetime
from dataclasses import dataclass

@dataclass
class SimContext:
    """
    Parameters for the SimPy simulation environment.
    """
    field_size: float
    soil_type: str
    start_date: datetime.datetime
    crop_type: str
    variety: str
    field_id: int
    field_name: str
    fuel_variation: float
    field_coords: tuple[float, float] | None = None
