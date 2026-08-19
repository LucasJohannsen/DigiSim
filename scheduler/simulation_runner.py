import datetime
import os
from typing import Any

import simpy

import models.sim_context as sim_context
import utils.sim_helper as sim_helper
from models.planting_plan import FieldOperationPhases, FieldOperationStatus
from scheduler.decision_manager import DecisionManager, WorkTypePriorityStrategy  # <-- new import
from services.irrigation_service import IrrigationSimulator
from services.moisture_service import MoistureDataService
from services.planting_plan_service import PlantingPlanService
from services.protection_plan_service import ProtectionPlanService
from utils.event_logger import EventLogger

EXPORT_BASE_DIR = os.path.join(os.path.dirname(__file__), "../export")


class SimulationRunner:
    """
    Manages the simulation processes and their execution within a given
    SimPy environment.
    """

    def __init__(self, sim_params: sim_context.SimContext, decision_strategy: Any = None):
        self.params = sim_params
        self.event_logger = EventLogger()
        self.planting_plan_service = None
        self.protection_plan_service: ProtectionPlanService = None
        self.irrigation_service: IrrigationSimulator = None
        # Use provided strategy or default to EarliestDateStrategy
        self.decision_manager = DecisionManager(decision_strategy or WorkTypePriorityStrategy())

    def time_step_logger(self):
        """Logs the current simulation time step."""
        print(f"{'Time':<5} | {'Event'}\n{'-' * 25}")
        while True:
            current_date = self.params.start_date + datetime.timedelta(days=self.env.now)
            print(f" {current_date.strftime('%Y-%m')} | ") if current_date.day == 1 else None
            yield self.env.timeout(1)

    def planting_plan_observer(self):
        """
        Observes the planting plan and logs events.
        This is a placeholder for future implementation.
        """
        while True:
            current_date = self.params.start_date + datetime.timedelta(days=self.env.now)

            events = self.planting_plan_service.get_next_operations(current_date)

            if events:
                for event in events:
                    self.event_logger.log(event)

            yield self.env.timeout(1)

    def process_irrigation_observer(self):
        """
        Processes irrigation events based on moisture simulation results.
        This is a placeholder for future implementation.
        """

        while True:
            # there are any events for today,
            current_date = self.params.start_date + datetime.timedelta(days=self.env.now)

            events = self.irrigation_service.handle_next_operation(current_date)
            for event in events:
                # log the event
                self.event_logger.log(event)

            yield self.env.timeout(1)

    def simulation_event_handler(self):
        """
        Handles the simulation events by iterating through the time steps
        and executing the operations based on the current simulation context.
        This method integrates various services like planting, irrigation, and protection plans.
        """
        while True:
            current_date = self.params.start_date + datetime.timedelta(days=self.env.now)

            # Reset services if crop management phase is completed
            if self._is_phase_completed(FieldOperationPhases.HARVESTING):
                if self.irrigation_service or self.protection_plan_service:
                    self._reset_services()

            # Initialize protection and irrigation services if needed
            if self._should_initialize_services():
                self._initialize_services(current_date)

            # Collect operations and events from all services
            all_operations, all_events = self._collect_operations_and_events(current_date)

            # Decide and execute selected operations
            self._execute_selected_operations(all_operations, all_events, current_date)

            yield self.env.timeout(1)  # Wait for the next time step

    def _is_phase_completed(self, phase):
        """Checks if a specific phase is completed."""
        return (
            self.planting_plan_service.get_phase_status(phase) == FieldOperationStatus.IN_PROGRESS
        )

    def _reset_services(self):
        """Resets irrigation and protection plan services."""
        print("Crop management phase completed. Resetting irrigation and protection plan services.")
        self.irrigation_service = None
        self.protection_plan_service = None

    def _should_initialize_services(self):
        """Determines if protection and irrigation services should be initialized."""
        return (
            not self.protection_plan_service
            and self.planting_plan_service.active_phase
            and self.planting_plan_service.active_phase.phase_name
            == FieldOperationPhases.CROP_MANAGEMENT.value
        )

    def _initialize_services(self, current_date):
        """Initializes protection and irrigation services."""
        self.protection_plan_service = ProtectionPlanService(
            context=self.params,
            start_date=current_date,
            planting_plan=self.planting_plan_service.planting_plan,
        )
        ms = MoistureDataService(context=self.params, min_moisture_level=200)
        self.irrigation_service = IrrigationSimulator(
            context=self.params, moisture_data=ms.get_moisture_data(year=2022, depth_range="0-10")
        )

    def _collect_operations_and_events(self, current_date):
        """Collects operations and events from planting, protection, and irrigation services."""
        all_operations, all_events = [], []

        # Planting operations
        field_ops = self.planting_plan_service.get_next_operations(current_date)
        if field_ops:
            all_operations.extend(field_ops)
            all_events.extend(
                self.planting_plan_service.get_events_for_ops(field_ops, current_date)
            )

        # Protection operations
        if self.protection_plan_service:
            protection_ops = self.protection_plan_service.get_next_operations(current_date)
            all_operations.extend(protection_ops)
            all_events.extend(
                self.protection_plan_service.get_events_for_ops(protection_ops, current_date)
            )

        # Irrigation operations
        if self.irrigation_service:
            irrigation_ops, irrigation_events = self._get_irrigation_operations(current_date)
            all_operations.extend(irrigation_ops)
            all_events.extend(irrigation_events)

        return all_operations, all_events

    def _get_irrigation_operations(self, current_date):
        """Gets irrigation operations and events."""
        irrigation_ops, irrigation_events = [], []
        day = (current_date - self.params.start_date).days
        try:
            irrigation_status = self.irrigation_service.get_status_for_day(current_date)
            if irrigation_status["irrigation_needed"] >= 5:  # Threshold
                irrigation_ops.append(
                    {"type": "irrigation", "day": day, "status": irrigation_status}
                )
                irrigation_events.append(None)  # Placeholder for event
        except Exception:
            pass
        return irrigation_ops, irrigation_events

    def _execute_selected_operations(self, all_operations, all_events, current_date):
        """Executes the selected operations."""
        selected_ops = self.decision_manager.decide(all_operations)
        if selected_ops:
            for op in selected_ops:
                op_index = all_operations.index(op)
                related_event = all_events[op_index]

                if isinstance(op, dict) and op.get("type") == "irrigation":
                    self._handle_irrigation_event(op, current_date)
                else:
                    self.event_logger.log(related_event)

    def _handle_irrigation_event(self, op, current_date):
        """Handles irrigation-specific events."""
        event = self.irrigation_service.trigger_irrigation(
            current_date, irrigation_amount=op["status"]["irrigation_needed"]
        )
        if event:
            self.event_logger.log(event)
            print(
                f"    Irrigation triggered for day {op['day']} with {op['status']['irrigation_needed']:.0f} mm"
            )

    def run(self):
        """
        Runs the simulation in the SimPy environment.
        """

        # print(f'Starting simulation with parameters: {self.params}')

        # Create a SimPy environment
        self.env = simpy.Environment()

        # Init the planting plan service
        self.planting_plan_service = PlantingPlanService(
            context=self.params, start_date=self.params.start_date
        )

        # self.planting_plan_service.configure_planting_timeline(FieldOperationPhases.SOIL_PREPARATION, start_date=self.params.start_date)
        # self.irrigation_service = ms.MoistureService(context = self.params)

        # # Start the processes
        self.env.process(self.time_step_logger())
        self.env.process(self.simulation_event_handler())
        # self.env.process(self.process_irrigation_observer())

        # harvest_date = self.planting_plan_service.get_harvest_date()

        # Run the simulation from start to harvest date
        iterations = 400  # (harvest_date.date() - self.params.start_date).days + 2
        self.env.run(until=iterations)

        print("Simulation completed.")
        # Save all events to JSON at the end
        # store in ../export folder from the current directory
        # get the current date and create a directory if it doesn't exist
        date = datetime.datetime.now().strftime("%Y-%m-%d")

        export_dir = os.path.join(EXPORT_BASE_DIR, date)
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)

        # add field id and name to the filename

        # sanitize field name to be a valid filename (without spaces and special characters)
        clean_field_name = sim_helper.sanitize_filename(self.params.field_name)

        filename = f"simulation_{self.params.field_id}_{clean_field_name}.json"
        filepath = os.path.join(export_dir, filename)

        self.event_logger.save(filepath, context=self.params)

        # export moisture data
        # self.irrigation_service.export_moisture_data()
