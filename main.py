import cmd
import datetime
import sys

import models.sim_context as sc
import scheduler.simulation_runner as sr
import services.sim_context_service as scs
from scheduler.fast_forward_runner import FastForwardRunner
from scheduler.replay_runner import ReplayRunner
from services.sim_context_service import get_batch_simulation_context, get_simulation_context


class DigiSimCli(cmd.Cmd):
    intro = "Welcome to the DigiSim CLI. Type help or ? to list commands.\n"
    prompt = "(digisim) "

    def __init__(self):
        self.context = sc.SimContext()

        super().__init__()

    def do_run(self, arg):
        "Run the DigiSim simulation."
        print("Running DigiSim simulation...")

        # print the current configuration
        self.do_show_config()

        # run the simulation
        runner = sr.SimulationRunner(self.context)
        runner.run()

    def do_plan(self, arg):
        "Plan a new simulation."
        print("Planning a new simulation...")

        # Collect simulation parameters from the user
        self.context = scs.collect(self.context)

    def do_pick_field(self, arg):
        "Select a field from a farm.\n"

        selected_field = get_simulation_context()
        if not selected_field:
            print("No valid field selected. Please try again.")
            return

        # update the context with the selected farm and field
        self.context.field_size = selected_field.area
        self.context.field_id = selected_field.id
        self.context.field_name = selected_field.name

    def do_show_config(self, arg=None):
        "Show the current configuration of DigiSim."
        print("Current configuration:")

        for key, value in self.context.__dict__.items():
            print(f"  \033[91m{key}:\033[0m {value}")

    def do_run_batch(self, arg=None):
        "Run a batch of simulations."
        print("Running batch simulations...")

        # Collect batch simulation contexts
        batch_contexts = get_batch_simulation_context()
        if not batch_contexts:
            print("No valid batch contexts available. Please try again.")
            return
        # Run each context in the batch
        for context in batch_contexts:
            print(f"Running simulation for field: {context.field_name} (ID: {context.field_id})")
            runner = sr.SimulationRunner(context)
            runner.run()

        print("Batch simulations completed.")

    def do_replay(self, arg):
        "Replay simulation for a past time period. Usage: replay --from YYYY-MM-DD --to YYYY-MM-DD [--output json|stdout]"
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--from", dest="start_date", required=True, help="Start date (YYYY-MM-DD)"
        )
        parser.add_argument("--to", dest="end_date", required=True, help="End date (YYYY-MM-DD)")
        parser.add_argument(
            "--output", default="json", choices=["json", "stdout", "digizert"], help="Output target"
        )

        try:
            args = parser.parse_args(arg.split())
            start_date = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
            end_date = datetime.datetime.strptime(args.end_date, "%Y-%m-%d").date()

            print(f"\nStarting replay simulation from {start_date} to {end_date}...")

            runner = ReplayRunner(
                context=self.context,
                start_date=start_date,
                end_date=end_date,
                output_target=args.output,
            )
            events = runner.run()

            print(f"\nReplay completed: {len(events)} events generated.")

        except Exception as e:
            print(f"Error: {e}")
            print("Usage: replay --from YYYY-MM-DD --to YYYY-MM-DD [--output json|stdout]")

    def do_fast_forward(self, arg):
        "Fast-forward simulation for N days. Usage: fast_forward --days N [--output json|stdout]"
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--days", type=int, required=True, help="Number of days to simulate")
        parser.add_argument(
            "--output", default="json", choices=["json", "stdout", "digizert"], help="Output target"
        )

        try:
            args = parser.parse_args(arg.split())

            print(f"\nStarting fast-forward simulation for {args.days} days...")

            runner = FastForwardRunner(
                context=self.context, n_days=args.days, output_target=args.output
            )
            events = runner.run()

            print(f"\nFast-forward completed: {len(events)} events generated.")

        except Exception as e:
            print(f"Error: {e}")
            print("Usage: fast_forward --days N [--output json|stdout]")

    def do_exit(self, arg=None):
        "Exit the DigiSim CLI.\n"
        print("Exiting DigiSim CLI.")
        return True


if __name__ == "__main__":
    cli = DigiSimCli()
    try:
        cli.cmdloop()
    except KeyboardInterrupt:
        print("\nExiting DigiSim CLI due to keyboard interrupt.")
        sys.exit(0)
