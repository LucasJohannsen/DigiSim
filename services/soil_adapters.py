import json
import os
from typing import Dict, Any, Optional

from services.data_source_adapter import SoilDataAdapter
from utils.logger import get_logger

logger = get_logger("soil_adapters")


class ConfigFileSoilAdapter(SoilDataAdapter):
    """
    Soil parameter adapter that loads data from JSON configuration files.
    
    Supports per-field or per-farm soil parameter configuration.
    
    Configuration format:
    {
        "field_id": {
            "soil_type": "sandy_loam",
            "field_capacity": 180,  # % nFK
            "wilting_point": 80,    # % nFK
            "organic_matter": 2.5,  # %
            "ph": 6.5
        }
    }
    
    Usage:
        adapter = ConfigFileSoilAdapter(
            config_path="config/soil_parameters.json"
        )
        soil_data = adapter.get_data(field_id="12345")
    """
    
    DEFAULT_SOIL_PARAMS = {
        "soil_type": "medium_loam",
        "field_capacity": 200,
        "wilting_point": 100,
        "organic_matter": 2.0,
        "ph": 6.8
    }
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        enabled: bool = True
    ):
        """
        Initialize config file soil adapter.
        
        Args:
            config_path: Path to soil parameters JSON file
            enabled: Whether adapter is enabled
        """
        self.config_path = config_path or os.path.join(
            os.path.dirname(__file__),
            '../config/soil_parameters.json'
        )
        self.enabled = enabled
        self._config_cache: Optional[Dict] = None
    
    def is_available(self) -> bool:
        """
        Check if configuration file exists and is readable.
        """
        if not self.enabled:
            return False
        
        return os.path.exists(self.config_path) and os.path.isfile(self.config_path)
    
    def get_data(self, field_id: str, **kwargs) -> Dict[str, Any]:
        """
        Load soil parameters for a specific field.
        
        Args:
            field_id: Field ID to look up
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with soil parameters
        """
        if not self.enabled:
            logger.info("Soil adapter is disabled, using fallback")
            return self.get_fallback_data(field_id=field_id)
        
        try:
            config = self._load_config()
            
            # Look up field-specific parameters
            field_params = config.get(str(field_id))
            
            if field_params:
                logger.info(f"Loaded soil parameters for field {field_id}")
                return self._validate_params(field_params)
            else:
                logger.warning(
                    f"No soil parameters found for field {field_id}, using fallback"
                )
                return self.get_fallback_data(field_id=field_id)
                
        except Exception as e:
            logger.error(f"Failed to load soil parameters: {e}")
            return self.get_fallback_data(field_id=field_id)
    
    def _load_config(self) -> Dict:
        """
        Load configuration file with caching.
        """
        if self._config_cache is not None:
            return self._config_cache
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config_cache = json.load(f)
        
        return self._config_cache
    
    def _validate_params(self, params: Dict) -> Dict[str, Any]:
        """
        Validate and normalize soil parameters.
        """
        validated = self.DEFAULT_SOIL_PARAMS.copy()
        validated.update(params)
        
        # Ensure numeric values are floats
        for key in ['field_capacity', 'wilting_point', 'organic_matter', 'ph']:
            if key in validated:
                validated[key] = float(validated[key])
        
        validated['source'] = 'config_file'
        return validated
    
    def get_fallback_data(self, field_id: str = None, **kwargs) -> Dict[str, Any]:
        """
        Return default soil parameters.
        """
        logger.info(
            "Using default soil parameters",
            field_id=field_id
        )
        
        fallback = self.DEFAULT_SOIL_PARAMS.copy()
        fallback['source'] = 'fallback'
        return fallback
    
    def create_default_config(self) -> None:
        """
        Create a default soil parameters configuration file.
        
        Useful for initial setup.
        """
        default_config = {
            "example_field_1": {
                "soil_type": "sandy_loam",
                "field_capacity": 180,
                "wilting_point": 80,
                "organic_matter": 2.5,
                "ph": 6.5
            },
            "example_field_2": {
                "soil_type": "clay_loam",
                "field_capacity": 220,
                "wilting_point": 120,
                "organic_matter": 3.0,
                "ph": 7.0
            }
        }
        
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Created default soil parameters config at {self.config_path}")
