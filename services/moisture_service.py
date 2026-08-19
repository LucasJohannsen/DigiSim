import os
import random
import re
import urllib.request as request

import geopandas as gpd
import netCDF4
import numpy as np

import datetime
from models.sim_context import SimContext


# download moisture data
# https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/soil_moisture/

MOISTURE_SOIL_TYPE = 'grass'  # 'grass', 'wheat',  'oak','pine','spruce','beach'
BASE_URL = 'https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/soil_moisture'
CACHE_FOLDER = "dwd_data"
YEAR = 2022
DEPTH_RANGE = '0-10'  # '20-30'
MIN_MOISTURE_LEVEL = 50  # in % nFK

# Regex zum Extrahieren der Jahreszahl aus DWD soil_moisture-Dateinamen.
_SM_YEAR_RE = re.compile(
    r"grids_germany_daily_soil_moisture_\w+_(\d{4})_.*\.nc$"
)


class MoistureDataService:
    """
    Handles downloading, reading, and transforming soil moisture/weather data.

    P3-1 (Issue #79): Jahres-Fallback ist dynamisch (zuletzt verfügbares
    Jahr), nicht mehr hart 2022. Der Feldstandort wird aus
    ``SimContext.field_coords`` gelesen, falls gesetzt. Ohne
    ``field_coords`` wird die alte Zufallskoordinate-Logik verwendet
    (Abwärtskompatibilität, Baseline bleibt stabil).
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

    def find_coordinate_at_coords(self, nc_file, lat, lon):
        """Find the nearest grid point to (lat, lon) in the netCDF file.

        P3-1 (Issue #79): Konfigurierbarer Feldstandort statt Zufall.
        Konvertiert WGS84 (lat, lon) → Gauss-Krueger (x, y) und sucht
        den nächstgelegenen Gitterpunkt.
        """
        # WGS84 → Gauss-Krueger (EPSG:31467)
        point_gdf = gpd.GeoDataFrame(
            geometry=gpd.points_from_xy([lon], [lat]),
            crs='EPSG:4326'
        )
        point_gk = point_gdf.to_crs('EPSG:31467')
        target_x = point_gk.geometry.x.iloc[0]
        target_y = point_gk.geometry.y.iloc[0]

        xs = nc_file.variables['x'][:]
        ys = nc_file.variables['y'][:]
        x_idx = int(np.argmin(np.abs(xs - target_x)))
        y_idx = int(np.argmin(np.abs(ys - target_y)))

        moisture_data = nc_file.variables['paws'][0, :, y_idx, x_idx]
        x_val = nc_file.variables['x'][x_idx]
        y_val = nc_file.variables['y'][y_idx]

        return {
            'x': x_val,
            'y': y_val,
            'moisture_data': moisture_data
        }

    def _find_latest_available_year(self) -> int:
        """Ermittelt das jüngste verfügbare Jahr im Cache-Ordner.

        Scannt ``dwd_data/`` nach soil_moisture-Dateien und liefert das
        maximale Jahr. Falls keine Dateien vorhanden: Fallback auf YEAR=2022.
        """
        cache_path = os.path.join(os.getcwd(), CACHE_FOLDER)
        if not os.path.isdir(cache_path):
            return YEAR
        available_years: list[int] = []
        for filename in os.listdir(cache_path):
            match = _SM_YEAR_RE.match(filename)
            if match:
                available_years.append(int(match.group(1)))
        if not available_years:
            return YEAR
        return max(available_years)

    def get_moisture_data(self, **kwargs):
        """
        Loads and returns the moisture data and coordinates.
        Falls back to dynamically latest available year if requested year
        is not available (P3-1, Issue #79: nicht mehr hart 2022).

        Falls ``SimContext.field_coords`` gesetzt ist, wird der
        konfigurierte Feldstandort verwendet (P3-1). Sonst wird die
        alte Zufallskoordinate-Logik verwendet (Abwärtskompatibilität).
        """
        year = kwargs.get('year', YEAR)
        depth_range = kwargs.get('depth_range', DEPTH_RANGE)

        try:
            nc_file_path = self.get_moisture_file(
                year=year, depth_range=depth_range)
            nc_file = netCDF4.Dataset(nc_file_path, 'r')
        except Exception as e:
            # P3-1 (Issue #79): Dynamischer Fallback auf jüngstes
            # verfügbares Jahr (nicht mehr hart YEAR=2022).
            fallback_year = self._find_latest_available_year()
            print(f"Warning: Moisture data for year {year} not available. "
                  f"Falling back to {fallback_year}. Error: {e}")
            year = fallback_year
            nc_file_path = self.get_moisture_file(
                year=year, depth_range=depth_range)
            nc_file = netCDF4.Dataset(nc_file_path, 'r')

        # P3-1 (Issue #79): Konfigurierbarer Feldstandort.
        # Falls field_coords gesetzt: nutze feste Koordinate.
        # Sonst: alte Zufallskoordinate-Logik (Baseline-Erhaltung).
        field_coords = getattr(self.context, 'field_coords', None)
        if field_coords is not None:
            lat, lon = field_coords
            moisture_object = self.find_coordinate_at_coords(
                nc_file, lat, lon)
        else:
            moisture_object = self.find_random_coordinate_with_date(nc_file)
            lat, lon = self.gauss_to_wgs84(
                moisture_object['x'], moisture_object['y'])

        return {
            'coords': [lat, lon],
            'dates': [datetime.date(year, 1, 1) + datetime.timedelta(days=i) for i in range(len(moisture_object['moisture_data']))],
            'moisture_data': moisture_object['moisture_data']
        }

    def get_moisture_data_dual_depth(self, **kwargs) -> dict:
        """Lädt Bodenfeuchte für 0-10cm und 20-30cm und interpoliert auf 15cm/30cm.

        DigiZert (NFK-Zertifikat) benötigt depth=15 und depth=30.
        DWD liefert 0-10 und 20-30. Interpolation:
            vwc_15 = (vwc_0_10 + vwc_20_30) / 2
            vwc_30 = vwc_20_30

        Returns:
            dict mit 'coords', 'dates', 'depth_15', 'depth_30' (jeweils Listen
            von täglichen VWC-Werten in %).
        """
        year = kwargs.get('year', YEAR)

        data_shallow = self.get_moisture_data(year=year, depth_range='0-10')
        data_deep = self.get_moisture_data(year=year, depth_range='20-30')

        vwc_0_10 = np.array(data_shallow['moisture_data'], dtype=float)
        vwc_20_30 = np.array(data_deep['moisture_data'], dtype=float)

        # Längen angleichen (Schaltjahr-Unterschiede o.ä.)
        min_len = min(len(vwc_0_10), len(vwc_20_30))
        vwc_0_10 = vwc_0_10[:min_len]
        vwc_20_30 = vwc_20_30[:min_len]

        # Interpolation
        vwc_15 = (vwc_0_10 + vwc_20_30) / 2.0
        vwc_30 = vwc_20_30

        dates = data_shallow['dates'][:min_len]

        return {
            'coords': data_shallow['coords'],
            'dates': dates,
            'depth_15': vwc_15.tolist(),
            'depth_30': vwc_30.tolist(),
        }