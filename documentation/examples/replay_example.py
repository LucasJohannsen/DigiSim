#!/usr/bin/env python3
"""
Example: Using ReplayRunner to re-simulate past time periods.

Use case: Recover missing simulation data for a specific time period.
"""
import datetime
from models.sim_context import SimContext
from scheduler.replay_runner import ReplayRunner


def main():
    # Configure field context
    context = SimContext(
        field_size=15.0,
        soil_type="sandy_loam",
        start_date=datetime.datetime(2025, 1, 1),
        crop_type="Potato",
        variety="Belana",
        field_id=12345,
        field_name="Example Field",
        fuel_variation=0.1
    )
    
    # Create replay runner for specific date range
    runner = ReplayRunner(
        context=context,
        start_date=datetime.date(2025, 4, 1),  # Start of growing season
        end_date=datetime.date(2025, 10, 31),  # End of growing season
        output_target="json"
    )
    
    # Execute replay
    events = runner.run()
    
    print(f"Replay completed: {len(events)} events generated")
    print("Output files in: export/replay/")


if __name__ == "__main__":
    main()
