from typing import List, Protocol, Any, Optional
from models.worktypes import LOW_PRIORITY_WORKTYPES
from events.domain_event_bus import DomainEventBus
from models.domain_events import (
    create_operation_considered,
    create_operation_approved,
    create_operation_rejected
)
import datetime

class DecisionStrategy(Protocol):
    """
    Protocol for decision strategies in the unified decision pipeline.
    
    Strategies determine which operations to execute from a list of candidates.
    This enables flexible decision-making logic while maintaining separation of concerns.
    """
    def select_operation(self, operations: List[Any]) -> Any:
        """
        Select which operations to execute from the candidate list.
        
        Args:
            operations: List of candidate operations (FieldOperationEvent or FieldOperation)
            
        Returns:
            Selected operations (list) or None if no operations
        """
        return NotImplemented

class WorkTypePriorityStrategy:
    """
    Priority-based decision strategy for agricultural operations.
    
    This strategy implements a two-tier priority system:
    
    **High-Priority Operations** (executed first):
    - Soil preparation (plowing, harrowing, etc.)
    - Planting operations
    - Fertilization
    - Harvesting
    - All other operations not in LOW_PRIORITY_WORKTYPES
    
    **Low-Priority Operations** (deferred when high-priority ops exist):
    - Irrigation (worktype 15 / BEREGNEN)
    - Plant protection spraying (worktype 14 / SPRITZEN)
    
    **Decision Rules:**
    1. If high-priority operations exist, select ALL high-priority ops and SUPPRESS all low-priority ops
    2. If only low-priority operations exist, select ALL of them
    3. If no operations exist, return None
    
    **Irrigation-Specific Behavior:**
    Irrigation candidates are only executed when no high-priority operations are scheduled.
    This ensures critical operations (planting, harvesting, etc.) are never delayed by irrigation.
    
    **Example Scenarios:**
    - [Planting, Irrigation] → Select: [Planting] (irrigation suppressed)
    - [Irrigation, Spraying] → Select: [Irrigation, Spraying] (both low-priority)
    - [Plowing, Planting, Irrigation] → Select: [Plowing, Planting] (irrigation suppressed)
    - [Irrigation] → Select: [Irrigation] (only operation available)
    
    **Integration with Unified Pipeline:**
    This strategy is used by DecisionManager in CalendarDrivenRunner.tick() to decide
    which operations to execute from the unified candidate list (planting + protection + irrigation).
    
    See Also:
        - models.worktypes.LOW_PRIORITY_WORKTYPES: List of low-priority worktype IDs
        - Issue #40: Integration of irrigation priority logic into DecisionManager
    """
    
    def select_operation(self, operations: List[Any]) -> Any:
        """
        Select operations based on priority rules.
        
        Filters out low-priority operations (irrigation, spraying) when high-priority
        operations are present. If only low-priority operations exist, all are selected.
        
        Args:
            operations: List of candidate operations with 'worktype' attribute
            
        Returns:
            List of selected operations, or None if input is empty
            
        Priority Logic:
            - Filters operations by worktype
            - Low-priority worktypes (14, 15) are suppressed by high-priority ops
            - If all operations are low-priority, all are selected
            
        Note:
            Operations without a 'worktype' attribute are treated as high-priority.
        """
        low_prio_worktypes = LOW_PRIORITY_WORKTYPES

        if not operations:
            return None
        
        # Filter out low-priority operations
        filtered_operations = [op for op in operations if getattr(op, 'worktype', None) not in low_prio_worktypes]
        
        # If no high-priority operations exist, select all (including low-priority)
        if not filtered_operations:
            return operations
        
        # High-priority operations exist - return only those
        return filtered_operations

class DecisionManager:
    def __init__(
        self,
        strategy: DecisionStrategy,
        event_bus: Optional[DomainEventBus] = None
    ):
        self.strategy = strategy
        self.event_bus = event_bus

    def decide(
        self,
        operations: List[Any],
        field_id: str | None = None,
        date: datetime.datetime | None = None
    ) -> Any:
        """
        Decide which operations to execute from the candidate list.
        
        Emits domain events for each operation:
        - OperationConsidered for each candidate
        - OperationApproved for selected operations
        - OperationRejected for rejected operations (with reason)
        
        Args:
            operations: List of candidate operations
            field_id: Optional field ID for domain events
            date: Optional date for domain events
            
        Returns:
            List of selected operations or None
        """
        if not operations:
            return None
        
        # Emit OperationConsidered events for all candidates
        if self.event_bus is not None and field_id and date:
            for op in operations:
                operation_type = getattr(op, 'operation', None) or getattr(op, 'worktype_text', 'Unknown')
                worktype = getattr(op, 'worktype', 0)
                
                self.event_bus.publish(
                    create_operation_considered(
                        field_id=field_id,
                        date=date,
                        operation_type=operation_type,
                        worktype=worktype
                    )
                )
        
        # Apply strategy to select operations
        selected = self.strategy.select_operation(operations)
        
        # Emit OperationApproved and OperationRejected events
        if self.event_bus is not None and field_id and date:
            selected_list = selected if selected else []
            
            for op in operations:
                operation_type = getattr(op, 'operation', None) or getattr(op, 'worktype_text', 'Unknown')
                worktype = getattr(op, 'worktype', 0)
                
                if op in selected_list:
                    self.event_bus.publish(
                        create_operation_approved(
                            field_id=field_id,
                            date=date,
                            operation_type=operation_type,
                            worktype=worktype
                        )
                    )
                else:
                    # Determine rejection reason
                    reason = self._get_rejection_reason(op, selected)
                    
                    self.event_bus.publish(
                        create_operation_rejected(
                            field_id=field_id,
                            date=date,
                            operation_type=operation_type,
                            worktype=worktype,
                            reason=reason
                        )
                    )
        
        return selected
    
    def _get_rejection_reason(self, operation: Any, selected_ops: List[Any]) -> str:
        """
        Determine why an operation was rejected.
        
        Args:
            operation: The rejected operation
            selected_ops: List of selected operations
            
        Returns:
            Reason string for rejection
        """
        worktype = getattr(operation, 'worktype', None)
        
        # Check if rejected due to low priority
        if worktype in LOW_PRIORITY_WORKTYPES:
            if selected_ops:  # If high-priority ops were selected
                return 'low_priority'
        
        return 'strategy_decision'
