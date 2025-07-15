import cmd
import simpy
import sys

import models.sim_context as sc
import scheduler.simulation_runner as sr
from services.farms_service import FarmLoaderService    

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

    def do_pick_field(self, arg):
        'Select a field from a farm.\n'

        print('Select a farm from the list')
        farm_loader = FarmLoaderService()
        farms = farm_loader.get_farms()
        # Print farm table header
        print(f"{'Farm ID':<10} {'Name':<20}")
        print('-' * 30)
        for farm in farms:
            print(f"{farm.id:<10} {farm.name:<20}")

        farm_id = input('\nEnter the Farm ID to select: ')
        selected_farm = next((f for f in farms if f.id == int(farm_id)), None)
        if not selected_farm:
            print("Invalid Farm ID selected.")
            return

        # List fields in the selected farm
        print('\nFields in the selected farm:')
        print(f"{'Field ID':<10} {'Name':<20} {'Distance to Barn (km)':<22} {'Area (ha)':<10}")
        print('-' * 70)
        for field in selected_farm.fields:
            print(f"{field.id:<10} {field.name:<20} {field.distance_to_barn:<22} {field.area:<10}")

        field_id = input('\nEnter the Field ID to select: ')
        selected_field = next((f for f in selected_farm.fields if f.id == int(field_id)), None)
        if not selected_field:
            print("Invalid Field ID selected.")
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
