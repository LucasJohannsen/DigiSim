import numpy as np
import datetime
import json
import os

import scheduler.simulation_runner as sim_runner
from models.planting_plan import FieldOperationEvent
from utils import sim_helper
from models.sim_context import SimContext

MIN_MOISTURE_LEVEL = 50  # fallback if not in context


class IrrigationSimulator:
    """
    Simulates irrigation needs based on moisture data.
    """

    def __init__(self, context: SimContext, moisture_data: dict):
        self.context = context
        self.moisture_data = moisture_data
        self.min_moisture_level = getattr(context, 'min_moisture_level', MIN_MOISTURE_LEVEL)
        self.current_day = 0
        self.moisture = np.array(moisture_data.get("moisture_data", []), dtype=float)
        self.irrigation = np.zeros_like(self.moisture)
        # Track updated moisture after irrigation
        self.updated_moisture = self.moisture.copy()

    def get_status_for_day(self, day):
        """
        Return the current status for the given day, including whether irrigation is needed.
        Simulates daily evaporation and checks if irrigation is required.
        """
        if day < 0 or day >= len(self.moisture):
            raise IndexError("Day out of range")

        DAILY_EVAPORATION = 5  # in % nFK, assumed evaporation per day
        WEATHER_FORECAST_DAYS = 4  # days in advance for precipitation forecast
        MIN_IRRIGATION_NEEDED = 5  # in % nFK, minimum irrigation needed to trigger irrigation

        # Simulate daily moisture based on previous day and evaporation
        if day == 0:
            self.updated_moisture[day] = self.moisture[day]
        else:
            # Use the difference in original data as "evaporation" (or fallback to fixed rate)
            evaporation = self.moisture[day] - self.moisture[day-1]
            self.updated_moisture[day] = self.updated_moisture[day-1] + evaporation

        # Check if irrigation is needed
        moisture_level = self.updated_moisture[day]
        irrigation_needed = max(0, self.min_moisture_level - moisture_level)
        needs_irrigation = False

        if irrigation_needed >= MIN_IRRIGATION_NEEDED:
            # Wetterbericht geht 4 Tage im Voraus
            upcoming_moisture_levels = self.moisture[day:day + WEATHER_FORECAST_DAYS]
            # Only irrigate if no upcoming day is above the threshold
            if not np.any(np.array(upcoming_moisture_levels) > self.min_moisture_level):
                needs_irrigation = True

        #
        # 
        # print(f"    Day {day}: Moisture {moisture_level:.2f}%, Irrigation needed: {irrigation_needed:.0f}mm")

        return {
            "day": day,
            "date": self.moisture_data['dates'][day],
            "moisture": float(moisture_level),
            "min_moisture_level": self.min_moisture_level,
            "irrigation_needed": irrigation_needed,
            "needs_irrigation": needs_irrigation
        }

    def trigger_irrigation(self, day, irrigation_amount: float = None):
        """
        Trigger irrigation for the given day and return the event.
        If irrigation_amount is not provided, use the calculated need.
        """
        # Create event
        PUMP_FLOW_RATE = 50  # in m³/h und für 7 bar
        FUEL_CONSUMPTION = 5  # in l/h
        fuel_per_ha_and_mm_irrigation = (10 / PUMP_FLOW_RATE) * FUEL_CONSUMPTION
        duration_per_ha_and_mm_irrigation = 10 / PUMP_FLOW_RATE
        duration_factor = duration_per_ha_and_mm_irrigation * self.context.field_size
        fuel_factor = fuel_per_ha_and_mm_irrigation * self.context.field_size

        date = datetime.datetime(self.context.start_date.year, 1, 1, 12) + datetime.timedelta(days=day)
        duration = float(round(irrigation_amount * duration_factor, 2))
        enddate = date + datetime.timedelta(hours=duration)

        event = FieldOperationEvent(
            worktype=15,
            start_date=date.strftime('%Y-%m-%d %H:%M:%S'),
            end_date=enddate.strftime('%Y-%m-%d %H:%M:%S'),
            area=self.context.field_size,
            distance=0,
            distanceWorked=0,
            duration=duration*60*60,  # in seconds
            durationWorked=duration*60*60,
            fuel=float(round(irrigation_amount * fuel_factor, 2)),  # in liters
            application_type='irrigation',
            application_category='water',
            application_name='Irrigation',
            application_amount=irrigation_amount,
            application_unit=12,  # mm
            worktype_text='Bewässerung',
            machine="Regner 5000"
        )
        event.field = self.context.field_id

        if irrigation_amount is None:
            # Calculate how much irrigation is needed
            moisture_level = self.updated_moisture[day]
            irrigation_needed = max(0, self.min_moisture_level - moisture_level)
            MIN_IRRIGATION_NEEDED = 5
            if irrigation_needed < MIN_IRRIGATION_NEEDED:
                return None
            irrigation_amount = irrigation_needed * np.random.uniform(0.8, 1.2)

        self.irrigation[day] = irrigation_amount
        self.updated_moisture[day] += irrigation_amount
        for d in range(day + 1, len(self.updated_moisture)):
            self.updated_moisture[d] = max(self.updated_moisture[d], self.updated_moisture[d-1])

        return event

    def export_moisture_data(self):
        """
        Export the moisture data and irrigation events as json
        This function is called by the simulation runner.
        """
        moisture_data = {
            'coords': self.moisture_data['coords'],
            'dates': [date.strftime('%Y-%m-%d') for date in self.moisture_data['dates']],
            'moisture_data': self.moisture.tolist(),
            'new_moisture': self.updated_moisture.tolist(),
            'irrigation': self.irrigation.tolist(),
        }

        # Save to file under 
        date = datetime.datetime.now().strftime('%Y-%m-%d')

        export_dir = os.path.join(sim_runner.EXPORT_BASE_DIR, date)
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)

        # add field id and name to the filename

        # sanitize field name to be a valid filename (without spaces and special characters)
        clean_field_name = sim_helper.sanitize_filename(self.context.field_name)

        filename = f'irrigation_{self.context.field_id}_{clean_field_name}.json'
        filepath = os.path.join(export_dir, filename)

        with open(filepath, 'w') as f:
            json.dump(moisture_data, f, indent=4)