from typing import List, Protocol, Any
from models.worktypes import LOW_PRIORITY_WORKTYPES

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
    def __init__(self, strategy: DecisionStrategy):
        self.strategy = strategy

    def decide(self, operations: List[Any]) -> Any:
        return self.strategy.select_operation(operations)
