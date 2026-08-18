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
    "DeadlineAwarePriorityStrategy",
    "DecisionManager",
    "RuleGuard",
    "GuardRule",
    "NoWorktypeAfterHarvestRule",
    "MinGapBeforeHarvestOpRule",
    "NoSiccationAfterHarvestRule",
    "WeatherConditionGuard",
    "SoilConditionGuard",
    "ForecastConditionGuard",
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


# ---------------------------------------------------------------------------
# Wetter-Guard-Regeln (MS6 P3-2, Issue #80)
# ---------------------------------------------------------------------------


class WeatherConditionGuard:
    """KAR-030 / KAR-035: Wetterbedingungen für Spritzoperationen.

    Prüft Niederschlag, Wind und (optional) Temperatur für einen
    konkreten ``worktype``. Über ``application_category`` kann die Prüfung
    auf eine Teilmenge der Operationen eingeschränkt werden (z. B. nur
    Sikkation, Kat. 26).

    Deaktiviert (``check`` → None), wenn ``cycle_context`` None oder
    ``current_weather`` None ist (Abwärtskompatibilität ohne P3-1).
    """

    def __init__(
        self,
        rule_id: str,
        description: str,
        worktype: int,
        application_category: int | None = None,
        max_precipitation_mm_day: float = 5.0,
        max_wind_ms: float = 5.0,
        max_temperature_c: float | None = None,
    ) -> None:
        self.rule_id = rule_id
        self.description = description
        self.worktype = worktype
        self.application_category = application_category
        self.max_precipitation_mm_day = max_precipitation_mm_day
        self.max_wind_ms = max_wind_ms
        self.max_temperature_c = max_temperature_c

    @classmethod
    def from_config(cls, entry: dict[str, Any]) -> "WeatherConditionGuard":
        return cls(
            rule_id=entry["rule_id"],
            description=entry["description"],
            worktype=entry["worktype"],
            application_category=entry.get("application_category"),
            max_precipitation_mm_day=float(
                entry.get("max_precipitation_mm_day", 5.0)
            ),
            max_wind_ms=float(entry.get("max_wind_ms", 5.0)),
            max_temperature_c=(
                float(entry["max_temperature_c"])
                if entry.get("max_temperature_c") is not None
                else None
            ),
        )

    def check(
        self,
        operation: Any,
        cycle_context: CycleContext | None,
        date: datetime.datetime,
    ) -> str | None:
        if cycle_context is None or cycle_context.current_weather is None:
            return None  # Guard deaktiviert ohne Wetterdaten

        wt = getattr(operation, "worktype", None)
        if wt != self.worktype:
            return None

        if self.application_category is not None:
            cat = getattr(operation, "application_category", None)
            if cat != self.application_category:
                return None

        weather = cycle_context.current_weather

        if weather.precipitation_mm > self.max_precipitation_mm_day:
            return (
                f"{self.rule_id}: {self.description} "
                f"(Niederschlag {weather.precipitation_mm} mm > "
                f"{self.max_precipitation_mm_day} mm)"
            )

        if weather.wind_speed_ms > self.max_wind_ms:
            return (
                f"{self.rule_id}: {self.description} "
                f"(Wind {weather.wind_speed_ms} m/s > "
                f"{self.max_wind_ms} m/s)"
            )

        if (
            self.max_temperature_c is not None
            and weather.temperature_max_c > self.max_temperature_c
        ):
            return (
                f"{self.rule_id}: {self.description} "
                f"(Temperatur {weather.temperature_max_c}°C > "
                f"{self.max_temperature_c}°C)"
            )

        return None


