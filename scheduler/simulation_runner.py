import datetime
import simpy
import models.sim_context as sim_context


import utils.sim_helper as sim_helper
from models.planting_plan import PlantingPlan, FieldPhases, FieldOperation 
from utils.event_logger import EventLogger
from services.planting_plan_service import PlantingPlanService

class SimulationRunner:
    """
    Manages the simulation processes and their execution within a given
    SimPy environment.
    """
    def __init__(self, sim_params: sim_context.SimContext):
        self.params = sim_params
        self.event_logger = EventLogger()
        self.planting_plan_service = None

    def observer(self):
        """A process that yields at each time step and prints the status."""
        print(f'{"Time":<5} | {"Event"}\n{"-"*25}')
        while True:
            current_date = self.params.start_date + datetime.timedelta(days=self.env.now)
            print(f' {current_date} | ') if current_date.day == 1 else None
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

        # Start the processes
        self.env.process(self.observer())
        self.env.process(self.planting_plan_observer())


        # Run the simulation from start to harvest date
        iterations = (self.params.harvest_date - self.params.start_date).days + 2
        self.env.run(until=iterations)

        print('Simulation completed.')
        # Save all events to JSON at the end
        self.event_logger.save("simulation_events.json")