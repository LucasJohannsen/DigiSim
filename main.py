import cmd
import simpy
import sys

import models.sim_context as sc
import scheduler.simulation_runner as sr

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
        self.context.collect()


    def do_show_config(self, arg = None):
        'Show the current configuration of DigiSim.'
        print('Current configuration:')

        for key, value in self.context.__dict__.items():
            print(f'  \033[91m{key}:\033[0m {value}')

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
