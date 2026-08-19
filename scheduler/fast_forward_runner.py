import datetime
import os
from typing import List, Optional

from models.sim_context import SimContext
from models.planting_plan import FieldOperationEvent
from scheduler.calendar_driven_runner import CalendarDrivenRunner, MoistureServiceFactory, WeatherServiceFactory
from events.domain_event_bus import DomainEventBus
from utils.event_logger import EventLogger
from utils.logger import get_logger

logger = get_logger("fast_forward_runner")


class FastForwardRunner:
    """
    Fast-forward simulation for multiple days or full seasons.
    
    Runs N days of simulation as fast as possible without real-time delay,
    producing a complete event history. Useful for demo preparation, data
    generation, and testing seasonal scenarios.
    
    Key features:
    - No inter-tick sleep (decoupled from wall-clock time)
    - Memory-efficient event streaming/flushing
    - Batch output to DigiZert or JSON
    - Progress reporting
    
    Usage:
        runner = FastForwardRunner(
            context=sim_context,
            n_days=365
        )
        events = runner.run()
    """
    
    def __init__(
        self,
        context: SimContext,
        n_days: int = 365,
        output_target: str = "json",
        output_path: Optional[str] = None,
        event_bus: Optional[DomainEventBus] = None,
        flush_interval: int = 30,
        moisture_service_factory: Optional[MoistureServiceFactory] = None,
        weather_service_factory: Optional[WeatherServiceFactory] = None
    ) -> None:
        """
        Initialize fast-forward runner.

        Args:
            context: Simulation context with field configuration
            n_days: Number of days to simulate
            output_target: Output target ("json", "digizert", "stdout")
            output_path: Optional custom output path for JSON export
            event_bus: Optional event bus for domain events
            flush_interval: Flush events to disk every N days (memory management)
            moisture_service_factory: Optional factory for the moisture service
                (P2-5 C, Issue #71). Falls gesetzt, wird sie an den
                ``CalendarDrivenRunner`` durchgereicht und dort statt der
                Hart-Instanziierung verwendet. Ohne Factory verhält sich der
                Runner unverändert (Abwärtskompatibilität).
            weather_service_factory: Optional factory for the weather service
                (P3-1, Issue #79). Analog moisture_service_factory: wird an
                den ``CalendarDrivenRunner`` durchgereicht.
        """
        self.context = context
        self.n_days = n_days
        self.output_target = output_target
        self.output_path = output_path
        self.event_bus = event_bus if event_bus is not None else DomainEventBus()
        self.flush_interval = flush_interval

        self.calendar_runner = CalendarDrivenRunner(
            context=self.context,
            event_bus=self.event_bus,
            moisture_service_factory=moisture_service_factory,
            weather_service_factory=weather_service_factory
        )
        
        self.all_events: List[FieldOperationEvent] = []
        self.event_logger = EventLogger()
        self.tick_count = 0
        self.error_count = 0
    
    def run(self) -> List[FieldOperationEvent]:
        """
        Execute fast-forward simulation for N days.
        
        Returns:
            List of all FieldOperationEvents generated
        """
        logger.info(
            "Starting fast-forward simulation",
            field_id=self.context.field_id,
            n_days=self.n_days,
            start_date=self.context.start_date
        )
        
        print(f"\nFast-forward simulation: {self.n_days} days")
        print(f"Field: {self.context.field_name} (ID: {self.context.field_id})")
        print(f"Start date: {self.context.start_date.date()}")
        print("-" * 60)
        
        current_date = self.context.start_date
        
        for day in range(self.n_days):
            try:
                # Execute one tick
                events = self.calendar_runner.tick(current_date)
                self.all_events.extend(events)
                
                # Log events
                for event in events:
                    self.event_logger.log(event)
                
                self.tick_count += 1
                
                # Progress reporting every 30 days
                if (day + 1) % 30 == 0:
                    self._print_progress(day + 1)
                
                # Memory management: flush events periodically
                if (day + 1) % self.flush_interval == 0:
                    self._flush_events_if_needed()
                
            except Exception as e:
                self.error_count += 1
                logger.error(
                    "Error during fast-forward tick",
                    day=day,
                    date=current_date,
                    error=str(e)
                )
            
            current_date += datetime.timedelta(days=1)
        
        logger.info(
            "Fast-forward simulation completed",
            field_id=self.context.field_id,
            ticks=self.tick_count,
            events=len(self.all_events),
            errors=self.error_count
        )
        
        # Final output
        self._output_results()
        
        return self.all_events
    
    def _print_progress(self, day: int) -> None:
        """
        Print progress update.
        """
        progress_pct = (day / self.n_days) * 100
        print(
            f"Day {day}/{self.n_days} ({progress_pct:.1f}%) - "
            f"Events: {len(self.all_events)}, Errors: {self.error_count}"
        )
    
    def _flush_events_if_needed(self) -> None:
        """
        Flush events to disk if memory usage is high.
        
        This prevents memory issues for large N (e.g., multi-year simulations).
        """
        # For now, we keep events in memory
        # Future: implement streaming to disk
        pass
    
    def _output_results(self) -> None:
        """
        Output fast-forward results to configured target.
        """
        print("\n" + "="*60)
        print("FAST-FORWARD SIMULATION COMPLETED")
        print("="*60)
        print(f"Total ticks: {self.tick_count}")
        print(f"Events generated: {len(self.all_events)}")
        print(f"Errors: {self.error_count}")
        print("="*60 + "\n")
        
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
        Export fast-forward results to JSON file.
        """
        if self.output_path:
            filepath = self.output_path
        else:
            # Default export path
            export_dir = os.path.join(
                os.path.dirname(__file__),
                '../export/fast_forward'
            )
            os.makedirs(export_dir, exist_ok=True)
            
            self.context.start_date + datetime.timedelta(days=self.n_days - 1)
            filename = (
                f"fast_forward_{self.context.field_id}_"
                f"{self.n_days}days_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            filepath = os.path.join(export_dir, filename)
        
        self.event_logger.save(filepath, context=self.context)
        
        logger.info(
            "Fast-forward results exported to JSON",
            filepath=filepath,
            events=len(self.all_events)
        )
        print(f"Results exported to: {filepath}")
    
    def _print_summary(self) -> None:
        """
        Print detailed summary to stdout.
        """
        # Event type breakdown
        event_types = {}
        for event in self.all_events:
            worktype_text = event.worktype_text or f"Worktype {event.worktype}"
            event_types[worktype_text] = event_types.get(worktype_text, 0) + 1
        
        print("\nEvent Types:")
        for event_type, count in sorted(event_types.items()):
            print(f"  {event_type}: {count}")
        print("="*60 + "\n")
    
    def _dispatch_to_digizert(self) -> None:
        """
        Dispatch fast-forward results to DigiZert in batch.
        
        This is a placeholder for future DigiZert integration.
        """
        logger.warning("DigiZert batch dispatch not yet implemented")
        print("DigiZert batch dispatch not yet implemented. Use 'json' output target instead.")
