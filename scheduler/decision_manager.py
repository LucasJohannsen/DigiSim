from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol, Any, Optional, runtime_checkable
from models.worktypes import LOW_PRIORITY_WORKTYPES
from events.domain_event_bus import DomainEventBus
from models.domain_events import (
    create_operation_considered,
    create_operation_approved,
    create_operation_rejected
)
from services.weather_service import WeatherData
import datetime

__all__ = [
    "CycleContext",
    "DecisionStrategy",
    "WorkTypePriorityStrategy",
    "DecisionManager",
    "RuleGuard",
    "GuardRule",
    "NoWorktypeAfterHarvestRule",
    "MinGapBeforeHarvestOpRule",
    "NoSiccationAfterHarvestRule",
]


# ---------------------------------------------------------------------------
# CycleContext (MS5 P2-4, Issue #68)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CycleContext:
    """Zyklus-Kontext für die Guard-Prüfung im DecisionManager.

    Enthält schreibgeschützt die Zyklus-Informationen, die der Guard
    benötigt. Wird von ``CalendarDrivenRunner._build_cycle_context()``
    aus den Services aufgebaut. Der Guard bekommt **nur** diesen
    Kontext, nicht die Services selbst (Event-Driven-Core, keine
    direkten Service-Abhängigkeiten im Guard).

    Attributes:
        planting_date: Geplantes Pflanzdatum des Zyklus.
        harvest_date: Erntetermin (Pflanzdatum + grow_duration).
        harvest_completed: True, wenn die Ernte im Zyklus abgeschlossen ist.
        last_siccation_date: Datum der letzten Sikkation (Kat. 26) im Zyklus.
        siccation_count_this_cycle: Anzahl Sikkationsgaben im Zyklus.
        last_harvest_op_date: Datum der letzten ausgeführten Ernte-Operation.
        current_weather: Aktuelle Wetterdaten für den Tick (P3-1, Issue #79).
            None, wenn kein WeatherService aktiv ist (Abwärtskompatibilität).
        weather_forecast: Wetterprognose ab dem Tick (P3-1, Issue #79).
            None, wenn kein WeatherService aktiv ist.
    """

    planting_date: datetime.datetime | None = None
    harvest_date: datetime.datetime | None = None
    harvest_completed: bool = False
    last_siccation_date: datetime.datetime | None = None
    siccation_count_this_cycle: int = 0
    last_harvest_op_date: datetime.datetime | None = None
    current_weather: WeatherData | None = None
    weather_forecast: list[WeatherData] | None = None


# ---------------------------------------------------------------------------
# Guard-Regeln (MS5 P2-4, Issue #68)
# ---------------------------------------------------------------------------


@runtime_checkable
class GuardRule(Protocol):
    """Protocol für eine einzelne Guard-Regel (datengetrieben)."""

    rule_id: str
    description: str

    def check(
        self,
        operation: Any,
        cycle_context: CycleContext | None,
        date: datetime.datetime,
    ) -> str | None:
        """Prüft eine Operation gegen die Regel.

        Returns:
            Regel-ID + Begründung bei Verstoß (z. B. ``"KAR-005: ..."``),
            ``None`` wenn die Operation in Ordnung ist.
        """
        ...


class NoWorktypeAfterHarvestRule:
    """KAR-005: Keine Bestandesmaßnahme nach Roden (harvest_completed=True).

    Lehnt alle ``worktypes`` ab, wenn ``cycle_context.harvest_completed``
    True ist. Datengetrieben aus ``config/decision_guards_potato.json``.
    """

    def __init__(self, rule_id: str, description: str, worktypes: list[int]) -> None:
        self.rule_id = rule_id
        self.description = description
        self.worktypes = worktypes

    @classmethod
    def from_config(cls, entry: dict[str, Any]) -> "NoWorktypeAfterHarvestRule":
        return cls(
            rule_id=entry["rule_id"],
            description=entry["description"],
            worktypes=list(entry["worktypes"]),
        )

    def check(
        self,
        operation: Any,
        cycle_context: CycleContext | None,
        date: datetime.datetime,
    ) -> str | None:
        if cycle_context is None or not cycle_context.harvest_completed:
            return None
        wt = getattr(operation, "worktype", None)
        if wt in self.worktypes:
            return f"{self.rule_id}: {self.description}"
        return None


class MinGapBeforeHarvestOpRule:
    """KAR-020: Sikkation → Roden ≥ 14 Tage Wartezeit.

    Lehnt ``to_worktype`` (Roden, wt=27) ab, wenn
    ``cycle_context.last_siccation_date`` gesetzt ist und
    ``date − last_siccation_date < min_days``.
    """

    def __init__(
        self, rule_id: str, description: str, to_worktype: int, min_days: int
    ) -> None:
        self.rule_id = rule_id
        self.description = description
        self.to_worktype = to_worktype
        self.min_days = min_days

    @classmethod
    def from_config(cls, entry: dict[str, Any]) -> "MinGapBeforeHarvestOpRule":
        return cls(
            rule_id=entry["rule_id"],
            description=entry["description"],
            to_worktype=entry["to_worktype"],
            min_days=entry["min_days"],
        )

    def check(
        self,
        operation: Any,
        cycle_context: CycleContext | None,
        date: datetime.datetime,
    ) -> str | None:
        if cycle_context is None or cycle_context.last_siccation_date is None:
            return None
        wt = getattr(operation, "worktype", None)
        if wt != self.to_worktype:
            return None
        delta = (date - cycle_context.last_siccation_date).days
        if delta < self.min_days:
            return f"{self.rule_id}: {self.description}"
        return None


