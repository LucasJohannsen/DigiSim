"""DWD Wetter-Provider (P3-1, Issue #79).

Lädt DWD netCDF-Daten für Niederschlag, Wind und Temperatur aus dem
``dwd_data/``-Cache-Ordner. Fallback-Strategie:

1. Falls Dateien für das angeforderte Jahr vorhanden: direkt verwenden.
2. Falls nicht: dynamisch letztes verfügbares Jahr ermitteln (Scanne
   ``dwd_data/``, nimm max. Jahr mit vorhandenen Dateien).
3. Falls gar keine Wetter-Daten vorhanden: logge Warnung und falle auf
   ``SyntheticWeatherDataProvider`` zurück (Simulation läuft weiter).

Datei-Namenskonventionen (DWD grids_germany_daily):
- Niederschlag: ``grids_germany_daily_precipitation_<year>_v1.nc``
- Wind:         ``grids_germany_daily_wind_<year>_v1.nc``
- Temperatur:   ``grids_germany_daily_airtemp_<year>_v1.nc``

Bodenfeuchte wird aus den soil_moisture-Dateien extrahiert (analog
``MoistureDataService``), die bereits im ``dwd_data/``-Ordner liegen.
"""

from __future__ import annotations

import datetime
import os
import re

import netCDF4
import numpy as np

from services.providers.synthetic_weather_provider import (
    SyntheticWeatherDataProvider,
)
from services.weather_service import WeatherData
from utils.logger import get_logger

__all__ = ["DWDWeatherDataProvider"]

logger = get_logger("dwd_weather_provider")

_CACHE_FOLDER = "dwd_data"

# Datei-Namensmuster für die verschiedenen DWD-Datensätze.
_FILE_PATTERNS: dict[str, str] = {
    "precipitation": "grids_germany_daily_precipitation_{year}_v1.nc",
    "wind": "grids_germany_daily_wind_{year}_v1.nc",
    "airtemp": "grids_germany_daily_airtemp_{year}_v1.nc",
    "soil_moisture": (
        "grids_germany_daily_soil_moisture_grass_{year}_0-10_v1.nc"
    ),
}

# Regex zum Extrahieren der Jahreszahl aus DWD-Dateinamen.
_YEAR_RE = re.compile(r"grids_germany_daily_\w+_(\d{4})_.*\.nc$")


