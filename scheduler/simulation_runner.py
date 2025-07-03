import datetime
import simpy
import models.sim_context as sim_context

class SimulationRunner:
    """
    Manages the simulation processes and their execution within a given
    SimPy environment.
    """
    def __init__(self, sim_params: sim_context.SimContext):
        self.params = sim_params

    def observer(self):
        """A process that yields at each time step and prints the status."""
        print(f'{"Time":<5} | {"Event"}\n{"-"*25}')
        while True:
            current_date = self.params.start_date + datetime.timedelta(days=self.env.now)
            print(f' {current_date} | ')
            yield self.env.timeout(1)

    def run(self):
        """
        Runs the simulation in the SimPy environment.
        """
        print(f'Starting simulation with parameters: {self.params}')
        
        # Create a SimPy environment
        self.env = simpy.Environment()

        # Start the observer process
        self.env.process(self.observer())

        # Run the simulation from start to harvest date
        iterations = (self.params.harvest_date - self.params.start_date).days + 2
        self.env.run(until=iterations)

        print('Simulation completed.')