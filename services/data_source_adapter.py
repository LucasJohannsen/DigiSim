from abc import ABC, abstractmethod
from typing import Dict, Any


class DataSourceAdapter(ABC):
    """
    Abstract base class for external data source adapters.
    
    Provides a common interface for integrating external data sources
    (weather, sensors, soil parameters) into DigiSim.
    
    All adapters should:
    - Implement fallback to default/static data if unavailable
    - Handle errors gracefully
    - Return data in standardized format
    - Support configuration via constructor
    """
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the data source is available.
        
        Returns:
            True if data source can be accessed, False otherwise
        """
        pass
    
    @abstractmethod
    def get_data(self, **kwargs) -> Dict[str, Any]:
        """
        Fetch data from the external source.
        
        Args:
            **kwargs: Source-specific parameters
            
        Returns:
            Dictionary with standardized data format
        """
        pass
    
    @abstractmethod
    def get_fallback_data(self, **kwargs) -> Dict[str, Any]:
        """
        Get fallback data when external source is unavailable.
        
        Args:
            **kwargs: Source-specific parameters
            
        Returns:
            Dictionary with fallback data in same format as get_data()
        """
        pass


class WeatherDataAdapter(DataSourceAdapter):
    """
    Abstract adapter for weather data sources.
    
    Standardized output format:
    {
        'dates': [datetime.date, ...],
        'precipitation': [float, ...],  # mm per day
        'temperature_min': [float, ...],  # °C
        'temperature_max': [float, ...],  # °C
        'evapotranspiration': [float, ...]  # mm per day (optional)
    }
    """
    pass


class SoilDataAdapter(DataSourceAdapter):
    """
    Abstract adapter for soil parameter data.
    
    Standardized output format:
    {
        'soil_type': str,
        'field_capacity': float,  # % nFK
        'wilting_point': float,  # % nFK
        'organic_matter': float,  # % (optional)
        'ph': float  # (optional)
    }
    """
    pass


class SensorDataAdapter(DataSourceAdapter):
    """
    Abstract adapter for sensor data.
    
    Standardized output format:
    {
        'sensor_id': str,
        'timestamp': datetime.datetime,
        'measurements': {
            'soil_moisture': float,  # % or mm
            'leaf_wetness': float,  # % (optional)
            'temperature': float  # °C (optional)
        }
    }
    """
    pass
