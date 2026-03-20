"""
Tests for dynamic moisture year (Issue #35)
"""
import pytest
import datetime
from unittest.mock import Mock, patch, MagicMock
from models.sim_context import SimContext
from scheduler.calendar_driven_runner import CalendarDrivenRunner
from services.moisture_service import MoistureDataService


@pytest.fixture
def sim_context():
    return SimContext(
        field_id=1,
        field_name="Test Field",
        field_size=10.0,
        soil_type="sand",
        start_date=datetime.datetime(2023, 3, 15),
        crop_type="Potato",
        variety="Belana",
        fuel_variation=0.1
    )


def test_calendar_driven_runner_uses_current_date_year(sim_context):
    """Test that CalendarDrivenRunner passes the correct year from current_date"""
    runner = CalendarDrivenRunner(sim_context)
    
    # Mock MoistureDataService to capture the year parameter
    with patch('scheduler.calendar_driven_runner.MoistureDataService') as MockMoistureService:
        mock_ms_instance = Mock()
        mock_ms_instance.get_moisture_data.return_value = {
            'coords': [52.0, 13.0],
            'dates': [datetime.date(2023, 1, 1)],
            'moisture_data': [60.0]
        }
        MockMoistureService.return_value = mock_ms_instance
        
        # Simulate initialization at a specific date in 2023
        test_date = datetime.datetime(2023, 6, 15)
        runner._initialize_services(test_date)
        
        # Verify that get_moisture_data was called with year=2023
        mock_ms_instance.get_moisture_data.assert_called_once_with(
            year=2023,
            depth_range='0-10'
        )


def test_calendar_driven_runner_uses_different_years(sim_context):
    """Test that different simulation dates result in different years being used"""
    runner = CalendarDrivenRunner(sim_context)
    
    test_cases = [
        (datetime.datetime(2020, 1, 1), 2020),
        (datetime.datetime(2021, 6, 15), 2021),
        (datetime.datetime(2024, 12, 31), 2024),
    ]
    
    for test_date, expected_year in test_cases:
        with patch('scheduler.calendar_driven_runner.MoistureDataService') as MockMoistureService:
            mock_ms_instance = Mock()
            mock_ms_instance.get_moisture_data.return_value = {
                'coords': [52.0, 13.0],
                'dates': [datetime.date(expected_year, 1, 1)],
                'moisture_data': [60.0]
            }
            MockMoistureService.return_value = mock_ms_instance
            
            runner._initialize_services(test_date)
            
            # Verify correct year was passed
            mock_ms_instance.get_moisture_data.assert_called_with(
                year=expected_year,
                depth_range='0-10'
            )


def test_moisture_service_fallback_on_unavailable_year(sim_context):
    """Test that MoistureDataService falls back to default year when requested year is unavailable"""
    ms = MoistureDataService(sim_context)
    
    # Mock get_moisture_file to fail on first call (year 2050), succeed on second (fallback to 2022)
    with patch.object(ms, 'get_moisture_file') as mock_get_file:
        # First call fails (year 2050 not available)
        # Second call succeeds (fallback to 2022)
        mock_get_file.side_effect = [
            Exception("File not found"),  # First call fails
            "path/to/2022_file.nc"  # Second call succeeds
        ]
        
        # Mock netCDF4.Dataset
        with patch('services.moisture_service.netCDF4.Dataset') as mock_dataset:
            mock_nc = MagicMock()
            mock_nc.variables = {
                'x': MagicMock(__getitem__=lambda self, i: 1000.0),
                'y': MagicMock(__getitem__=lambda self, i: 2000.0),
                'paws': MagicMock(
                    __getitem__=lambda self, idx: MagicMock(mask=MagicMock(all=lambda: False)),
                    _FillValue=-999
                )
            }
            mock_dataset.return_value = mock_nc
            
            with patch.object(ms, 'find_random_coordinate_with_date') as mock_find:
                mock_find.return_value = {
                    'x': 1000.0,
                    'y': 2000.0,
                    'moisture_data': [60.0] * 365
                }
                
                # Request year 2050 (not available)
                result = ms.get_moisture_data(year=2050, depth_range='0-10')
                
                # Should have fallen back to 2022
                assert len(result['dates']) == 365
                assert result['dates'][0].year == 2022


def test_moisture_service_uses_provided_year_when_available(sim_context):
    """Test that MoistureDataService uses the provided year when data is available"""
    ms = MoistureDataService(sim_context)
    
    with patch.object(ms, 'get_moisture_file') as mock_get_file:
        mock_get_file.return_value = "path/to/2023_file.nc"
        
        with patch('services.moisture_service.netCDF4.Dataset') as mock_dataset:
            mock_nc = MagicMock()
            mock_nc.variables = {
                'x': MagicMock(__getitem__=lambda self, i: 1000.0),
                'y': MagicMock(__getitem__=lambda self, i: 2000.0),
                'paws': MagicMock(
                    __getitem__=lambda self, idx: MagicMock(mask=MagicMock(all=lambda: False)),
                    _FillValue=-999
                )
            }
            mock_dataset.return_value = mock_nc
            
            with patch.object(ms, 'find_random_coordinate_with_date') as mock_find:
                mock_find.return_value = {
                    'x': 1000.0,
                    'y': 2000.0,
                    'moisture_data': [60.0] * 365
                }
                
                result = ms.get_moisture_data(year=2023, depth_range='0-10')
                
                # Should use the requested year
                assert result['dates'][0].year == 2023
                mock_get_file.assert_called_with(year=2023, depth_range='0-10')
