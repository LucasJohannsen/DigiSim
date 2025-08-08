import datetime
import os
import simpy
from typing import Any
from scheduler.decision_manager import DecisionManager, WorkTypePriorityStrategy  # <-- new import

from services.planting_plan_service import PlantingPlanService
from utils.event_logger import EventLogger
import models.sim_context as sim_context
import utils.sim_helper as sim_helper
from  services.irrigation_service import IrrigationSimulator 
from services.moisture_service import MoistureDataService
from models.planting_plan import FieldOperationPhases, FieldOperationStatus
from services.protection_plan_service import ProtectionPlanService


EXPORT_BASE_DIR = os.path.join(os.path.dirname(__file__), '../export')

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

    def observer(self):
        """A process that yields at each time step and prints the status."""
        print(f'{"Time":<5} | {"Event"}\n{"-"*25}')
        while True:
            current_date = self.params.start_date + datetime.timedelta(days=self.env.now)
            print(f' {current_date.strftime("%Y-%m")} | ') if current_date.day == 1 else None
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

    def new_observer(self):
        """
        A new observer process that monitors the simulation and logs events.
        Uses the decision manager to select which event to process first.
        """
        while True:
            current_date = self.params.start_date + datetime.timedelta(days=self.env.now)
            day_of_year = current_date.timetuple().tm_yday

            field_ops = self.planting_plan_service.get_next_operations(current_date)
            #events = self.planting_plan_service.get_events_for_ops(field_ops, current_date)

            # reset irrigation, proection if phase crop_management is completed
            crop_phase_status = self.planting_plan_service.get_phase_status(FieldOperationPhases.HARVESTING)
            if self.protection_plan_service and crop_phase_status == FieldOperationStatus.IN_PROGRESS:
                print("Crop management phase completed. Resetting irrigation and protection plan services.")
                self.irrigation_service = None
                self.protection_plan_service = None

            # create protection plan service if not already created if crop_management phase is active
            if not self.protection_plan_service and \
               self.planting_plan_service.active_phase and \
                self.planting_plan_service.active_phase.phase_name == FieldOperationPhases.CROP_MANAGEMENT.value:
                self.protection_plan_service = ProtectionPlanService(
                    context=self.params,
                    start_date=current_date,
                    planting_plan=self.planting_plan_service.planting_plan
                )

                ms = MoistureDataService(
                    context=self.params,
                    min_moisture_level=200
                )
                self.irrigation_service = IrrigationSimulator(
                    context=self.params,
                    moisture_data=ms.get_moisture_data(year=2022, depth_range='0-10')
                )
                

            protection_ops = []
            if self.protection_plan_service:
                protection_ops = self.protection_plan_service.get_next_operations(current_date)

            # --- IRRIGATION INTEGRATION START ---
            irrigation_ops = []
            irrigation_events = []
            if self.irrigation_service:
                day = (current_date - self.params.start_date).days
                try:

                    irrigation_status = self.irrigation_service.get_status_for_day(day_of_year)
                    # If irrigation is needed, create a "virtual" operation object
                    if irrigation_status["irrigation_needed"] >= 5:  # threshold as in IrrigationSimulator
                        # Use a simple dict as a placeholder operation
                        irrigation_op = {
                            "type": "irrigation",
                            "day": day,
                            "status": irrigation_status
                        }
                        irrigation_ops.append(irrigation_op)
                        # For event mapping, store None for now (event will be created if selected)
                        irrigation_events.append(None)
                except Exception:
                    pass
            # --- IRRIGATION INTEGRATION END ---

            # Collect all operations/events from different services
            all_operations = []
            all_events = []
            if field_ops:
                all_operations.extend(field_ops)
                all_events.extend(self.planting_plan_service.get_events_for_ops(field_ops, current_date))
            if protection_ops:
                all_operations.extend(protection_ops)
                all_events.extend(self.protection_plan_service.get_events_for_ops(protection_ops, current_date))
            # Add irrigation ops last
            if irrigation_ops:
                all_operations.extend(irrigation_ops)
                all_events.extend(irrigation_events)

            # Use decision manager to select which operation to perform/log
            selected_op = self.decision_manager.decide(all_operations)
            if selected_op:
                for op in selected_op:
                    op_index = all_operations.index(op)
                    related_event = all_events[op_index]
                    # --- IRRIGATION EVENT HANDLING ---
                    if isinstance(op, dict) and op.get("type") == "irrigation":
                        # Trigger irrigation and get the event
                        day = op["day"]
                        event = self.irrigation_service.trigger_irrigation(day_of_year, irrigation_amount=op["status"]["irrigation_needed"])
                        if event:
                            self.event_logger.log(event)
                            print(f"    Irrigation triggered for day {day} with {op["status"]["irrigation_needed"]:.0f} mm")
                    else:
                        # Normal event logging
                        self.event_logger.log(related_event)

            yield self.env.timeout(1)  # Wait for the next time step



    def run(self):
        """
        Runs the simulation in the SimPy environment.
        """

        

        #print(f'Starting simulation with parameters: {self.params}')
        
        # Create a SimPy environment
        self.env = simpy.Environment()

        # Init the planting plan service
        self.planting_plan_service = PlantingPlanService(
            context=self.params,
            start_date=self.params.start_date
        )

        

        #self.planting_plan_service.configure_planting_timeline(FieldOperationPhases.SOIL_PREPARATION, start_date=self.params.start_date)
        # self.irrigation_service = ms.MoistureService(context = self.params)

   
        # # Start the processes
        self.env.process(self.observer())
        self.env.process(self.new_observer())
        # self.env.process(self.process_irrigation_observer())

        #harvest_date = self.planting_plan_service.get_harvest_date()

        # Run the simulation from start to harvest date
        iterations = 400#(harvest_date.date() - self.params.start_date).days + 2
        self.env.run(until=iterations)


        print('Simulation completed.')
        # Save all events to JSON at the end
        # store in ../export folder from the current directory
        # get the current date and create a directory if it doesn't exist
        date = datetime.datetime.now().strftime('%Y-%m-%d')

        export_dir = os.path.join(EXPORT_BASE_DIR, date)
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)

        # add field id and name to the filename

        # sanitize field name to be a valid filename (without spaces and special characters)
        clean_field_name = sim_helper.sanitize_filename(self.params.field_name)

        filename = f'simulation_{self.params.field_id}_{clean_field_name}.json'
        filepath = os.path.join(export_dir, filename)

        self.event_logger.save(filepath, context = self.params)

        # export moisture data
        #self.irrigation_service.export_moisture_data()