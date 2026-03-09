import datetime
from unittest.mock import Mock, patch, call
import pytest

from models.sim_context import SimContext
from scheduler.tick_scheduler import TickScheduler


@pytest.fixture
def sample_contexts():
    return [
        SimContext(
            field_id=1,
            field_name="Field 1",
            field_size=10.0,
            soil_type="sand",
            start_date=datetime.datetime(2024, 10, 1),
            crop_type="Potato",
            variety="Belana",
            fuel_variation=0.1
        ),
        SimContext(
            field_id=2,
            field_name="Field 2",
            field_size=15.0,
            soil_type="sand",
            start_date=datetime.datetime(2024, 10, 1),
            crop_type="Potato",
            variety="Belana",
            fuel_variation=0.1
        )
    ]


def test_daily_tick_calls_tick_for_each_field(sample_contexts):
    """
    Test 1: daily_tick() ruft tick(today) für jedes Feld auf
    """
    with patch('scheduler.tick_scheduler.CalendarDrivenRunner') as MockRunner:
        mock_runner_1 = Mock()
        mock_runner_1.tick.return_value = []
        mock_runner_2 = Mock()
        mock_runner_2.tick.return_value = []
        
        MockRunner.side_effect = [mock_runner_1, mock_runner_2]
        
        scheduler = TickScheduler(sample_contexts)
        
        with patch('scheduler.tick_scheduler.datetime') as mock_datetime:
            mock_datetime.date.today.return_value = datetime.date(2024, 11, 15)
            
            scheduler.daily_tick()
            
            mock_runner_1.tick.assert_called_once_with(datetime.date(2024, 11, 15))
            mock_runner_2.tick.assert_called_once_with(datetime.date(2024, 11, 15))


def test_daily_tick_field_error_does_not_stop_others(sample_contexts):
    """
    Test 2: Fehler in einem Feld stoppt nicht andere Felder
    """
    with patch('scheduler.tick_scheduler.CalendarDrivenRunner') as MockRunner:
        mock_runner_1 = Mock()
        mock_runner_1.tick.side_effect = Exception("Field 1 error")
        mock_runner_2 = Mock()
        mock_runner_2.tick.return_value = []
        
        MockRunner.side_effect = [mock_runner_1, mock_runner_2]
        
        scheduler = TickScheduler(sample_contexts)
        
        with patch('scheduler.tick_scheduler.datetime') as mock_datetime:
            mock_datetime.date.today.return_value = datetime.date(2024, 11, 15)
            
            scheduler.daily_tick()
            
            mock_runner_1.tick.assert_called_once()
            mock_runner_2.tick.assert_called_once()


def test_tick_scheduler_creates_runner_per_context(sample_contexts):
    """
    Test 3: TickScheduler erstellt einen Runner pro SimContext
    """
    with patch('scheduler.tick_scheduler.CalendarDrivenRunner') as MockRunner:
        MockRunner.return_value = Mock()
        
        scheduler = TickScheduler(sample_contexts)
        
        assert len(scheduler.runners) == len(sample_contexts)
        assert 1 in scheduler.runners
        assert 2 in scheduler.runners


def test_daily_tick_passes_today_to_runners(sample_contexts):
    """
    Test 4: daily_tick() übergibt datetime.date.today() an jeden Runner
    """
    with patch('scheduler.tick_scheduler.CalendarDrivenRunner') as MockRunner:
        mock_runner = Mock()
        mock_runner.tick.return_value = []
        MockRunner.return_value = mock_runner
        
        scheduler = TickScheduler(sample_contexts)
        
        with patch('scheduler.tick_scheduler.datetime') as mock_datetime:
            test_date = datetime.date(2024, 12, 25)
            mock_datetime.date.today.return_value = test_date
            
            scheduler.daily_tick()
            
            for call_args in mock_runner.tick.call_args_list:
                assert call_args[0][0] == test_date


def test_tick_scheduler_parses_tick_time():
    """
    Test 5: TickScheduler parst tick_time korrekt
    """
    context = SimContext(
        field_id=1,
        field_name="Test",
        field_size=10.0,
        soil_type="sand",
        start_date=datetime.datetime(2024, 10, 1),
        crop_type="Potato",
        variety="Belana",
        fuel_variation=0.1
    )
    
    with patch('scheduler.tick_scheduler.CalendarDrivenRunner'):
        scheduler = TickScheduler([context], tick_time="14:30")
        
        assert scheduler.tick_hour == 14
        assert scheduler.tick_minute == 30


def test_tick_scheduler_default_tick_time():
    """
    Test 6: TickScheduler verwendet Standard-Zeit 06:00
    """
    context = SimContext(
        field_id=1,
        field_name="Test",
        field_size=10.0,
        soil_type="sand",
        start_date=datetime.datetime(2024, 10, 1),
        crop_type="Potato",
        variety="Belana",
        fuel_variation=0.1
    )
    
    with patch('scheduler.tick_scheduler.CalendarDrivenRunner'):
        scheduler = TickScheduler([context])
        
        assert scheduler.tick_hour == 6
        assert scheduler.tick_minute == 0
