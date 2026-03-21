import datetime
import pytest
from unittest.mock import Mock, patch, MagicMock

from services.weather_adapters import OpenMeteoWeatherAdapter, DWDWeatherAdapter


class TestOpenMeteoWeatherAdapter:
    """Test suite for OpenMeteoWeatherAdapter (Issue #46)."""
    
    def test_adapter_initialization(self):
        """Test adapter can be initialized."""
        adapter = OpenMeteoWeatherAdapter(
            latitude=52.52,
            longitude=13.41
        )
        
        assert adapter.latitude == 52.52
        assert adapter.longitude == 13.41
        assert adapter.enabled is True
    
    def test_adapter_disabled(self):
        """Test adapter respects enabled flag."""
        adapter = OpenMeteoWeatherAdapter(
            latitude=52.52,
            longitude=13.41,
            enabled=False
        )
        
        assert adapter.is_available() is False
    
    @patch('services.weather_adapters.requests.get')
    def test_availability_check(self, mock_get):
        """Test availability check."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        adapter = OpenMeteoWeatherAdapter(
            latitude=52.52,
            longitude=13.41
        )
        
        assert adapter.is_available() is True
    
    @patch('services.weather_adapters.requests.get')
    def test_get_data_success(self, mock_get):
        """Test successful data retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "daily": {
                "time": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "temperature_2m_max": [5.0, 6.0, 7.0],
                "temperature_2m_min": [-1.0, 0.0, 1.0],
                "precipitation_sum": [0.0, 2.5, 0.0],
                "et0_fao_evapotranspiration": [1.0, 1.2, 1.1]
            }
        }
        mock_get.return_value = mock_response
        
        adapter = OpenMeteoWeatherAdapter(
            latitude=52.52,
            longitude=13.41
        )
        
        data = adapter.get_data(
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 1, 3)
        )
        
        assert "dates" in data
        assert "precipitation" in data
        assert "temperature_min" in data
        assert "temperature_max" in data
        assert "evapotranspiration" in data
        assert len(data["dates"]) == 3
        assert data["source"] == "open-meteo"
    
    def test_fallback_data(self):
        """Test fallback data generation."""
        adapter = OpenMeteoWeatherAdapter(
            latitude=52.52,
            longitude=13.41,
            enabled=False
        )
        
        data = adapter.get_fallback_data(
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 1, 31)
        )
        
        assert "dates" in data
        assert "precipitation" in data
        assert "temperature_min" in data
        assert "temperature_max" in data
        assert len(data["dates"]) == 31
        assert data["source"] == "fallback"
    
    def test_fallback_data_seasonal_variation(self):
        """Test that fallback data has seasonal temperature variation."""
        adapter = OpenMeteoWeatherAdapter(
            latitude=52.52,
            longitude=13.41,
            enabled=False
        )
        
        # Winter data
        winter_data = adapter.get_fallback_data(
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 1, 31)
        )
        
        # Summer data
        summer_data = adapter.get_fallback_data(
            start_date=datetime.date(2024, 7, 1),
            end_date=datetime.date(2024, 7, 31)
        )
        
        # Summer should be warmer than winter
        avg_winter_temp = sum(winter_data["temperature_max"]) / len(winter_data["temperature_max"])
        avg_summer_temp = sum(summer_data["temperature_max"]) / len(summer_data["temperature_max"])
        
        assert avg_summer_temp > avg_winter_temp
    
    @patch('services.weather_adapters.requests.get')
    def test_error_handling_fallback(self, mock_get):
        """Test that errors trigger fallback."""
        mock_get.side_effect = Exception("Network error")
        
        adapter = OpenMeteoWeatherAdapter(
            latitude=52.52,
            longitude=13.41
        )
        
        data = adapter.get_data(
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 1, 10)
        )
        
        # Should return fallback data
        assert data["source"] == "fallback"
        assert len(data["dates"]) == 10


class TestDWDWeatherAdapter:
    """Test suite for DWDWeatherAdapter (Issue #46)."""
    
    def test_dwd_adapter_not_implemented(self):
        """Test that DWD adapter is not yet implemented."""
        adapter = DWDWeatherAdapter(station_id="12345")
        
        assert adapter.is_available() is False
    
    def test_dwd_adapter_fallback(self):
        """Test that DWD adapter uses fallback."""
        adapter = DWDWeatherAdapter(station_id="12345")
        
        data = adapter.get_data(
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 1, 10),
            latitude=52.52,
            longitude=13.41
        )
        
        # Should return fallback data
        assert "dates" in data
        assert len(data["dates"]) == 10