class NoSiccationAfterHarvestRule:
    """KAR-024: Keine Sikkation (wt=14, Kat. 26) nach Roden.

    Lehnt ``worktype`` mit ``application_category`` ab, wenn
    ``cycle_context.harvest_completed`` True ist.
    """

    def __init__(
        self,
        rule_id: str,
        description: str,
        worktype: int,
        application_category: int,
    ) -> None:
        self.rule_id = rule_id
        self.description = description
        self.worktype = worktype
        self.application_category = application_category

    @classmethod
    def from_config(cls, entry: dict[str, Any]) -> "NoSiccationAfterHarvestRule":
        return cls(
            rule_id=entry["rule_id"],
            description=entry["description"],
            worktype=entry["worktype"],
            application_category=entry["application_category"],
        )

    def check(
        self,
        operation: Any,
        cycle_context: CycleContext | None,
        date: datetime.datetime,
    ) -> str | None:
        if cycle_context is None or not cycle_context.harvest_completed:
            return None
        wt = getattr(operation, "worktype", None)
        if wt != self.worktype:
            return None
        cat = getattr(operation, "application_category", None)
        if cat == self.application_category:
            return f"{self.rule_id}: {self.description}"
        return None


class RuleGuard:
    """Sammelt Guard-Regeln und prüft Operationen gegen alle Regeln.

    Der Guard ist ein Sicherheitsnetz: er lehnt nur ab, wenn eine Regel
    einen Verstoß meldet. Bei ``cycle_context=None`` ist der Guard
    deaktiviert (Abwärtskompatibilität).
    """

    def __init__(self, rules: list[GuardRule]) -> None:
        self.rules = rules

    def check(
        self,
        operation: Any,
        cycle_context: CycleContext | None,
        date: datetime.datetime,
    ) -> str | None:
        """Prüft die Operation gegen alle Guard-Regeln.

        Returns:
            Regel-ID + Begründung beim ersten Verstoß, ``None`` sonst.
        """
        if cycle_context is None:
            return None
        for rule in self.rules:
            reason = rule.check(operation, cycle_context, date)
            if reason is not None:
                return reason
        return None

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
        event_bus: Optional[DomainEventBus] = None,
        rule_guard: Optional[RuleGuard] = None
    ):
        self.strategy = strategy
        self.event_bus = event_bus
        self.rule_guard = rule_guard

    def decide(
        self,
        operations: List[Any],
        field_id: str | None = None,
        date: datetime.datetime | None = None,
        cycle_context: CycleContext | None = None
    ) -> Any:
        """
        Decide which operations to execute from the candidate list.
        
        Emits domain events for each operation:
        - OperationConsidered for each candidate
        - OperationApproved for selected operations
        - OperationRejected for rejected operations (with reason)
        
        Guard-Schicht (P2-4, Issue #68): Nach der Strategie-Auswahl werden
        selektierte Kandidaten, die gegen eine Guard-Regel verstoßen,
        entfernt und als OperationRejected mit Regel-ID markiert.
        Bei ``cycle_context=None`` ist der Guard deaktiviert (Abwärts-
        kompatibilität, keine Regression).
        
        Args:
            operations: List of candidate operations
            field_id: Optional field ID for domain events
            date: Optional date for domain events
            cycle_context: Optional cycle context for guard checks
            
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
        selected_list = list(selected) if selected else []
        
        # Apply guard filter on selected candidates (P2-4, Issue #68).
        # Guard deaktiviert bei cycle_context=None oder rule_guard=None.
        guard_rejected: list[tuple[Any, str]] = []
        if self.rule_guard is not None and cycle_context is not None and date is not None:
            filtered: list[Any] = []
            for op in selected_list:
                reason = self.rule_guard.check(op, cycle_context, date)
                if reason is not None:
                    guard_rejected.append((op, reason))
                else:
                    filtered.append(op)
            selected_list = filtered
        
        # Emit OperationApproved and OperationRejected events
        if self.event_bus is not None and field_id and date:
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
                    # Check if rejected by guard (rule-id reason takes priority)
                    guard_reason = next(
                        (r for o, r in guard_rejected if o == op), None
                    )
                    if guard_reason is not None:
                        reason = guard_reason
                    else:
                        reason = self._get_rejection_reason(op, selected_list)
                    
                    self.event_bus.publish(
                        create_operation_rejected(
                            field_id=field_id,
                            date=date,
                            operation_type=operation_type,
                            worktype=worktype,
                            reason=reason
                        )
                    )
        
        return selected_list if selected_list else None
    
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
