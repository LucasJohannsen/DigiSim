import datetime
import os
from typing import Dict, Any, List, Optional
import requests

from services.data_source_adapter import WeatherDataAdapter
from utils.logger import get_logger

logger = get_logger("weather_adapters")


class OpenMeteoWeatherAdapter(WeatherDataAdapter):
    """
    Weather data adapter using Open-Meteo API.
    
    Open-Meteo provides free weather data without API key requirement.
    
    Features:
    - Historical weather data
    - Weather forecasts
    - No API key required
    - Free for non-commercial use
    
    Usage:
        adapter = OpenMeteoWeatherAdapter(
            latitude=52.52,
            longitude=13.41
        )
        weather_data = adapter.get_data(
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 12, 31)
        )
    """
    
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
    
    def __init__(
        self,
        latitude: float,
        longitude: float,
        enabled: bool = True,
        timeout: int = 10
    ):
        """
        Initialize Open-Meteo weather adapter.
        
        Args:
            latitude: Latitude of location
            longitude: Longitude of location
            enabled: Whether adapter is enabled (can be disabled via config)
            timeout: Request timeout in seconds
        """
        self.latitude = latitude
        self.longitude = longitude
        self.enabled = enabled
        self.timeout = timeout
    
    def is_available(self) -> bool:
        """
        Check if Open-Meteo API is available.
        """
        if not self.enabled:
            return False
        
        try:
            response = requests.get(
                self.BASE_URL,
                params={
                    "latitude": self.latitude,
                    "longitude": self.longitude,
                    "daily": "temperature_2m_max",
                    "forecast_days": 1
                },
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Open-Meteo availability check failed: {e}")
            return False
    
    def get_data(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch weather data from Open-Meteo.
        
        Args:
            start_date: Start date for weather data
            end_date: End date for weather data
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with weather data in standardized format
        """
        if not self.enabled:
            logger.info("Open-Meteo adapter is disabled, using fallback")
            return self.get_fallback_data(start_date=start_date, end_date=end_date)
        
        try:
            # Determine if we need historical or forecast data
            today = datetime.date.today()
            
            if end_date < today:
                # Historical data
                url = self.ARCHIVE_URL
            else:
                # Forecast or mixed
                url = self.BASE_URL
            
            params = {
                "latitude": self.latitude,
                "longitude": self.longitude,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "daily": [
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_sum",
                    "et0_fao_evapotranspiration"
                ],
                "timezone": "Europe/Berlin"
            }
            
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            return self._parse_response(data)
            
        except Exception as e:
            logger.error(f"Failed to fetch Open-Meteo data: {e}")
            return self.get_fallback_data(start_date=start_date, end_date=end_date)
    
    def _parse_response(self, data: Dict) -> Dict[str, Any]:
        """
        Parse Open-Meteo API response into standardized format.
        """
        daily = data.get("daily", {})
        
        dates = [
            datetime.datetime.fromisoformat(d).date()
            for d in daily.get("time", [])
        ]
        
        return {
            "dates": dates,
            "precipitation": daily.get("precipitation_sum", []),
            "temperature_min": daily.get("temperature_2m_min", []),
            "temperature_max": daily.get("temperature_2m_max", []),
            "evapotranspiration": daily.get("et0_fao_evapotranspiration", []),
            "source": "open-meteo",
            "latitude": self.latitude,
            "longitude": self.longitude
        }
    
    def get_fallback_data(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate synthetic fallback weather data.
        
        Uses simple patterns to generate realistic-looking data.
        """
        import random
        
        dates = []
        precipitation = []
        temp_min = []
        temp_max = []
        evapotranspiration = []
        
        current_date = start_date
        while current_date <= end_date:
            dates.append(current_date)
            
            # Seasonal temperature variation
            day_of_year = current_date.timetuple().tm_yday
            base_temp = 10 + 15 * (1 - abs((day_of_year - 180) / 180))
            
            temp_min.append(base_temp - 5 + random.uniform(-3, 3))
            temp_max.append(base_temp + 5 + random.uniform(-3, 3))
            
            # Random precipitation (20% chance of rain)
            if random.random() < 0.2:
                precipitation.append(random.uniform(2, 20))
            else:
                precipitation.append(0)
            
            # Simple evapotranspiration model
            evapotranspiration.append(2 + random.uniform(0, 3))
            
            current_date += datetime.timedelta(days=1)
        
        logger.info(
            "Using fallback weather data",
            start_date=start_date,
            end_date=end_date,
            days=len(dates)
        )
        
        return {
            "dates": dates,
            "precipitation": precipitation,
            "temperature_min": temp_min,
            "temperature_max": temp_max,
            "evapotranspiration": evapotranspiration,
            "source": "fallback",
            "latitude": self.latitude,
            "longitude": self.longitude
        }


class DWDWeatherAdapter(WeatherDataAdapter):
    """
    Weather data adapter using DWD (Deutscher Wetterdienst) Open Data.
    
    This is a placeholder for future DWD integration.
    DWD provides high-quality German weather data but requires more
    complex parsing of various file formats.
    """
    
    def __init__(self, station_id: str, enabled: bool = False):
        self.station_id = station_id
        self.enabled = enabled
    
    def is_available(self) -> bool:
        return False  # Not yet implemented
    
    def get_data(self, **kwargs) -> Dict[str, Any]:
        logger.warning("DWD adapter not yet implemented, using fallback")
        return self.get_fallback_data(**kwargs)
    
    def get_fallback_data(self, **kwargs) -> Dict[str, Any]:
        # Use OpenMeteo fallback as default
        adapter = OpenMeteoWeatherAdapter(
            latitude=kwargs.get("latitude", 52.52),
            longitude=kwargs.get("longitude", 13.41),
            enabled=False
        )
        return adapter.get_fallback_data(**kwargs)
