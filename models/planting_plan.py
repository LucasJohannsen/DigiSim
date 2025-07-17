
from dataclasses import dataclass
from typing import Tuple
from datetime import datetime

from enum import Enum

@dataclass
class FieldOperationEvent():
    batch: str = None
    field: int = 0
    worktype: int = 0
    exa_id: int = 0
    start_date: str = None
    end_date: str = None
    area: float = 0.0
    distance: float = 0.0
    distanceWorked: float = 0.0
    duration: float = 0.0
    durationWorked: float = 0.0
    fuel: float = 0.0
    application_type: str = None
    application_category: str = None
    application_name: str = None
    application_amount: float = 0.0
    application_unit: str = None
    worktype_text: str = None
    machine: str = None  # Machine used for the operation


class FieldOperationStatus(Enum):
    """
    Enum representing the status of a field operation.
    """
    NOT_STARTED = "Not started"
    IN_PROGRESS = "In progress"
    COMPLETED = "Completed"
    FAILED = "Failed"

class TargetDates(Enum):
    """
    Enum representing the target dates for field operations.
    """
    NONE = "None"
    PLANTING = "Planting"
    HARVESTING = "Harvesting"
    FERTILIZATION = "Fertilization"

@dataclass
class FieldOperation:
    """
    Represents a collection of operations to be performed on a field.
    """
    sequence:  int = None # Sequence number of the operation in the planting plan
    operation: str = None
    
    min_days_to_target: int  = None # Minimum number of days to the target date for this
    max_days_to_target: int  = None # Maximum number of days to the target date for this operation

    offset_prev_operation: int = None  # Offset in days from the previous operation

    duration_per_ha: float = None  # Duration of the operation per hectare in hours
    working_width: float  = None # Working width of the equipment in meters
    fuel_consumption: float = None  # Fuel consumption per hectare in liters
    worktype: int = None  # Work type ID for the operation

    planned_date: datetime = None
    actual_date: datetime = None  # Actual date when the operation was performed

    application_type: str = None  
    category: str = None  
    application_name: str = None
    application_category: str = None  
    application_amount: float = 0
    application_unit: str = None

@dataclass
class FieldPhases:
    phase_name: str  # Name of the phase (e.g., "soil_preparation", "planting", "harvesting")
    operations: list[FieldOperation]  # List of operations to be performed in this phase
    status: FieldOperationStatus = FieldOperationStatus.NOT_STARTED  # Status of the phase operations
    target_date_offset: int = 0  # Offset in days from the target date for this phase
    target_date_name: TargetDates = TargetDates.NONE  # Target date for the phase operations

@dataclass
class ApplicationCategory:
    id: int
    category: str
    name: str
    

@dataclass
class Protection:
    
    day: int = 0
    type: int = 0
    name: str = None
    amount: str = None

@dataclass
class ProtectionPlan:
    """
    Represents a protection plan for a specific crop variety.
    """
    name: str
    description: str
    days_to_target: int  # Number of days to the target date for the protection plan
    protections: list[Protection]  # List of protections to be applied in the plan

@dataclass
class PlantingPlan:
    """
    Represents a planting plan for a specific crop variety.
    """
    crop_type: str
    variety: str
    planting_period_months: Tuple[int, int]  # Start and end month of the planting period
    harvest_period_months: Tuple[int, int]  # Start and end month of the harvest period
    grow_duration: int  # Duration of the crop growth in days
    phases: list[FieldPhases]  # List of phases in the planting plan
    protection_plans: list[ProtectionPlan] = None  # List of protection plans for the crop variety

