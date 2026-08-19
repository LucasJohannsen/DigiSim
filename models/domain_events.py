import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any


@dataclass
class DomainEvent:
    """
    Base class for all domain events in the simulation.
    
    Domain events represent significant occurrences within the simulation
    that are relevant for traceability, debugging, and potential replay.
    
    Attributes:
        event_id: Unique identifier for this event (UUID)
        event_type: Type/name of the event (e.g., 'DailyTickStarted')
        timestamp: When the event occurred
        field_id: ID of the field this event relates to
        payload: Event-specific data
    """
    event_id: str
    event_type: str
    timestamp: datetime
    field_id: str
    payload: dict[str, Any]
    
    def to_dict(self) -> dict[str, Any]:
        """
        Serialize the event to a dictionary.
        
        Returns:
            Dictionary representation with ISO-formatted timestamp
        """
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'DomainEvent':
        """
        Deserialize an event from a dictionary.
        
        Args:
            data: Dictionary with event data
            
        Returns:
            DomainEvent instance
        """
        data_copy = data.copy()
        if isinstance(data_copy.get('timestamp'), str):
            data_copy['timestamp'] = datetime.fromisoformat(data_copy['timestamp'])
        return cls(**data_copy)


def create_daily_tick_started(
    field_id: str,
    date: datetime
) -> DomainEvent:
    """
    Create a DailyTickStarted event.
    
    Emitted at the beginning of each simulation tick.
    
    Args:
        field_id: ID of the field being simulated
        date: The simulation date for this tick
        
    Returns:
        DomainEvent with type 'DailyTickStarted'
    """
    return DomainEvent(
        event_id=str(uuid.uuid4()),
        event_type='DailyTickStarted',
        timestamp=datetime.now(),
        field_id=field_id,
        payload={
            'date': date.isoformat() if isinstance(date, datetime) else str(date)
        }
    )


def create_daily_tick_completed(
    field_id: str,
    date: datetime,
    events_dispatched: int
) -> DomainEvent:
    """
    Create a DailyTickCompleted event.
    
    Emitted at the end of each simulation tick.
    
    Args:
        field_id: ID of the field being simulated
        date: The simulation date for this tick
        events_dispatched: Number of integration events dispatched during this tick
        
    Returns:
        DomainEvent with type 'DailyTickCompleted'
    """
    return DomainEvent(
        event_id=str(uuid.uuid4()),
        event_type='DailyTickCompleted',
        timestamp=datetime.now(),
        field_id=field_id,
        payload={
            'date': date.isoformat() if isinstance(date, datetime) else str(date),
            'events_dispatched': events_dispatched
        }
    )


def create_crop_cycle_scheduled(
    field_id: str,
    date: datetime,
    planned_planting_date: datetime,
    crop_type: str
) -> DomainEvent:
    """
    Create a CropCycleScheduled event.

    Emitted when the planting date for a crop cycle has been determined
    (planned, not yet executed). Makes the scheduling decision traceable
    (Befund B2, Issue #58).

    Args:
        field_id: ID of the field
        date: Date when the scheduling decision was made (typically the
            simulation start date)
        planned_planting_date: The planned planting date for this cycle
        crop_type: Type of crop being planted

    Returns:
        DomainEvent with type 'CropCycleScheduled'
    """
    return DomainEvent(
        event_id=str(uuid.uuid4()),
        event_type='CropCycleScheduled',
        timestamp=datetime.now(),
        field_id=field_id,
        payload={
            'date': date.isoformat() if isinstance(date, datetime) else str(date),
            'planned_planting_date': (
                planned_planting_date.isoformat()
                if isinstance(planned_planting_date, datetime)
                else str(planned_planting_date)
            ),
            'crop_type': crop_type
        }
    )


def create_crop_cycle_started(
    field_id: str,
    date: datetime,
    crop_type: str
) -> DomainEvent:
    """
    Create a CropCycleStarted event.

    Emitted when a new crop cycle begins (typically at planting).

    Args:
        field_id: ID of the field
        date: Date when the crop cycle started
        crop_type: Type of crop being planted

    Returns:
        DomainEvent with type 'CropCycleStarted'
    """
    return DomainEvent(
        event_id=str(uuid.uuid4()),
        event_type='CropCycleStarted',
        timestamp=datetime.now(),
        field_id=field_id,
        payload={
            'date': date.isoformat() if isinstance(date, datetime) else str(date),
            'crop_type': crop_type
        }
    )


def create_harvest_completed(
    field_id: str,
    date: datetime,
    yield_estimate: float | None = None
) -> DomainEvent:
    """
    Create a HarvestCompleted event.
    
    Emitted when harvest operations are completed.
    
    Args:
        field_id: ID of the field
        date: Date when harvest was completed
        yield_estimate: Optional estimated yield
        
    Returns:
        DomainEvent with type 'HarvestCompleted'
    """
    return DomainEvent(
        event_id=str(uuid.uuid4()),
        event_type='HarvestCompleted',
        timestamp=datetime.now(),
        field_id=field_id,
        payload={
            'date': date.isoformat() if isinstance(date, datetime) else str(date),
            'yield_estimate': yield_estimate
        }
    )


