import random
from datetime import datetime, time, timedelta

import models.sim_context as sim_context
from models.domain_events import create_protection_operations_pruned
from models.planting_plan import FieldOperation, FieldOperationEvent, PlantingPlan
from models.worktypes import WorkType
from services.isip_pressure_service import ISIPPressureService
from utils import sim_helper
from utils.logger import get_logger

logger = get_logger("protection_plan_service")

# Sikkationsgaben (Kat. 26) muessen >= 14 Tage vor dem Roden liegen (KAR-020/KAR-024).
SIKKATION_MIN_DAYS_BEFORE_HARVEST = 14  # KAR-020 / KAR-024

# Application-Category fuer Sikkationsgaben (Herbizid, z. B. Quickdown/Shark).
SIKKATION_CATEGORY = 26

# Application-Category fuer Fungizide (DropdownData pk=27).
FUNGIZID_CATEGORY = 27

# Max. Verschiebung einer Fungizid-Spritzung bei ISIP-Druck-Gating (Tage).
# Nach Ablauf: deterministische Ausführung (verhindert dass Spritzungen
# komplett entfallen).
ISIP_MAX_SHIFT_DAYS = 7

# Falls die naechste geplante Fungizid-Maßnahme <= diesem Wert (Tage ab
# aktuellem Tick) anliegt, wird die aktuelle verfallen lassen.
ISIP_SKIP_THRESHOLD_DAYS = 2


