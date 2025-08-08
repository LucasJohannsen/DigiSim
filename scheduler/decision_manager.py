from typing import List, Protocol, Any

class DecisionStrategy(Protocol):
    def select_operation(self, operations: List[Any]) -> Any:
        return NotImplemented

class WorkTypePriorityStrategy:
    def select_operation(self, operations: List[Any]) -> Any:
        low_prio_worktypes = [14, 15]  # Example low priority work types (Spritzen, Bewässern)

        if not operations:
            return None
        
        # return all that are not in low_prio_worktypes
        filtered_operations = [op for op in operations if getattr(op, 'worktype', None) not in low_prio_worktypes]
        if not filtered_operations:
            return operations
        
        return filtered_operations

class DecisionManager:
    def __init__(self, strategy: DecisionStrategy):
        self.strategy = strategy

    def decide(self, operations: List[Any]) -> Any:
        return self.strategy.select_operation(operations)