def create_operation_considered(
    field_id: str,
    date: datetime,
    operation_type: str,
    worktype: int
) -> DomainEvent:
    """
    Create an OperationConsidered event.
    
    Emitted when an operation is evaluated as a candidate for execution.
    
    Args:
        field_id: ID of the field
        date: Date when the operation was considered
        operation_type: Type/name of the operation
        worktype: Worktype ID of the operation
        
    Returns:
        DomainEvent with type 'OperationConsidered'
    """
    return DomainEvent(
        event_id=str(uuid.uuid4()),
        event_type='OperationConsidered',
        timestamp=datetime.now(),
        field_id=field_id,
        payload={
            'date': date.isoformat() if isinstance(date, datetime) else str(date),
            'operation_type': operation_type,
            'worktype': worktype
        }
    )


def create_operation_approved(
    field_id: str,
    date: datetime,
    operation_type: str,
    worktype: int
) -> DomainEvent:
    """
    Create an OperationApproved event.
    
    Emitted when an operation is approved for execution by the DecisionManager.
    
    Args:
        field_id: ID of the field
        date: Date when the operation was approved
        operation_type: Type/name of the operation
        worktype: Worktype ID of the operation
        
    Returns:
        DomainEvent with type 'OperationApproved'
    """
    return DomainEvent(
        event_id=str(uuid.uuid4()),
        event_type='OperationApproved',
        timestamp=datetime.now(),
        field_id=field_id,
        payload={
            'date': date.isoformat() if isinstance(date, datetime) else str(date),
            'operation_type': operation_type,
            'worktype': worktype
        }
    )


def create_operation_rejected(
    field_id: str,
    date: datetime,
    operation_type: str,
    worktype: int,
    reason: str
) -> DomainEvent:
    """
    Create an OperationRejected event.
    
    Emitted when an operation is rejected by the DecisionManager.
    
    Args:
        field_id: ID of the field
        date: Date when the operation was rejected
        operation_type: Type/name of the operation
        worktype: Worktype ID of the operation
        reason: Reason for rejection (e.g., 'low_priority', 'weather_constraint')
        
    Returns:
        DomainEvent with type 'OperationRejected'
    """
    return DomainEvent(
        event_id=str(uuid.uuid4()),
        event_type='OperationRejected',
        timestamp=datetime.now(),
        field_id=field_id,
        payload={
            'date': date.isoformat() if isinstance(date, datetime) else str(date),
            'operation_type': operation_type,
            'worktype': worktype,
            'reason': reason
        }
    )


def create_operation_applied(
    field_id: str,
    date: datetime,
    operation_type: str,
    worktype: int,
    integration_event_id: str | None = None
) -> DomainEvent:
    """
    Create an OperationApplied event.
    
    Emitted when an operation has been successfully applied/executed.
    
    Args:
        field_id: ID of the field
        date: Date when the operation was applied
        operation_type: Type/name of the operation
        worktype: Worktype ID of the operation
        integration_event_id: Optional ID of the corresponding integration event
        
    Returns:
        DomainEvent with type 'OperationApplied'
    """
    return DomainEvent(
        event_id=str(uuid.uuid4()),
        event_type='OperationApplied',
        timestamp=datetime.now(),
        field_id=field_id,
        payload={
            'date': date.isoformat() if isinstance(date, datetime) else str(date),
            'operation_type': operation_type,
            'worktype': worktype,
            'integration_event_id': integration_event_id
        }
    )


__all__ = [
    "DomainEvent",
    "create_daily_tick_started",
    "create_daily_tick_completed",
    "create_crop_cycle_scheduled",
    "create_crop_cycle_started",
    "create_harvest_completed",
    "create_operation_considered",
    "create_operation_approved",
    "create_operation_rejected",
    "create_operation_applied",
    "create_protection_operations_pruned",
]


def create_protection_operations_pruned(
    field_id: str,
    date: datetime,
    planned_count: int,
    pruned_count: int,
    pruned_after_harvest: int,
    pruned_sikkation_too_late: int,
) -> DomainEvent:
    """Create a ProtectionOperationsPruned event.

    Emitted once at the end of ProtectionPlanService.plan_protections()
    when one or more protection operations were pruned (not planned) because
    they would have violated KAR-005 or KAR-024.

    Only emitted when pruned_count > 0 (gewaehlter Ansatz, Issue #67).
    """
    return DomainEvent(
        event_id=str(uuid.uuid4()),
        event_type='ProtectionOperationsPruned',
        timestamp=datetime.now(),
        field_id=field_id,
        payload={
            'date': date.isoformat() if isinstance(date, datetime) else str(date),
            'planned_count': planned_count,
            'pruned_count': pruned_count,
            'pruned_after_harvest': pruned_after_harvest,
            'pruned_sikkation_too_late': pruned_sikkation_too_late,
        }
    )
