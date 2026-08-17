import pytest
import asyncio
import datetime
from unittest.mock import Mock, patch
from pathlib import Path

from scheduler.tick_scheduler import TickScheduler
from models.sim_context import SimContext


@pytest.fixture
def multiple_contexts():
    return [
        SimContext(
            field_id=i,
            field_name=f"Field {i}",
            field_size=10.0,
            soil_type="sand",
            start_date=datetime.datetime(2024, 10, 1),
            crop_type="Potato",
            variety="Belana",
            fuel_variation=0.1
        )
        for i in range(1, 6)
    ]


@pytest.mark.asyncio
async def test_daily_tick_processes_all_fields(tmp_path, multiple_contexts):
    with patch('scheduler.tick_scheduler.CalendarDrivenRunner') as MockRunner:
        mock_runners = {}
        for ctx in multiple_contexts:
            mock_runner = Mock()
            mock_runner.tick.return_value = []
            mock_runner.context = ctx
            mock_runners[ctx.field_id] = mock_runner
        
        MockRunner.side_effect = lambda ctx, **kwargs: mock_runners[ctx.field_id]
        
        scheduler = TickScheduler(multiple_contexts, state_dir=str(tmp_path))
        await scheduler.daily_tick()
        
        for runner in mock_runners.values():
            runner.tick.assert_called_once()


@pytest.mark.asyncio
async def test_field_error_does_not_stop_others(tmp_path, multiple_contexts):
    with patch('scheduler.tick_scheduler.CalendarDrivenRunner') as MockRunner:
        mock_runners = {}
        for i, ctx in enumerate(multiple_contexts):
            mock_runner = Mock()
            if i == 2:
                mock_runner.tick.side_effect = Exception("Field 3 error")
            else:
                mock_runner.tick.return_value = []
            mock_runner.context = ctx
            mock_runners[ctx.field_id] = mock_runner
        
        MockRunner.side_effect = lambda ctx, **kwargs: mock_runners[ctx.field_id]
        
        scheduler = TickScheduler(multiple_contexts, state_dir=str(tmp_path))
        await scheduler.daily_tick()
        
        for runner in mock_runners.values():
            assert runner.tick.call_count == 1


@pytest.mark.asyncio
async def test_max_concurrent_fields_limits_parallelism(tmp_path):
    contexts = [
        SimContext(
            field_id=i,
            field_name=f"Field {i}",
            field_size=10.0,
            soil_type="sand",
            start_date=datetime.datetime(2024, 10, 1),
            crop_type="Potato",
            variety="Belana",
            fuel_variation=0.1
        )
        for i in range(1, 21)
    ]
    
    concurrent_count = 0
    max_concurrent = 0
    import threading
    lock = threading.Lock()
    
    def slow_tick(*args):
        import time
        nonlocal concurrent_count, max_concurrent
        with lock:
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
        time.sleep(0.01)
        with lock:
            concurrent_count -= 1
        return []
    
    with patch('scheduler.tick_scheduler.CalendarDrivenRunner') as MockRunner:
        mock_runners = {}
        for ctx in contexts:
            mock_runner = Mock()
            mock_runner.tick = slow_tick
            mock_runner.context = ctx
            mock_runners[ctx.field_id] = mock_runner
        
        MockRunner.side_effect = lambda ctx, **kwargs: mock_runners[ctx.field_id]
        
        scheduler = TickScheduler(contexts, state_dir=str(tmp_path), max_concurrent_fields=5)
        await scheduler.daily_tick()
        
        assert max_concurrent <= 5


def test_tick_scheduler_accepts_max_concurrent_fields(tmp_path):
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
        scheduler = TickScheduler([context], state_dir=str(tmp_path), max_concurrent_fields=15)
        assert scheduler.max_concurrent_fields == 15


@pytest.mark.asyncio
async def test_tick_summary_logs_success_count(tmp_path, multiple_contexts, caplog):
    import structlog.testing
    
    with structlog.testing.capture_logs() as logs:
        with patch('scheduler.tick_scheduler.CalendarDrivenRunner') as MockRunner, \
             patch('scheduler.tick_scheduler.StateManager') as MockStateManager:
            
            mock_state_manager = Mock()
            mock_state_manager.load.return_value = None
            mock_state_manager.save.return_value = None
            MockStateManager.return_value = mock_state_manager
            
            mock_runners = {}
            for i, ctx in enumerate(multiple_contexts):
                mock_runner = Mock()
                if i < 3:
                    mock_runner.tick.return_value = []
                else:
                    mock_runner.tick.side_effect = Exception("error")
                mock_runner.context = ctx
                mock_runners[ctx.field_id] = mock_runner
            
            MockRunner.side_effect = lambda ctx, **kwargs: mock_runners[ctx.field_id]
            
            scheduler = TickScheduler(multiple_contexts, state_dir=str(tmp_path))
            await scheduler.daily_tick()
    
    summary_logs = [l for l in logs if l.get("event") == "Tick summary"]
    assert len(summary_logs) == 1
    assert summary_logs[0]["successful"] == 3
    assert summary_logs[0]["total"] == 5
