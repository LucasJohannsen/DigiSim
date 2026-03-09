import json
import datetime
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
import httpx
import structlog.testing

from models.planting_plan import FieldOperationEvent
from models.sim_context import SimContext
from utils.logger import setup_logging, get_logger
from scheduler.tick_scheduler import TickScheduler
from services.retry_dispatcher import RetryDispatcher
from services.digizert_client import DigiZertClient


@pytest.fixture
def mock_event():
    return FieldOperationEvent(
        field=42,
        worktype=5,
        start_date="2024-03-15",
        end_date="2024-03-15",
        area=10.5,
        fuel=15.5,
        worktype_text="Fertilization"
    )


@pytest.fixture
def mock_context():
    return SimContext(
        field_size=10.5,
        soil_type="loam",
        start_date=datetime.datetime(2024, 3, 1),
        crop_type="Potato",
        variety="Belana",
        field_id=42,
        field_name="Test Field",
        fuel_variation=0.1
    )


def test_tick_scheduler_logs_tick_completed(mock_context):
    with structlog.testing.capture_logs() as logs:
        with patch('scheduler.tick_scheduler.CalendarDrivenRunner') as MockRunner:
            mock_runner = Mock()
            mock_runner.tick.return_value = [Mock(), Mock()]
            mock_runner.context = mock_context
            MockRunner.return_value = mock_runner
            
            with patch('scheduler.tick_scheduler.StateManager'):
                scheduler = TickScheduler([mock_context])
                scheduler.daily_tick()
    
    tick_logs = [l for l in logs if l.get("event") == "Tick completed"]
    assert len(tick_logs) == 1
    assert tick_logs[0]["field_id"] == 42
    assert tick_logs[0]["events_sent"] == 2
    assert "tick_date" in tick_logs[0]


def test_tick_scheduler_logs_state_restored(mock_context):
    with structlog.testing.capture_logs() as logs:
        with patch('scheduler.tick_scheduler.CalendarDrivenRunner') as MockRunner:
            mock_runner = Mock()
            MockRunner.return_value = mock_runner
            
            with patch('scheduler.tick_scheduler.StateManager') as MockStateManager:
                mock_state_manager = Mock()
                mock_snapshot = Mock()
                mock_snapshot.last_tick_date = datetime.date(2024, 3, 14)
                mock_state_manager.load.return_value = mock_snapshot
                MockStateManager.return_value = mock_state_manager
                
                scheduler = TickScheduler([mock_context])
    
    state_logs = [l for l in logs if l.get("event") == "State restored"]
    assert len(state_logs) == 1
    assert state_logs[0]["field_id"] == 42
    assert "last_tick_date" in state_logs[0]


def test_tick_scheduler_logs_tick_failed(mock_context):
    with structlog.testing.capture_logs() as logs:
        with patch('scheduler.tick_scheduler.CalendarDrivenRunner') as MockRunner:
            mock_runner = Mock()
            mock_runner.tick.side_effect = Exception("Test error")
            mock_runner.context = mock_context
            MockRunner.return_value = mock_runner
            
            with patch('scheduler.tick_scheduler.StateManager'):
                scheduler = TickScheduler([mock_context])
                scheduler.daily_tick()
    
    error_logs = [l for l in logs if l.get("event") == "Tick failed"]
    assert len(error_logs) == 1
    assert error_logs[0]["field_id"] == 42
    assert "error" in error_logs[0]


def test_retry_dispatcher_logs_retry_attempt(tmp_path, mock_event, mock_context):
    with structlog.testing.capture_logs() as logs:
        mock_client = Mock()
        mock_client.send_event.side_effect = [
            httpx.TimeoutException("timeout"),
            None
        ]
        
        from tenacity import wait_none
        dispatcher = RetryDispatcher(mock_client, max_attempts=3, queue_dir=str(tmp_path), _wait_strategy=wait_none())
        dispatcher.send_event(mock_event, mock_context)
    
    retry_logs = [l for l in logs if l.get("event") == "Retry attempt"]
    assert len(retry_logs) >= 1
    assert "attempt" in retry_logs[0]
    assert "error" in retry_logs[0]
    assert retry_logs[0]["max_attempts"] == 3


def test_retry_dispatcher_logs_event_queued(tmp_path, mock_event, mock_context):
    with structlog.testing.capture_logs() as logs:
        mock_client = Mock()
        mock_client.send_event.side_effect = httpx.TimeoutException("timeout")
        
        from tenacity import wait_none
        dispatcher = RetryDispatcher(
            mock_client,
            max_attempts=3,
            queue_dir=str(tmp_path),
            _wait_strategy=wait_none()
        )
        dispatcher.send_event(mock_event, mock_context)
    
    queue_logs = [l for l in logs if l.get("event") == "Event queued"]
    assert len(queue_logs) == 1
    assert "queue_file" in queue_logs[0]


