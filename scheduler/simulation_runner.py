import datetime
import os
import simpy

from services.planting_plan_service import PlantingPlanService
from utils.event_logger import EventLogger
import models.sim_context as sim_context
import utils.sim_helper as sim_helper
import services.moisture_service as ms


EXPORT_BASE_DIR = os.path.join(os.path.dirname(__file__), '../export')

class SimulationRunner:
    """
    Manages the simulation processes and their execution within a given
    SimPy environment.
    """
    def __init__(self, sim_params: sim_context.SimContext):
        self.params = sim_params
        self.event_logger = EventLogger()
        self.planting_plan_service = None
        self.irrigation_service: ms.MoistureService = None

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
            
            events = self.planting_plan_service.handle_next_operation(current_date)
            
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

    def run(self):
        """
        Runs the simulation in the SimPy environment.
        """

        

        print(f'Starting simulation with parameters: {self.params}')
        
        # Create a SimPy environment
        self.env = simpy.Environment()

        # Init the planting plan service
        self.planting_plan_service = PlantingPlanService(
            context=self.params,
            start_date=self.params.start_date
        )
        self.planting_plan_service.prepare_planting_plan()
        self.irrigation_service = ms.MoistureService(context = self.params)

   
        # Start the processes
        self.env.process(self.observer())
        self.env.process(self.planting_plan_observer())
        self.env.process(self.process_irrigation_observer())

        harvest_date = self.planting_plan_service.get_harvest_date()

        # Run the simulation from start to harvest date
        iterations = (harvest_date.date() - self.params.start_date).days + 2
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
        self.irrigation_service.export_moisture_data()