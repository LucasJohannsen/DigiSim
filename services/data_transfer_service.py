"""Data-Transfer-Service: Konvertiert DigiSim-Daten in DigiZert-API-Format.

Kombiniert WeatherDataService und MoistureDataService zu Messwerten,
die der DigiZertDataClient an die API sendet.

S2 (SoilMoistureData): Tägliche VWC-Werte für 15cm + 30cm Tiefe.
S3 (WeatherData): Tägliche rain_fall + temperature.
"""

from __future__ import annotations

import datetime

from services.digizert_data_client import (
    SoilMoistureMeasurement,
    WeatherMeasurement,
)
from services.moisture_service import MoistureDataService
from services.weather_service import WeatherDataService
from utils.logger import get_logger

__all__ = ["DataTransferService"]

logger = get_logger("data_transfer_service")


class DataTransferService:
    """Sammelt und konvertiert tägliche Messwerte für den DigiZert-Transfer.

    Nutzt WeatherDataService (S3) und MoistureDataService (S2) um die
    Rohdaten in API-konforme Messwerte umzuwandeln.
    """

    def __init__(
        self,
        weather_service: WeatherDataService,
        moisture_service: MoistureDataService,
    ) -> None:
        self.weather_service = weather_service
        self.moisture_service = moisture_service

    def collect_weather_measurements(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> list[WeatherMeasurement]:
        """Sammelt WeatherData für einen Zeitraum.

        Args:
            start_date: Start-Datum (inklusiv).
            end_date: End-Datum (inklusiv).

        Returns:
            Liste von WeatherMeasurement, ein Eintrag pro Tag.
        """
        measurements: list[WeatherMeasurement] = []
        current = start_date
        while current <= end_date:
            try:
                wd = self.weather_service.get_weather_for_date(current)
                temperature = (
                    (wd.temperature_max_c + wd.temperature_min_c) / 2.0
                    if wd.temperature_max_c is not None and wd.temperature_min_c is not None
                    else None
                )
                measurements.append(
                    WeatherMeasurement(
                        timestamp=datetime.datetime.combine(current, datetime.time(0, 0)),
                        rain_fall=wd.precipitation_mm,
                        temperature=temperature,
                    )
                )
            except (IndexError, ValueError) as exc:
                logger.warning(
                    "Weather data missing for date, skipping",
                    date=str(current),
                    error=str(exc),
                )
            current += datetime.timedelta(days=1)
        return measurements

    def collect_soil_moisture_measurements(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        year: int,
    ) -> dict[int, list[SoilMoistureMeasurement]]:
        """Sammelt SoilMoistureData für 15cm und 30cm Tiefe.

        Args:
            start_date: Start-Datum (inklusiv).
            end_date: End-Datum (inklusiv).
            year: Simulationsjahr für DWD-Daten.

        Returns:
            dict mit depth (15, 30) → Liste von SoilMoistureMeasurement.
        """
        dual = self.moisture_service.get_moisture_data_dual_depth(year=year)
        dates: list[datetime.date] = dual["dates"]
        depth_15: list[float] = dual["depth_15"]
        depth_30: list[float] = dual["depth_30"]

        result: dict[int, list[SoilMoistureMeasurement]] = {15: [], 30: []}

        for i, date in enumerate(dates):
            if date < start_date or date > end_date:
                continue
            if i < len(depth_15):
                result[15].append(
                    SoilMoistureMeasurement(
                        timestamp=datetime.datetime.combine(date, datetime.time(0, 0)),
                        vwc=depth_15[i],
                    )
                )
            if i < len(depth_30):
                result[30].append(
                    SoilMoistureMeasurement(
                        timestamp=datetime.datetime.combine(date, datetime.time(0, 0)),
                        vwc=depth_30[i],
                    )
                )

        return result
