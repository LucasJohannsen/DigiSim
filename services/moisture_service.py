import os
import random
import urllib.request as request

import geopandas as gpd
import netCDF4
import numpy as np

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


class MoistureDataService:
    """
    Handles downloading, reading, and transforming soil moisture/weather data.
    """

    def __init__(self, context: SimContext, **kwargs):

        self.context = context
        self.min_moisture_level = kwargs.get(
            'min_moisture_level', MIN_MOISTURE_LEVEL)

    def get_moisture_file(self, year, depth_range) -> str:

        # download if not in current folder, else return path
        filepath = f"grids_germany_daily_soil_moisture_{MOISTURE_SOIL_TYPE}_{year}_{depth_range}_v1.nc"
        local_storage_path = os.path.join(os.getcwd(), CACHE_FOLDER, filepath)

        if not os.path.exists(local_storage_path):
            url = f"{BASE_URL}/{MOISTURE_SOIL_TYPE}/{year}/{filepath}"
            print(f"Downloading {url} ... (>~130MB)")
            os.makedirs(os.path.dirname(local_storage_path), exist_ok=True)
            request.urlretrieve(url, local_storage_path)
        #print(f"Downloaded to {local_storage_path}")

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

    def get_moisture_data(self, **kwargs):
        """
        Loads and returns the moisture data and coordinates.
        Falls back to nearest available year if requested year is not available.
        """
        year = kwargs.get('year', YEAR)
        depth_range = kwargs.get('depth_range', DEPTH_RANGE)

        try:
            nc_file_path = self.get_moisture_file(
                year=year, depth_range=depth_range)
            nc_file = netCDF4.Dataset(nc_file_path, 'r')
        except Exception as e:
            # Fallback to default year if requested year is not available
            print(f"Warning: Moisture data for year {year} not available. Falling back to {YEAR}. Error: {e}")
            year = YEAR
            nc_file_path = self.get_moisture_file(
                year=year, depth_range=depth_range)
            nc_file = netCDF4.Dataset(nc_file_path, 'r')

        moisture_object = self.find_random_coordinate_with_date(nc_file)
        lat, lon = self.gauss_to_wgs84(
            moisture_object['x'], moisture_object['y'])

        return {
            'coords': [lat, lon],
            'dates': [datetime.date(year, 1, 1) + datetime.timedelta(days=i) for i in range(len(moisture_object['moisture_data']))],
            'moisture_data': moisture_object['moisture_data']
        }