class SoilConditionGuard:
    """KAR-032: Bodenfeuchte-/Niederschlag-Guard für Bodenbearbeitung.

    Lehnt Bodenbearbeitung (``worktypes``) ab, wenn die Bodenfeuchte
    > ``max_soil_moisture_pct_nfk`` oder der Tagesniederschlag
    > ``max_previous_day_precipitation_mm`` ist.

    .. note::
        **Vereinfachung (MVP):** ``WeatherData`` enthält nur den aktuellen
        Tag, keine History. Daher wird ``current_weather.precipitation_mm``
        als Näherung für den Vortagesniederschlag verwendet. Eine echte
        Vortages-Prüfung benötigt eine WeatherService-History und ist ein
        Folge-Issue.

    Deaktiviert (``check`` → None), wenn ``cycle_context`` None oder
    ``current_weather`` None ist.
    """

    def __init__(
        self,
        rule_id: str,
        description: str,
        worktypes: list[int],
        max_soil_moisture_pct_nfk: float = 90.0,
        max_previous_day_precipitation_mm: float = 10.0,
    ) -> None:
        self.rule_id = rule_id
        self.description = description
        self.worktypes = worktypes
        self.max_soil_moisture_pct_nfk = max_soil_moisture_pct_nfk
        self.max_previous_day_precipitation_mm = (
            max_previous_day_precipitation_mm
        )

    @classmethod
    def from_config(cls, entry: dict[str, Any]) -> "SoilConditionGuard":
        return cls(
            rule_id=entry["rule_id"],
            description=entry["description"],
            worktypes=list(entry["worktypes"]),
            max_soil_moisture_pct_nfk=float(
                entry.get("max_soil_moisture_pct_nfk", 90.0)
            ),
            max_previous_day_precipitation_mm=float(
                entry.get("max_previous_day_precipitation_mm", 10.0)
            ),
        )

    def check(
        self,
        operation: Any,
        cycle_context: CycleContext | None,
        date: datetime.datetime,
    ) -> str | None:
        if cycle_context is None or cycle_context.current_weather is None:
            return None

        wt = getattr(operation, "worktype", None)
        if wt not in self.worktypes:
            return None

        weather = cycle_context.current_weather

        if weather.soil_moisture_pct_nfk > self.max_soil_moisture_pct_nfk:
            return (
                f"{self.rule_id}: {self.description} "
                f"(Bodenfeuchte {weather.soil_moisture_pct_nfk}% nFK > "
                f"{self.max_soil_moisture_pct_nfk}% nFK)"
            )

        # MVP-Vereinfachung: Tagesniederschlag als Näherung für
        # Vortagesniederschlag (keine History verfügbar).
        if weather.precipitation_mm > self.max_previous_day_precipitation_mm:
            return (
                f"{self.rule_id}: {self.description} "
                f"(Niederschlag {weather.precipitation_mm} mm > "
                f"{self.max_previous_day_precipitation_mm} mm)"
            )

        return None


class ForecastConditionGuard:
    """KAR-031: Prognose-Guard für Beregnung.

    Lehnt Beregnung (``worktype``) ab, wenn der kumulative
    Prognose-Niederschlag über ``forecast_days`` Tage
    > ``max_cumulative_precipitation_mm`` ist.

    Deaktiviert (``check`` → None), wenn ``cycle_context`` None oder
    ``weather_forecast`` None ist.
    """

    def __init__(
        self,
        rule_id: str,
        description: str,
        worktype: int,
        forecast_days: int = 4,
        max_cumulative_precipitation_mm: float = 10.0,
    ) -> None:
        self.rule_id = rule_id
        self.description = description
        self.worktype = worktype
        self.forecast_days = forecast_days
        self.max_cumulative_precipitation_mm = max_cumulative_precipitation_mm

    @classmethod
    def from_config(cls, entry: dict[str, Any]) -> "ForecastConditionGuard":
        return cls(
            rule_id=entry["rule_id"],
            description=entry["description"],
            worktype=entry["worktype"],
            forecast_days=int(entry.get("forecast_days", 4)),
            max_cumulative_precipitation_mm=float(
                entry.get("max_cumulative_precipitation_mm", 10.0)
            ),
        )

    def check(
        self,
        operation: Any,
        cycle_context: CycleContext | None,
        date: datetime.datetime,
    ) -> str | None:
        if cycle_context is None or cycle_context.weather_forecast is None:
            return None

        wt = getattr(operation, "worktype", None)
        if wt != self.worktype:
            return None

        forecast = cycle_context.weather_forecast[: self.forecast_days]
        cumulative_precip = sum(
            day.precipitation_mm for day in forecast
        )

        if cumulative_precip > self.max_cumulative_precipitation_mm:
            return (
                f"{self.rule_id}: {self.description} "
                f"(Prognose-Niederschlag {cumulative_precip} mm > "
                f"{self.max_cumulative_precipitation_mm} mm)"
            )

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


