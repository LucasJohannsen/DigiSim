#!/usr/bin/env python3
"""
Example: Using FastForwardRunner for rapid simulation.

Use case: Generate synthetic data for testing or demo preparation.
"""

import datetime

from models.sim_context import SimContext
from scheduler.fast_forward_runner import FastForwardRunner


def main():
    # Configure field context
    context = SimContext(
        field_size=20.0,
        soil_type="sandy_loam",
        start_date=datetime.datetime(2026, 1, 1),
        crop_type="Potato",
        variety="Belana",
        field_id=67890,
        field_name="Demo Field",
        fuel_variation=0.1,
    )

    # Create fast-forward runner
    runner = FastForwardRunner(
        context=context,
        n_days=500,  # Simulate 500 days
        output_target="json",
        flush_interval=50,  # Flush every 50 days for memory efficiency
    )

    # Execute fast-forward
    events = runner.run()

    print(f"Fast-forward completed: {len(events)} events generated")
    print("Output files in: export/fast_forward/")


if __name__ == "__main__":
    main()
