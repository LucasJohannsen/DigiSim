import cmd
import simpy
import sys

import models.sim_context as sc
import scheduler.simulation_runner as sr
from services.sim_context_service import get_simulation_context, get_batch_simulation_context
import services.sim_context_service as scs

class DigiSimCli(cmd.Cmd):


    intro = 'Welcome to the DigiSim CLI. Type help or ? to list commands.\n'
    prompt = '(digisim) '

    def __init__(self):
        self.context = sc.SimContext()
        
      
        super().__init__()


    def do_run(self, arg):
        'Run the DigiSim simulation.'
        print('Running DigiSim simulation...')

        # print the current configuration
        self.do_show_config()

        # run the simulation
        runner = sr.SimulationRunner(self.context)
        runner.run()

    def do_plan(self, arg):
        'Plan a new simulation.'
        print('Planning a new simulation...')

        # Collect simulation parameters from the user
        self.context = scs.collect(self.context)

    def do_pick_field(self, arg):
        'Select a field from a farm.\n'

        selected_field = get_simulation_context()
        if not selected_field:
            print("No valid field selected. Please try again.")
            return

        # update the context with the selected farm and field
        self.context.field_size = selected_field.area
        self.context.field_id = selected_field.id
        self.context.field_name = selected_field.name


    def do_show_config(self, arg = None):
        'Show the current configuration of DigiSim.'
        print('Current configuration:')

        for key, value in self.context.__dict__.items():
            print(f'  \033[91m{key}:\033[0m {value}')
    
    def do_run_batch(self, arg = None):
        'Run a batch of simulations.'
        print('Running batch simulations...')

        # Collect batch simulation contexts
        batch_contexts = get_batch_simulation_context()
        if not batch_contexts:
            print("No valid batch contexts available. Please try again.")
            return
        # Run each context in the batch
        for context in batch_contexts:
            print(f'Running simulation for field: {context.field_name} (ID: {context.field_id})')
            runner = sr.SimulationRunner(context)
            runner.run()

        print('Batch simulations completed.')

       

    def do_exit(self, arg = None):
        'Exit the DigiSim CLI.\n'
        print('Exiting DigiSim CLI.')
        return True
    
if __name__ == '__main__':
    cli = DigiSimCli()
    try:
        cli.cmdloop()
    except KeyboardInterrupt:
        print('\nExiting DigiSim CLI due to keyboard interrupt.')
        sys.exit(0)
