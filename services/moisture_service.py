import os
import random
import urllib.request as request

import geopandas as gpd
import netCDF4
import numpy as np

import scheduler.simulation_runner as sim_runner
from models.planting_plan import FieldOperationEvent
import datetime
from utils import sim_helper
from models.sim_context import SimContext
import json


# download moisture data
# https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/soil_moisture/

MOISTURE_SOIL_TYPE = 'grass'  # 'grass', 'wheat',  'oak','pine','spruce','beach'
BASE_URL = 'https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/soil_moisture'
CACHE_FOLDER = "dwd_data"
YEAR = 2022
DEPTH_RANGE = '0-10'  # '20-30'
MIN_MOISTURE_LEVEL = 50  # in % nFK


class MoistureService:
    """
    Service to handle soil moisture data and irrigation needs.
    """

    def __init__(self, context: SimContext, **kwargs):

        self.context = context
        self.min_moisture_level = kwargs.get(
            'min_moisture_level', MIN_MOISTURE_LEVEL)

        self.planned_events = self.prepare_events(

        )

    def get_moisture_file(self, year, depth_range) -> str:

        # download if not in current folder, else return path
        filepath = f"grids_germany_daily_soil_moisture_{MOISTURE_SOIL_TYPE}_{year}_{depth_range}_v1.nc"
        local_storage_path = os.path.join(os.getcwd(), CACHE_FOLDER, filepath)

        if not os.path.exists(local_storage_path):
            url = f"{BASE_URL}/{MOISTURE_SOIL_TYPE}/{year}/{filepath}"
            print(f"Downloading {url} ... (>~130MB)")
            os.makedirs(os.path.dirname(local_storage_path), exist_ok=True)
            request.urlretrieve(url, local_storage_path)
        print(f"Downloaded to {local_storage_path}")

        return local_storage_path

    def gauss_to_wgs84(self, x, y):
        """
        Convert Gauss-Krueger coordinates (EPSG:31467) to WGS84 (EPSG:4326).
        """
        point_gdf = gpd.GeoDataFrame(
            geometry=gpd.points_from_xy([x], [y]),
            crs='EPSG:31467'
        )
        point_wgs84 = point_gdf.to_crs('EPSG:4326')
        return point_wgs84.geometry.x.iloc[0], point_wgs84.geometry.y.iloc[0]

    def find_random_coordinate_with_date(self, nc_file):
        """
        Get a random x and y coordinate from the netCDF file.
        """
        attempts = 0
        while attempts < 10:
            x_idx = random.randint(0, len(nc_file.variables['x']) - 1)
            y_idx = random.randint(0, len(nc_file.variables['y']) - 1)
            x_val = nc_file.variables['x'][x_idx]
            y_val = nc_file.variables['y'][y_idx]
            moisture_data = nc_file.variables['paws'][0, :, y_idx, x_idx]
            # Check if all values are masked or blank
            if np.ma.is_masked(moisture_data) and moisture_data.mask.all():
                attempts += 1
                continue
            if np.all(moisture_data == nc_file.variables['paws']._FillValue):
                attempts += 1
                continue
            # Found valid data

            return {
                'x': x_val,
                'y': y_val,
                'moisture_data': moisture_data
            }
        raise ValueError(
            "Could not find a valid coordinate with non-blank moisture data.")

    def calculate_precipitation(self, moisture_data, min_moisture_level):
        """ Calculate irrigation needs based on moisture data.
        Args:
            moisture_data (np.ndarray): Array of soil moisture data (% nFK).

            Wir verwenden eine Faustformel: 1mm Bewässerung -> 1% nFK Erhöhung

        Returns:
            np.ndarray: New moisture levels after irrigation.
            np.ndarray: Irrigation amounts for each day.
        """

        DAILY_EVAPORATION = 5  # in % nFK, assumed evaporation per day
        WEATHER_FORECAST_DAYS = 4  # days in advance for precipitation forecast
        MIN_IRRIGATION_NEEDED = 5  # in % nFK, minimum irrigation needed to trigger irrigation

        new_moisture = [moisture_data[0]] * len(moisture_data)
        irrigation = [0] * len(moisture_data)

        for day in range(len(moisture_data)):
            evaporation = 0
            if day > 0:
                evaporation = moisture_data[day] - \
                    moisture_data[day-1]  # aus der Zeitreihe
                new_moisture[day] = new_moisture[day-1] + evaporation

            # get moisture data for the day
            if new_moisture[day] < min_moisture_level:
                # Calculate new moisture level after precipitation
                preciption_needed = min_moisture_level - new_moisture[day]

                if 0 < preciption_needed < MIN_IRRIGATION_NEEDED:
                    print(
                        f"Skipping irrigation for day {day} as only {preciption_needed:.2f}% nFK needed.")
                    continue  # Skip if less than 5% nFK needed

                # Wetterbericht geht 4 Tage im Voraus
                upcoming_moisture_levels = moisture_data[day:day +
                                                         WEATHER_FORECAST_DAYS]
                if not np.any(upcoming_moisture_levels > min_moisture_level):
                    irrigation_needed = preciption_needed * \
                        np.random.uniform(0.8, 1.2)
                    new_moisture[day] = new_moisture[day] + irrigation_needed
                    irrigation[day] = irrigation_needed

                    print(
                        f"irrigate day {day} with {irrigation_needed:.2f} mm, evaporation: {evaporation:.1f} ")

            if new_moisture[day] > moisture_data[day]:
                new_moisture[day] = new_moisture[day] * 0.99

            if new_moisture[day] < moisture_data[day]:
                new_moisture[day] = moisture_data[day]

        return np.array(new_moisture), np.array(irrigation)

    def prepare_events(self, **kwargs):
        """
        Simulate moisture and irrigation needs.
        All parameters can be overridden via kwargs.
        """
        moisture_soil_type = kwargs.get(
            'moisture_soil_type', MOISTURE_SOIL_TYPE)
        year = kwargs.get('year', YEAR)
        depth_range = kwargs.get('depth_range', DEPTH_RANGE)
        min_moisture_level = self.min_moisture_level

        nc_file_path = self.get_moisture_file(
            year=year, depth_range=depth_range)
        nc_file = netCDF4.Dataset(nc_file_path, 'r')

        moisture_object = self.find_random_coordinate_with_date(nc_file)

        lat, lon = self.gauss_to_wgs84(
            moisture_object['x'], moisture_object['y'])

        new_moisture, irrigation = self.calculate_precipitation(
            moisture_data=moisture_object['moisture_data'], min_moisture_level=min_moisture_level
        )

        events = self.get_irrigation_events(irrigation)

        return {
            'coords': [lat, lon],
            'dates': [datetime.date(year, 1, 1) + datetime.timedelta(days=i) for i in range(len(new_moisture))],
            'moisture_data': moisture_object['moisture_data'],
            'new_moisture': new_moisture,
            'irrigation': irrigation,
            "events": events
        }

    def get_irrigation_events(self, irrigation_result):
        """ 
        Get the doys of the irrigation events and log them.

        """

        # https://www.lwk-niedersachsen.de/lwk/news/39282_Wirtschaftlich_beregnen_in_unruhigen_Zeiten
        PUMP_FLOW_RATE = 50  # in m³/h und für 7 bar
        FUEL_CONSUMPTION = 5  # in l/h

        # Berechne den Kraftstoffverbrauch pro Hektar und mm Beregnung
        # Annahme: 1 mm auf 1 ha = 10 m³ Wasser (1 mm = 1 L/m², 1 ha = 10.000 m²)
        # Pumpenleistung: m³/h, Kraftstoffverbrauch: l/h
        # Kraftstoff pro mm und ha = (10m³ / 50 m³/h) * 5 l/h
        fuel_per_ha_and_mm_irrigation = (
            10 / PUMP_FLOW_RATE) * FUEL_CONSUMPTION

        # duration in hours for 1 ha
        duration_per_ha_and_mm_irrigation = 10 / PUMP_FLOW_RATE  # 1mm-> 10³/ha
    #
        # calculate duration and fuel
        duration_factor = duration_per_ha_and_mm_irrigation * \
            self.context.field_size  # duration in hours for 100 ha
        fuel_factor = fuel_per_ha_and_mm_irrigation * self.context.field_size

        events = []
        for doy, amount in enumerate(irrigation_result):
            if amount > 0:
                date = datetime.datetime(
                    # midday
                    self.context.start_date.year, 1, 1, 12) + datetime.timedelta(days=doy)
                duration = float(round(amount * duration_factor, 2))
                enddate = date + datetime.timedelta(hours=duration)

                event = FieldOperationEvent(
                    worktype=15,
                    start_date=date.strftime('%Y-%m-%d %H:%M:%S'),
                    end_date=enddate.strftime('%Y-%m-%d %H:%M:%S'),
                    area=self.context.field_size,
                    distance=0,
                    distanceWorked=0,
                    duration=duration,
                    durationWorked=duration,  # in hours
                    fuel=float(round(amount * fuel_factor, 2)),  # in liters
                    application_type='irrigation',
                    application_category='water',
                    application_name='Irrigation',
                    application_amount=amount,
                    application_unit='mm',
                    worktype_text='Bewässerung',
                    machine="Regner 5000"
                )
                event.field = self.context.field_id

                events.append(event)

        return events

    def handle_next_operation(self, current_date):
        """
        Handle the next operation based on the current date and context.
        This function is called by the simulation runner.
        """

        irrigation_events = []
        if self.planned_events:
            for event in self.planned_events['events']:
                # Convert event.start_date (string) to datetime for comparison
                event_start_date = datetime.datetime.strptime(
                    event.start_date, '%Y-%m-%d %H:%M:%S')
                if event_start_date.timetuple().tm_yday == current_date.timetuple().tm_yday:
                    # log the event
                    # print(f"Handling irrigation event on DOY {current_date.timetuple().tm_yday}: {event}")
                    print(
                        f"\033[92m    Irrigation: {event_start_date.strftime('%Y-%m-%dT%H:%M:%SZ')}\033[0m")
                    irrigation_events.append(event)

        return irrigation_events

    def export_moisture_data(self):
        """
        Export the moisture data and irrigation events as json
        This function is called by the simulation runner.
        """
       
        moisture_data = {
            'coords': self.planned_events['coords'],
            'dates': [date.strftime('%Y-%m-%d') for date in self.planned_events['dates']],
            'moisture_data': self.planned_events['moisture_data'].tolist(),
            'new_moisture': self.planned_events['new_moisture'].tolist(),
            'irrigation': self.planned_events['irrigation'].tolist(),
            #'events': [event.__dict__ for event in self.planned_events['events']]
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