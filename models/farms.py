from dataclasses import dataclass

@dataclass
class Field:
    id: int
    name: str
    distance_to_barn: float # in km
    area: float # in ha
    soil_type: str


@dataclass
class Farm:
    id: int
    name: str
    fields: list[Field]

