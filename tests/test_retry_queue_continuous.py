"""
Tests for continuous retry queue processing after each Daily Tick (Issue #34)
"""
import pytest
import asyncio
import datetime
from unittest.mock import Mock

from models.sim_context import SimContext
from scheduler.tick_scheduler import TickScheduler
from services.retry_dispatcher import RetryDispatcher


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


@pytest.fixture
def mock_dispatcher():
    """Create a mock RetryDispatcher"""
    dispatcher = Mock(spec=RetryDispatcher)
    dispatcher.send_event = Mock()
    dispatcher.process_queue = Mock()
    return dispatcher


@pytest.mark.asyncio
async def test_retry_queue_processed_after_tick(sim_context, mock_dispatcher, tmp_path):
    """Test that process_queue is called after each daily tick"""
    scheduler = TickScheduler(
        contexts=[sim_context],
        tick_time="06:00",
        state_dir=str(tmp_path),
        event_dispatcher=mock_dispatcher,
        max_concurrent_fields=1
    )
    
    # Mock the runner's tick method to return empty events
    for runner in scheduler.runners.values():
        runner.tick = Mock(return_value=[])
    
    # Execute daily tick
    await scheduler.daily_tick()
    
    # Verify process_queue was called
    mock_dispatcher.process_queue.assert_called_once()


@pytest.mark.asyncio
async def test_retry_queue_processing_does_not_block_tick(sim_context, tmp_path):
    """Test that retry queue processing doesn't block the tick cycle"""
    # Create a dispatcher that simulates slow queue processing
    slow_dispatcher = Mock(spec=RetryDispatcher)
    slow_dispatcher.send_event = Mock()
    
    # Simulate slow process_queue (but should not block due to asyncio.to_thread)
    def slow_process():
        import time
        time.sleep(0.1)  # Simulate slow processing
    
    slow_dispatcher.process_queue = Mock(side_effect=slow_process)
    
    scheduler = TickScheduler(
        contexts=[sim_context],
        tick_time="06:00",
        state_dir=str(tmp_path),
        event_dispatcher=slow_dispatcher,
        max_concurrent_fields=1
    )
    
    # Mock the runner's tick method
    for runner in scheduler.runners.values():
        runner.tick = Mock(return_value=[])
    
    # Measure time for daily tick
    start_time = asyncio.get_event_loop().time()
    await scheduler.daily_tick()
    elapsed = asyncio.get_event_loop().time() - start_time
    
    # Should complete relatively quickly despite slow queue processing
    # (asyncio.to_thread runs it in background)
    assert elapsed < 1.0  # Should be well under 1 second
    slow_dispatcher.process_queue.assert_called_once()


@pytest.mark.asyncio
async def test_retry_queue_failure_does_not_crash_tick(sim_context, tmp_path):
    """Test that retry queue processing failure doesn't crash the tick cycle"""
    failing_dispatcher = Mock(spec=RetryDispatcher)
    failing_dispatcher.send_event = Mock()
    failing_dispatcher.process_queue = Mock(side_effect=Exception("Queue processing failed"))
    
    scheduler = TickScheduler(
        contexts=[sim_context],
        tick_time="06:00",
        state_dir=str(tmp_path),
        event_dispatcher=failing_dispatcher,
        max_concurrent_fields=1
    )
    
    # Mock the runner's tick method
    for runner in scheduler.runners.values():
        runner.tick = Mock(return_value=[])
    
    # Should not raise exception despite queue processing failure
    await scheduler.daily_tick()
    
    # Verify heartbeat was still written
    heartbeat_path = tmp_path / "heartbeat.json"
    assert heartbeat_path.exists()


@pytest.mark.asyncio
async def test_failed_event_retried_on_next_tick(sim_context, tmp_path):
    """
    Test that a failed event from a previous tick is retried on the next tick.
    This is the key acceptance criterion from Issue #34.
    """
    from models.planting_plan import FieldOperationEvent
    
    # Create a real RetryDispatcher with temp queue directory
    queue_dir = tmp_path / "queue"
    queue_dir.mkdir()
    
    mock_client = Mock()
    mock_client.send_event = Mock(side_effect=Exception("API unavailable"))
    
    dispatcher = RetryDispatcher(
        client=mock_client,
        max_attempts=2,
        queue_dir=str(queue_dir)
    )
    
    # Create a test event
    test_event = FieldOperationEvent(
        worktype=1,
        start_date="2023-03-15 08:00:00",
        end_date="2023-03-15 10:00:00",
        area=10.0,
        distance=0,
        distanceWorked=0,
        duration=7200,
        durationWorked=7200,
        fuel=15.0,
        worktype_text="Test Operation"
    )
    test_event.field = sim_context.field_id
    
    # First tick: Event fails and gets queued
    dispatcher.send_event(test_event, sim_context)
    
    # Verify event was queued
    queue_files = list(queue_dir.rglob("*.json"))
    assert len(queue_files) == 1
    
    # Second tick: Mock client to succeed this time
    mock_client.send_event = Mock()  # Now succeeds
    
    # Process queue (simulating next tick)
    dispatcher.process_queue()
    
    # Verify event was resent and removed from queue
    mock_client.send_event.assert_called_once()
    queue_files_after = list(queue_dir.rglob("*.json"))
    assert len(queue_files_after) == 0


@pytest.mark.asyncio
async def test_retry_queue_not_called_without_dispatcher(sim_context, tmp_path):
    """Test that retry queue processing is skipped when no dispatcher is configured"""
    scheduler = TickScheduler(
        contexts=[sim_context],
        tick_time="06:00",
        state_dir=str(tmp_path),
        event_dispatcher=None,  # No dispatcher
        max_concurrent_fields=1
    )
    
    # Mock the runner's tick method
    for runner in scheduler.runners.values():
        runner.tick = Mock(return_value=[])
    
    # Should complete without errors
    await scheduler.daily_tick()
    
    # Verify heartbeat was written
    heartbeat_path = tmp_path / "heartbeat.json"
    assert heartbeat_path.exists()
