import datetime
import json
import os

from events.domain_event_bus import DomainEventBus
from models.planting_plan import FieldOperationEvent
from models.sim_context import SimContext
from scheduler.calendar_driven_runner import CalendarDrivenRunner
from utils.event_logger import EventLogger
from utils.logger import get_logger

logger = get_logger("replay_runner")


class ReplayRunner:
    """
    Deterministic replay simulation for past time periods.

    Replays a date range using the same rules as live simulation but without
    real-time delays. Outputs to DigiZert or local JSON export.

    Key features:
    - Deterministic (same seed, same config → same output)
    - Does not interfere with live simulation state
    - Configurable output target (DigiZert / JSON / stdout)

    Usage:
        runner = ReplayRunner(
            context=sim_context,
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 12, 31)
        )
        events = runner.run()
    """

    def __init__(
        self,
        context: SimContext,
        start_date: datetime.date,
        end_date: datetime.date,
        output_target: str = "json",
        output_path: str | None = None,
        event_bus: DomainEventBus | None = None,
    ) -> None:
        """
        Initialize replay runner.

        Args:
            context: Simulation context with field configuration
            start_date: Start date of replay period
            end_date: End date of replay period (inclusive)
            output_target: Output target ("json", "digizert", "stdout")
            output_path: Optional custom output path for JSON export
            event_bus: Optional event bus for domain events
        """
        self.context = context
        self.start_date = start_date
        self.end_date = end_date
        self.output_target = output_target
        self.output_path = output_path
        self.event_bus = event_bus if event_bus is not None else DomainEventBus()

        # Create calendar-driven runner with modified context
        replay_context = self._create_replay_context()
        self.calendar_runner = CalendarDrivenRunner(
            context=replay_context, event_bus=self.event_bus
        )

        self.all_events: list[FieldOperationEvent] = []
        self.all_domain_events = []

    def _create_replay_context(self) -> SimContext:
        """
        Create a modified context for replay with start_date set to replay start.
        """
        import copy

        replay_context = copy.deepcopy(self.context)
        replay_context.start_date = datetime.datetime.combine(self.start_date, datetime.time())
        return replay_context

    def run(self) -> list[FieldOperationEvent]:
        """
        Execute replay simulation for the configured date range.

        Returns:
            List of all FieldOperationEvents generated during replay
        """
        logger.info(
            "Starting replay simulation",
            field_id=self.context.field_id,
            start_date=self.start_date,
            end_date=self.end_date,
        )

        current_date = self.start_date
        tick_count = 0

        while current_date <= self.end_date:
            # Execute one tick
            events = self.calendar_runner.tick(current_date)
            self.all_events.extend(events)

            tick_count += 1
            current_date += datetime.timedelta(days=1)

        # Collect domain events from event bus
        if self.event_bus is not None:
            self.all_domain_events = self.event_bus.get_history()

        logger.info(
            "Replay simulation completed",
            field_id=self.context.field_id,
            ticks=tick_count,
            integration_events=len(self.all_events),
            domain_events=len(self.all_domain_events),
        )

        # Output results
        self._output_results()

        return self.all_events

    def _output_results(self) -> None:
        """
        Output replay results to configured target.
        """
        if self.output_target == "json":
            self._export_to_json()
        elif self.output_target == "stdout":
            self._print_summary()
        elif self.output_target == "digizert":
            self._dispatch_to_digizert()
        else:
            logger.warning(f"Unknown output target: {self.output_target}")

    def _export_to_json(self) -> None:
        """
        Export replay results to JSON file.
        """
        if self.output_path:
            filepath = self.output_path
        else:
            # Default export path
            export_dir = os.path.join(os.path.dirname(__file__), "../export/replay")
            os.makedirs(export_dir, exist_ok=True)

            filename = (
                f"replay_{self.context.field_id}_"
                f"{self.start_date.isoformat()}_to_{self.end_date.isoformat()}.json"
            )
            filepath = os.path.join(export_dir, filename)

        # Use EventLogger for consistent format
        event_logger = EventLogger()
        for event in self.all_events:
            event_logger.log(event)

        event_logger.save(filepath, context=self.context)

        # Also export domain events
        domain_events_path = filepath.replace(".json", "_domain_events.json")
        self._export_domain_events(domain_events_path)

        logger.info(
            "Replay results exported to JSON",
            integration_events_path=filepath,
            domain_events_path=domain_events_path,
        )

    def _export_domain_events(self, filepath: str) -> None:
        """
        Export domain events to separate JSON file.
        """
        domain_events_data = []
        for event in self.all_domain_events:
            domain_events_data.append(
                {
                    "event_type": event.event_type,
                    "timestamp": event.timestamp.isoformat(),
                    "field_id": event.field_id,
                    "payload": event.payload,
                }
            )

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(domain_events_data, f, ensure_ascii=False, indent=2)

    def _print_summary(self) -> None:
        """
        Print replay summary to stdout.
        """
        print("\n" + "=" * 60)
        print("REPLAY SIMULATION SUMMARY")
        print("=" * 60)
        print(f"Field ID: {self.context.field_id}")
        print(f"Field Name: {self.context.field_name}")
        print(f"Period: {self.start_date} to {self.end_date}")
        print(f"Total Days: {(self.end_date - self.start_date).days + 1}")
        print(f"Integration Events: {len(self.all_events)}")
        print(f"Domain Events: {len(self.all_domain_events)}")
        print("=" * 60)

        # Event type breakdown
        event_types = {}
        for event in self.all_events:
            worktype_text = event.worktype_text or f"Worktype {event.worktype}"
            event_types[worktype_text] = event_types.get(worktype_text, 0) + 1

        print("\nEvent Types:")
        for event_type, count in sorted(event_types.items()):
            print(f"  {event_type}: {count}")
        print("=" * 60 + "\n")

    def _dispatch_to_digizert(self) -> None:
        """
        Dispatch replay results to DigiZert.

        This is a placeholder for future DigiZert integration.
        """
        logger.warning("DigiZert dispatch not yet implemented")
        print("DigiZert dispatch not yet implemented. Use 'json' output target instead.")