class DWDWeatherDataProvider:
    """Lädt DWD-Daten für Niederschlag, Wind, Temperatur und Bodenfeuchte.

    Fallback auf dynamisch letztes verfügbares Jahr (nicht hart 2022).
    Falls gar keine Wetter-Daten vorhanden: Fallback auf
    ``SyntheticWeatherDataProvider``.
    """

    def __init__(self, cache_folder: str = _CACHE_FOLDER) -> None:
        self.cache_folder = cache_folder
        self._synthetic_fallback = SyntheticWeatherDataProvider(seed=42)

    def get_weather_data(
        self,
        year: int,
        coords: tuple[float, float] | None = None,
    ) -> list[WeatherData]:
        """Liefert Wetterdaten für ein Jahr an einer Koordinate.

        Args:
            year: Angefordertes Simulationsjahr.
            coords: (lat, lon) der Feldkoordinate, oder None für Default.

        Returns:
            Liste von ``WeatherData`` für das gesamte Jahr.
        """
        if coords is None:
            coords = (52.5, 9.9)

        # Ermittle das tatsächlich zu verwendende Jahr (Fallback dynamisch).
        effective_year = self._resolve_year(year)
        if effective_year is None:
            logger.warning(
                "No DWD weather data found in %s, falling back to "
                "SyntheticWeatherDataProvider",
                self.cache_folder,
            )
            return self._synthetic_fallback.get_weather_data(year, coords)

        if effective_year != year:
            logger.info(
                "DWD data for year %d not available, using %d instead",
                year,
                effective_year,
            )

        try:
            return self._load_and_assemble(effective_year, coords)
        except (FileNotFoundError, OSError, ValueError) as exc:
            logger.warning(
                "Failed to load DWD data for year %d: %s. "
                "Falling back to SyntheticWeatherDataProvider.",
                effective_year,
                exc,
            )
            return self._synthetic_fallback.get_weather_data(year, coords)

    def _resolve_year(self, requested_year: int) -> int | None:
        """Ermittelt das zu verwendende Jahr.

        Falls Dateien für ``requested_year`` vorhanden: direkt zurück.
        Sonst: dynamisch letztes verfügbares Jahr.
        Falls gar keine Daten: None (Caller nutzt Synthetic).
        """
        if self._has_all_files(requested_year):
            return requested_year
        return self._find_latest_available_year()

    def _has_all_files(self, year: int) -> bool:
        """Prüft, ob alle benötigten Dateien für ein Jahr vorhanden sind."""
        for pattern in _FILE_PATTERNS.values():
            filepath = os.path.join(self.cache_folder, pattern.format(year=year))
            if not os.path.exists(filepath):
                return False
        return True

    def _find_latest_available_year(self) -> int | None:
        """Ermittelt das jüngste Jahr, für das alle Dateien vorhanden sind.

        Scannt ``dwd_data/`` nach ``grids_germany_daily_*_<year>_*.nc``
        und liefert das maximale Jahr, für das **alle** benötigten
        Datei-Typen (precipitation, wind, airtemp, soil_moisture)
        vorhanden sind.

        Returns:
            Jüngstes verfügbares Jahr, oder None falls keines vorhanden.
        """
        if not os.path.isdir(self.cache_folder):
            return None

        # Sammle alle Jahre, die im Ordner vorkommen.
        available_years: set[int] = set()
        for filename in os.listdir(self.cache_folder):
            if not filename.endswith(".nc"):
                continue
            match = _YEAR_RE.match(filename)
            if match:
                available_years.add(int(match.group(1)))

        # Finde das jüngste Jahr, für das alle Dateien vorhanden sind.
        for year in sorted(available_years, reverse=True):
            if self._has_all_files(year):
                return year

        return None

    def _load_and_assemble(
        self, year: int, coords: tuple[float, float]
    ) -> list[WeatherData]:
        """Lädt alle DWD-Dateien für ein Jahr und baut WeatherData-Liste.

        Extrahiert die Werte an der gegebenen Koordinate (lat, lon).
        """
        lat, lon = coords

        # Niederschlag
        precip_data = self._extract_from_nc(
            year, "precipitation", lat, lon, var_name="precipitation"
        )
        # Wind
        wind_data = self._extract_from_nc(
            year, "wind", lat, lon, var_name="wind_speed"
        )
        # Temperatur (min/max)
        temp_min_data = self._extract_from_nc(
            year, "airtemp", lat, lon, var_name="temperature_min"
        )
        temp_max_data = self._extract_from_nc(
            year, "airtemp", lat, lon, var_name="temperature_max"
        )
        # Bodenfeuchte
        moisture_data = self._extract_from_nc(
            year, "soil_moisture", lat, lon, var_name="paws"
        )

        # Datenlänge bestimmen (alle Arrays sollten gleich lang sein).
        n_days = min(
            len(precip_data),
            len(wind_data),
            len(temp_min_data),
            len(temp_max_data),
            len(moisture_data),
        )

        start = datetime.date(year, 1, 1)
        result: list[WeatherData] = []
        for i in range(n_days):
            date = start + datetime.timedelta(days=i)
            result.append(
                WeatherData(
                    date=date,
                    precipitation_mm=float(precip_data[i]),
                    wind_speed_ms=float(wind_data[i]),
                    temperature_max_c=float(temp_max_data[i]),
                    temperature_min_c=float(temp_min_data[i]),
                    soil_moisture_pct_nfk=float(moisture_data[i]),
                )
            )

        # Falls Daten kürzer als 365 Tage: mit Synthetic auffüllen.
        expected_days = (
            datetime.date(year, 12, 31) - datetime.date(year, 1, 1)
        ).days + 1
        if n_days < expected_days:
            logger.warning(
                "DWD data for year %d has only %d days (expected %d), "
                "filling remaining days with synthetic data",
                year,
                n_days,
                expected_days,
            )
            synthetic = self._synthetic_fallback.get_weather_data(year, coords)
            result.extend(synthetic[n_days:])

        return result

    def _extract_from_nc(
        self,
        year: int,
        dataset_key: str,
        lat: float,
        lon: float,
        var_name: str,
    ) -> np.ndarray:
        """Extrahiert eine Zeitreihe an (lat, lon) aus einer netCDF-Datei.

        Findet den nächstgelegenen Gitterpunkt und liefert die Werte
        über alle Zeitschritte.
        """
        pattern = _FILE_PATTERNS[dataset_key]
        filepath = os.path.join(self.cache_folder, pattern.format(year=year))

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"DWD file not found: {filepath}")

        nc = netCDF4.Dataset(filepath, "r")

        try:
            # Koordinaten finden: DWD-Grids verwenden lat/lon oder x/y.
            if "lat" in nc.variables and "lon" in nc.variables:
                lats = nc.variables["lat"][:]
                lons = nc.variables["lon"][:]
                # Für 1D-Koordinaten (reguläres Grid)
                if lats.ndim == 1 and lons.ndim == 1:
                    lat_idx = int(np.argmin(np.abs(lats - lat)))
                    lon_idx = int(np.argmin(np.abs(lons - lon)))
                    data = nc.variables[var_name][:, lat_idx, lon_idx]
                else:
                    # 2D-Koordinaten
                    dist = (lats - lat) ** 2 + (lons - lon) ** 2
                    idx = np.unravel_index(np.argmin(dist), dist.shape)
                    data = nc.variables[var_name][:, idx[0], idx[1]]
            elif "x" in nc.variables and "y" in nc.variables:
                # Gauss-Krueger Koordinaten – näherungsweise über Indizes.
                xs = nc.variables["x"][:]
                ys = nc.variables["y"][:]
                x_idx = int(np.argmin(np.abs(xs - lon * 1000)))
                y_idx = int(np.argmin(np.abs(ys - lat * 1000)))
                data = nc.variables[var_name][:, y_idx, x_idx]
            else:
                raise ValueError(
                    f"Unknown coordinate system in {filepath}"
                )

            # Maskierte Werte durch 0 ersetzen (für fehlende Datenpunkte).
            if np.ma.is_masked(data):
                data = data.filled(0.0)

            return np.asarray(data, dtype=float)
        finally:
            nc.close()