class DeadlineAwarePriorityStrategy:
    """Prioritätsstrategie mit Fälligkeitsberücksichtigung (P3-4, Issue #82).

    Erweitert ``WorkTypePriorityStrategy`` um Fälligkeitslogik für
    terminkritische Operationen (``is_critical=True``). Überfällige
    kritische Operationen werden auch bei High-Prio-Konkurrenz
    ausgeführt, um die Wirksamkeit von Fungizid-Spritzfolgen zu
    sichern (KAR-021: Fungizidabstände ≥ 3 Tage, üblich 5–14 Tage).

    **Drei Kategorien:**

    1. **Überfällig kritisch** (``is_critical=True``, ``due_date`` gesetzt,
       ``planned_date > due_date``): Werden **immer** ausgeführt, auch bei
       High-Prio-Konkurrenz. Zusätzlich werden High-Prio-Ops ausgeführt,
       aber Low-Prio-Ops unterdrückt (um Stauung zu vermeiden).
    2. **Im-Fenster kritisch** (``is_critical=True``, ``due_date`` gesetzt,
       ``planned_date <= due_date``): Werden wie High-Prio behandelt –
       zusammen mit High-Prio-Ops ausgeführt, Low-Prio unterdrückt.
    3. **Andere** (nicht kritisch oder ohne ``due_date``): Standard-Logik
       wie ``WorkTypePriorityStrategy`` (Low-Prio bei High-Prio-Konkurrenz
       unterdrückt).

    **Aktuelles Datum:** Die Strategie kennt das Simulationsdatum nicht
    direkt. ``op.planned_date`` wird vom Runner auf den aktuellen Tick
    gesetzt und als Referenz für "heute" verwendet. Ist ``planned_date``
    None, wird die Operation als nicht-überfällig behandelt.
    """

    def select_operation(self, operations: List[Any]) -> Any:
        """Wählt Operationen nach Fälligkeits- und Prioritätslogik aus.

        Args:
            operations: Liste von Kandidaten-Operationen mit ``worktype``,
                optional ``is_critical``, ``due_date`` und ``planned_date``.

        Returns:
            Liste der ausgewählten Operationen, oder ``None`` bei leerer
            Eingabe.
        """
        if not operations:
            return None

        # Trenne in kritisch-überfällig, kritisch-im-Fenster, andere.
        overdue_critical: list[Any] = []
        in_window_critical: list[Any] = []
        others: list[Any] = []

        for op in operations:
            is_critical = getattr(op, "is_critical", False)
            due_date = getattr(op, "due_date", None)

            if is_critical and due_date is not None:
                # planned_date wird vom Runner auf den aktuellen Tick
                # gesetzt → Referenz für "heute". Ist planned_date None,
                # wird die Op als nicht-überfällig behandelt (Fallback).
                today = getattr(op, "planned_date", None)
                if today is not None and today > due_date:
                    overdue_critical.append(op)
                else:
                    in_window_critical.append(op)
            else:
                others.append(op)

        # Priorität: überfällig kritisch > im Fenster kritisch + high-prio
        # > low-prio.
        if overdue_critical:
            # Überfällige kritische Ops werden IMMER ausgeführt (auch bei
            # High-Prio-Konkurrenz). Plus alle High-Prio-Ops, aber nicht
            # Low-Prio (um Stauung zu vermeiden).
            high_prio = [
                op for op in others
                if getattr(op, "worktype", None) not in LOW_PRIORITY_WORKTYPES
            ]
            return overdue_critical + high_prio

        # Keine überfälligen kritischen → Standard-Logik mit
        # Im-Fenster-kritischen als High-Prio-Äquivalent.
        high_prio = [
            op for op in others
            if getattr(op, "worktype", None) not in LOW_PRIORITY_WORKTYPES
        ]
        low_prio = [
            op for op in others
            if getattr(op, "worktype", None) in LOW_PRIORITY_WORKTYPES
        ]

        if high_prio or in_window_critical:
            # High-Prio + im-Fenster-kritische ausführen, Low-Prio
            # unterdrücken.
            return in_window_critical + high_prio

        # Nur Low-Prio → alle ausführen.
        return low_prio


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