def test_retry_dispatcher_logs_all_attempts_failed(tmp_path, mock_event, mock_context):
    with structlog.testing.capture_logs() as logs:
        mock_client = Mock()
        mock_client.send_event.side_effect = httpx.TimeoutException("timeout")
        
        from tenacity import wait_none
        dispatcher = RetryDispatcher(
            mock_client,
            max_attempts=3,
            queue_dir=str(tmp_path),
            _wait_strategy=wait_none()
        )
        dispatcher.send_event(mock_event, mock_context)
    
    error_logs = [l for l in logs if l.get("event") == "All retry attempts failed"]
    assert len(error_logs) == 1
    assert error_logs[0]["max_attempts"] == 3
    assert "error" in error_logs[0]


def test_setup_logging_outputs_valid_json():
    with structlog.testing.capture_logs() as logs:
        logger = get_logger("test")
        logger.info("Test message", field_id=1)
    
    assert len(logs) == 1
    log_entry = logs[0]
    # capture_logs captures before processors run, so fields are pre-processing
    assert log_entry["log_level"] == "info"
    assert log_entry["event"] == "Test message"
    assert log_entry["field_id"] == 1


def test_log_level_filters_info_logs(capsys):
    import logging
    
    # Reset and configure with WARNING level
    structlog.reset_defaults()
    logging.root.handlers = []
    setup_logging(log_level="WARNING")
    
    logger = get_logger("test")
    logger.info("Should not appear")
    logger.warning("Should appear", test_field="value")
    
    captured = capsys.readouterr()
    lines = [line for line in captured.out.strip().split("\n") if line]
    
    # Only WARNING should appear, INFO should be filtered
    assert len(lines) == 1
    log_entry = json.loads(lines[0])
    assert log_entry["level"] == "warning"
    assert log_entry["event"] == "Should appear"
    assert log_entry["service"] == "test"
    assert "Should not appear" not in captured.out


def test_setup_logging_writes_to_file(tmp_path):
    import logging
    import time
    
    log_file = tmp_path / "logs" / "test.log"
    
    # Reset structlog to avoid test interference
    structlog.reset_defaults()
    logging.root.handlers = []
    
    setup_logging(log_level="INFO", log_file=str(log_file))
    logger = structlog.get_logger("test_file")
    logger.info("File test", field_id=99)
    
    # Flush handlers carefully
    for handler in logging.root.handlers:
        try:
            handler.flush()
        except (ValueError, OSError):
            pass
    
    # Small delay to ensure write completes
    time.sleep(0.1)
    
    # Verify file was created
    assert log_file.exists()


def test_digizert_client_logs_event_dispatched(mock_event, mock_context):
    with structlog.testing.capture_logs() as logs:
        with patch('httpx.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            client = DigiZertClient("http://test-api/", "token")
            client.send_event(mock_event, mock_context)
    
    dispatch_logs = [l for l in logs if l.get("event") == "Event dispatched"]
    assert len(dispatch_logs) == 1
    assert dispatch_logs[0]["field"] == 42
    assert dispatch_logs[0]["worktype"] == 5


def test_tick_scheduler_logs_started(mock_context):
    with structlog.testing.capture_logs() as logs:
        with patch('scheduler.tick_scheduler.CalendarDrivenRunner'):
            with patch('scheduler.tick_scheduler.StateManager'):
                scheduler = TickScheduler([mock_context])
                
                with patch.object(scheduler.scheduler, 'start'):
                    with patch('time.sleep', side_effect=KeyboardInterrupt):
                        try:
                            scheduler.start()
                        except KeyboardInterrupt:
                            pass
    
    start_logs = [l for l in logs if l.get("event") == "TickScheduler started"]
    assert len(start_logs) == 1
    assert start_logs[0]["field_count"] == 1
    assert start_logs[0]["tick_time"] == "06:00"


def test_tick_scheduler_logs_stopped(mock_context):
    with structlog.testing.capture_logs() as logs:
        with patch('scheduler.tick_scheduler.CalendarDrivenRunner'):
            with patch('scheduler.tick_scheduler.StateManager'):
                scheduler = TickScheduler([mock_context])
                scheduler._running = False
                scheduler.scheduler = Mock()
                scheduler.scheduler.running = True
                scheduler.stop()
    
    stop_logs = [l for l in logs if l.get("event") == "TickScheduler stopped"]
    assert len(stop_logs) == 1