class ProtectionPlanService:
    def __init__(
        self,
        context: sim_context.SimContext,
        start_date: datetime,
        planting_plan: PlantingPlan = None,
        harvest_date: datetime | None = None,
        event_bus: object | None = None,
        isip_service: ISIPPressureService | None = None,
    ):
        self.context = context

        self.start_date = start_date  # Anker fuer Protection-Termine (Pflanzdatum, P2-3)
        self.planting_plan = planting_plan
        # Erntetermin = Pflanzdatum + grow_duration (P2-3, Befund B6). None
        # deaktiviert die Beschneidung (Abwaertskompatibilitaet).
        self.harvest_date = harvest_date
        self.event_bus = event_bus
        self.isip_service = isip_service  # P4: ISIP-Druck-Gating (optional)

        self.operations = []

        # Intra-Tages-Sequenz-Cursor (Befund B7, Issue #66 / P2-2):
        # Eigener, separater Cursor (kein gemeinsamer Zustand mit
        # PlantingPlanService). Pro Kalendertag wird der zuletzt vergebene
        # Event-Zeitpunkt gespeichert, damit aufeinanderfolgende Einzel-Calls
        # von get_events_for_ops() für dasselbe Datum strikt monoton steigende
        # Zeitstempel erhalten. Der Cursor wirkt NICHT über Tagesgrenzen.
        self._last_assigned_time: dict[datetime.date, datetime] = {}

        self.plan_protections()

    def plan_protections(self):
        """
        Plan the protection operations for the planting plan.

        Protection-Termine werden relativ zum Pflanzdatum (self.start_date)
        geplant. Operationen nach dem Erntetermin (KAR-005) und Sikkationen
        < 14 d vor Ernte (KAR-024) werden verworfen und als Domain Event
        protokolliert.
        """
        if not self.planting_plan or not self.planting_plan.protection_plans:
            print("No protection plans available in the planting plan.")
            return

        # Get protection defaults from planting plan or use fallback values
        protection_defaults = getattr(self.planting_plan, "protection_defaults", {})
        default_duration = protection_defaults.get("duration_per_ha", 0.2)
        default_width = protection_defaults.get("working_width", 18)
        default_fuel = protection_defaults.get("fuel_consumption", 1.0)

        # read categories from config
        protection_categories = sim_helper.get_protection_categories()

        # pick random protection plan
        protection_plan = random.choice(self.planting_plan.protection_plans)
        print(f"Selected protection plan: {protection_plan.name}")

        # Schadensereignis
        target_date_diff = protection_plan.days_to_target
        protection_target_date = self.start_date + timedelta(days=target_date_diff)

        print(f"Planned protection date: {protection_target_date.strftime('%Y-%m-%d')}")

        # Zaehler fuer die Beschneidungs-Protokollierung (P2-3, Befund B6).
        planned_count = 0
        pruned_after_harvest = 0
        pruned_sikkation_too_late = 0

        # erstelle die Schutzoperationen
        for protection in protection_plan.protections:
            protection_operation_date = protection_target_date + timedelta(days=protection.day)

            # P2-3 (Befund B6): Beschneide am Erntetermin (KAR-005).
            # >= (nicht >), da eine Operation am Erntetag selbst nicht mehr
            # ausgefuehrt werden darf.
            if self.harvest_date is not None and protection_operation_date >= self.harvest_date:
                planned_count += 1
                pruned_after_harvest += 1
                print(
                    f"Pruned protection operation (after harvest): "
                    f"{protection.name} on {protection_operation_date.strftime('%Y-%m-%d')}"
                )
                continue

            # Sikkationen (Kat. 26) muessen >= 14 d vor dem Roden liegen (KAR-024).
            if (
                self.harvest_date is not None
                and protection.type == SIKKATION_CATEGORY
                and (self.harvest_date - protection_operation_date).days
                < SIKKATION_MIN_DAYS_BEFORE_HARVEST
            ):
                planned_count += 1
                pruned_sikkation_too_late += 1
                print(
                    f"Pruned sikkation (< {SIKKATION_MIN_DAYS_BEFORE_HARVEST} d before harvest): "
                    f"{protection.name} on {protection_operation_date.strftime('%Y-%m-%d')}"
                )
                continue

            planned_count += 1

            # Calculate the sum if protection.amount contains '+'
            application_amount = sum(float(x) for x in protection.amount.split("+"))

            # get the category from the protection categories
            category_item = next(
                (c for c in protection_categories if c["id"] == protection.type), None
            )
            application_type_text = category_item["category"] if category_item else "unknown"

            spritz_operation = FieldOperation(
                operation="Spritzen",
                worktype=WorkType.SPRITZEN,
                duration_per_ha=default_duration,
                working_width=default_width,
                fuel_consumption=default_fuel,
                planned_date=protection_operation_date,
                application_type=application_type_text,
                application_category=protection.type,
                application_name=f"{protection.name} ({protection.amount})",
                application_amount=application_amount,
                application_unit=9,  # Liter (DataUnit pk=9) – PSM ist flüssig
                # P3-4 (Issue #82): Fälligkeits-Metadaten aus der Konfiguration.
                is_critical=protection.is_critical,
                due_window_days=protection.due_window_days,
            )

            # P3-4 (Issue #82): due_date = planned_date + due_window_days.
            # Wird nur für terminkritische Operationen benötigt, aber
            # einheitlich berechnet (auch nicht-kritische Ops erhalten ein
            # due_date, das von der Strategie jedoch ignoriert wird, da
            # is_critical=False).
            spritz_operation.due_date = protection_operation_date + timedelta(
                days=protection.due_window_days
            )

            self.operations.append(spritz_operation)

        # Beschneidung als fachliches Ereignis protokollieren (Styleguide).
        # Nur emittieren, wenn Operationen verworfen wurden (Issue #67).
        pruned_count = pruned_after_harvest + pruned_sikkation_too_late
        if pruned_count > 0 and self.event_bus is not None:
            self.event_bus.publish(
                create_protection_operations_pruned(
                    field_id=str(self.context.field_id),
                    date=self.start_date,
                    planned_count=planned_count,
                    pruned_count=pruned_count,
                    pruned_after_harvest=pruned_after_harvest,
                    pruned_sikkation_too_late=pruned_sikkation_too_late,
                )
            )

    def get_next_operations(self, date: datetime) -> list[FieldOperation]:
        """
        Get the next operations for the protection plan based on the current date.

        P4 (ISIP-Druck-Gating): Fungizid-Operationen (category=27) werden
        nur ausgefuehrt, wenn ``is_justified_window=true`` fuer den aktuellen
        Tag. Falls nicht justified:

        1. Naechste geplante Fungizid-Maßnahme ≤ +2 Tage entfernt → aktuelle
           verfallen lassen (skip).
        2. Sonst → zurueckstellen (wird naechsten Tick erneut geprueft).
        3. Fallback: geplantes Datum + 7 Tage ueberschritten → deterministisch.

        Herbizide/Insektizide/Sikkationen bleiben deterministisch.

        :param date: The current date in the simulation.
        """
        if not self.operations:
            print("No protection operations planned.")
            return []

        current_date = date.date() if isinstance(date, datetime) else date

        next_operations = []
        for operation in self.operations:
            if operation.planned_date <= date and not operation.actual_date:
                # ISIP-Druck-Gating nur fuer Fungizide
                if (
                    self._is_fungicide(operation)
                    and self.isip_service
                    and self.isip_service.enabled
                ):
                    # Fallback: geplantes Datum + 7 Tage → deterministisch
                    planned_date = (
                        operation.planned_date.date()
                        if isinstance(operation.planned_date, datetime)
                        else operation.planned_date
                    )
                    if planned_date + timedelta(days=ISIP_MAX_SHIFT_DAYS) <= current_date:
                        logger.info(
                            "Fungizid deterministisch (7-Tage-Fallback)",
                            field_id=self.context.field_id,
                            planned=str(planned_date),
                            current=str(current_date),
                        )
                        next_operations.append(operation)
                        continue

                    # ISIP-Check
                    if not self.isip_service.is_justified(current_date):
                        # Nicht justified → pruefe Skip-Bedingung
                        if self._should_skip_fungicide(operation, current_date):
                            operation.actual_date = date  # Skip permanent
                            logger.info(
                                "Fungizid verfallen (naechste ≤ +2 Tage)",
                                field_id=self.context.field_id,
                                planned=str(planned_date),
                                current=str(current_date),
                            )
                            continue
                        else:
                            # Zurueckstellen – naechster Tick versucht es erneut
                            continue

                next_operations.append(operation)

        if not next_operations:
            return []

        return next_operations

    def _is_fungicide(self, operation: FieldOperation) -> bool:
        """Prueft ob eine Operation ein Fungizid ist (category=27)."""
        return operation.application_category == FUNGIZID_CATEGORY

    def _should_skip_fungicide(
        self, current_op: FieldOperation, current_date: datetime.date
    ) -> bool:
        """Prueft ob die naechste Fungizid-Maßnahme ≤ +2 Tage anliegt.

        Falls ja → aktuelle verfallen lassen (skip).
        Falls nein → zurueckstellen (wird naechsten Tick erneut geprueft).
        """
        next_fungicide = self._find_next_fungicide(current_op)
        if next_fungicide is None:
            return False

        next_planned = (
            next_fungicide.planned_date.date()
            if isinstance(next_fungicide.planned_date, datetime)
            else next_fungicide.planned_date
        )
        delta_days = (next_planned - current_date).days
        return delta_days <= ISIP_SKIP_THRESHOLD_DAYS

    def _find_next_fungicide(self, current_op: FieldOperation) -> FieldOperation | None:
        """Findet die naechste geplante Fungizid-Operation nach current_op."""
        found_current = False
        for op in self.operations:
            if op is current_op:
                found_current = True
                continue
            if found_current and self._is_fungicide(op) and not op.actual_date:
                return op
        return None

    def get_events_for_ops(
        self, operations: list[FieldOperation], date: datetime
    ) -> list[FieldOperationEvent]:

        # get active phase
        events = []

        # Intra-Tages-Sequenz-Cursor (Befund B7, Issue #66 / P2-2):
        # date wird vom CalendarDrivenRunner als datetime übergeben; der
        # Cursor-Key ist das Kalenderdatum, damit der Zustand nicht über
        # Tagesgrenzen wirkt.
        date_key = date.date() if isinstance(date, datetime) else date

        for operation in operations:
            # get the variation factor for fuel consumption (individual per operation)
            fuel_variation_factor = random.uniform(
                1 - self.context.fuel_variation, 1 + self.context.fuel_variation
            )
            # Process the operation

            # Update the actual date of the operation
            operation.actual_date = date
            print(f"    {operation.operation}: {operation.actual_date.strftime('%Y-%m-%d')}")

            event = FieldOperationEvent()

            # Sequenzkonforme Uhrzeitvergabe via zustandsbehaftetem Zeit-Cursor
            # (Befund B7, Issue #66 / P2-2): Der Cursor speichert den zuletzt
            # vergebenen Zeitpunkt pro Kalendertag. Bei jedem Call wird die
            # Uhrzeit im Restfenster [cursor, 17:00] gezogen und strikt nach
            # dem Cursor platziert -> Intra-Tages-Sequenz bleibt erhalten.
            # P3-5 (Issue #83): Defaults bleiben auf [06:00, 17:00], um den
            # Zufallszustand nicht zu verschieben (KAR-021).
            last_dt = self._last_assigned_time.get(date_key)
            min_start = last_dt.time() if last_dt is not None else time(6, 0)
            operation.actual_datetime = sim_helper.assign_sequential_time(date, min_start=min_start)
            self._last_assigned_time[date_key] = operation.actual_datetime

            event.start_date = operation.actual_datetime.strftime("%Y-%m-%d %H:%M:%S")
            event.end_date = (
                operation.actual_datetime
                + timedelta(hours=operation.duration_per_ha * self.context.field_size)
            ).strftime("%Y-%m-%d %H:%M:%S")
            event.area = self.context.field_size
            event.fuel = round(self.context.field_size * operation.fuel_consumption, 2)
            event.worktype = operation.worktype
            event.worktype_text = operation.operation
            event.duration = round(
                operation.duration_per_ha * self.context.field_size * 60 * 60, 2
            )  # Umrechnung in Sekunden
            event.durationWorked = round(event.duration * 0.95, 2)
            event.distance = (
                round(self.context.field_size * 10 / operation.working_width, 2)
                if operation.working_width > 0
                else 0
            )
            event.distanceWorked = round(event.distance * 0.95, 2)
            event.application_type = operation.application_type
            event.application_name = operation.application_name
            event.application_category = operation.application_category
            event.application_amount = round(
                operation.application_amount * self.context.field_size, 2
            )
            event.application_unit = operation.application_unit
            event.field = self.context.field_id

            # variations for e.g. fuel consumption (in the range of 0.9 to 1.1 if set to 0.1 --> 10% variation in both directions)
            event.fuel = round(event.fuel * fuel_variation_factor, 2)

            events.append(event)

        return events
