import datetime
import json
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
import httpx
from tenacity import wait_none

from models.planting_plan import FieldOperationEvent
from models.sim_context import SimContext
from services.retry_dispatcher import RetryDispatcher
from services.digizert_client import DigiZertClient


@pytest.fixture
def mock_event():
    return FieldOperationEvent(
        batch="test-batch",
        field=42,
        worktype=5,
        exa_id=1,
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
        field_name="Nordfeld",
        fuel_variation=0.1
    )


def make_fast_dispatcher(client, **kwargs):
    return RetryDispatcher(client, _wait_strategy=wait_none(), **kwargs)


def test_send_event_succeeds_on_first_attempt(tmp_path, mock_event, mock_context):
    mock_client = Mock()
    mock_client.send_event = Mock()
    
    dispatcher = make_fast_dispatcher(mock_client, queue_dir=str(tmp_path))
    dispatcher.send_event(mock_event, mock_context)
    
    mock_client.send_event.assert_called_once_with(mock_event, mock_context)
    queue_files = list(tmp_path.rglob("*.json"))
    assert len(queue_files) == 0


def test_send_event_queues_after_max_attempts(tmp_path, mock_event, mock_context):
    mock_client = Mock()
    mock_client.send_event.side_effect = httpx.TimeoutException("timeout")
    
    dispatcher = make_fast_dispatcher(mock_client, max_attempts=3, queue_dir=str(tmp_path))
    dispatcher.send_event(mock_event, mock_context)
    
    assert mock_client.send_event.call_count == 3
    queue_files = list(tmp_path.rglob("*.json"))
    assert len(queue_files) == 1


def test_send_event_succeeds_on_second_attempt(tmp_path, mock_event, mock_context):
    mock_client = Mock()
    mock_client.send_event.side_effect = [
        httpx.TimeoutException("timeout"),
        None
    ]
    
    dispatcher = make_fast_dispatcher(mock_client, max_attempts=3, queue_dir=str(tmp_path))
    dispatcher.send_event(mock_event, mock_context)
    
    assert mock_client.send_event.call_count == 2
    queue_files = list(tmp_path.rglob("*.json"))
    assert len(queue_files) == 0


def test_send_event_succeeds_on_third_attempt(tmp_path, mock_event, mock_context):
    mock_client = Mock()
    mock_client.send_event.side_effect = [
        httpx.TimeoutException("timeout"),
        httpx.HTTPStatusError("Server Error", request=Mock(), response=Mock()),
        None
    ]
    
    dispatcher = make_fast_dispatcher(mock_client, max_attempts=3, queue_dir=str(tmp_path))
    dispatcher.send_event(mock_event, mock_context)
    
    assert mock_client.send_event.call_count == 3
    queue_files = list(tmp_path.rglob("*.json"))
    assert len(queue_files) == 0


def test_queue_file_contains_correct_format(tmp_path, mock_event, mock_context):
    mock_client = Mock()
    mock_client.send_event.side_effect = httpx.TimeoutException("timeout")
    
    dispatcher = make_fast_dispatcher(mock_client, max_attempts=3, queue_dir=str(tmp_path))
    dispatcher.send_event(mock_event, mock_context)
    
    queue_files = list(tmp_path.rglob("*.json"))
    assert len(queue_files) == 1
    
    with open(queue_files[0], 'r') as f:
        data = json.load(f)
    
    assert "field_id" in data
    assert data["field_id"] == 42
    assert "failed_at" in data
    assert "event" in data
    assert "context" in data
    
    assert data["event"]["field"] == mock_event.field
    assert data["event"]["worktype"] == mock_event.worktype
    assert data["event"]["start_date"] == mock_event.start_date
    
    assert data["context"]["field_id"] == mock_context.field_id
    assert data["context"]["field_name"] == mock_context.field_name


def test_queue_file_stored_in_field_subdirectory(tmp_path, mock_event, mock_context):
    mock_client = Mock()
    mock_client.send_event.side_effect = httpx.TimeoutException("timeout")
    
    dispatcher = make_fast_dispatcher(mock_client, max_attempts=3, queue_dir=str(tmp_path))
    dispatcher.send_event(mock_event, mock_context)
    
    field_dir = tmp_path / "42"
    assert field_dir.exists()
    assert field_dir.is_dir()
    
    queue_files = list(field_dir.glob("*.json"))
    assert len(queue_files) == 1


def test_process_queue_resends_events(tmp_path, mock_event, mock_context):
    field_dir = tmp_path / "42"
    field_dir.mkdir(parents=True)
    
    queue_data = {
        "field_id": 42,
        "failed_at": "2024-03-15T08:30:05",
        "event": {
            "batch": mock_event.batch,
            "field": mock_event.field,
            "worktype": mock_event.worktype,
            "exa_id": mock_event.exa_id,
            "start_date": mock_event.start_date,
            "end_date": mock_event.end_date,
            "area": mock_event.area,
            "distance": mock_event.distance,
            "distanceWorked": mock_event.distanceWorked,
            "duration": mock_event.duration,
            "durationWorked": mock_event.durationWorked,
            "fuel": mock_event.fuel,
            "application_type": mock_event.application_type,
            "application_category": mock_event.application_category,
            "application_name": mock_event.application_name,
            "application_amount": mock_event.application_amount,
            "application_unit": mock_event.application_unit,
            "worktype_text": mock_event.worktype_text,
            "machine": mock_event.machine
        },
        "context": {
            "field_size": mock_context.field_size,
            "soil_type": mock_context.soil_type,
            "start_date": mock_context.start_date.isoformat(),
            "crop_type": mock_context.crop_type,
            "variety": mock_context.variety,
            "field_id": mock_context.field_id,
            "field_name": mock_context.field_name,
            "fuel_variation": mock_context.fuel_variation
        }
    }
    
    queue_file = field_dir / "2024-03-15T083005.json"
    with open(queue_file, 'w') as f:
        json.dump(queue_data, f)
    
    mock_client = Mock()
    mock_client.send_event = Mock()
    
    dispatcher = make_fast_dispatcher(mock_client, queue_dir=str(tmp_path))
    dispatcher.process_queue()
    
    assert mock_client.send_event.call_count == 1


def test_process_queue_deletes_on_success(tmp_path, mock_event, mock_context):
    field_dir = tmp_path / "42"
    field_dir.mkdir(parents=True)
    
    queue_data = {
        "field_id": 42,
        "failed_at": "2024-03-15T08:30:05",
        "event": {
            "batch": mock_event.batch,
            "field": mock_event.field,
            "worktype": mock_event.worktype,
            "exa_id": mock_event.exa_id,
            "start_date": mock_event.start_date,
            "end_date": mock_event.end_date,
            "area": mock_event.area,
            "distance": mock_event.distance,
            "distanceWorked": mock_event.distanceWorked,
            "duration": mock_event.duration,
            "durationWorked": mock_event.durationWorked,
            "fuel": mock_event.fuel,
            "application_type": mock_event.application_type,
            "application_category": mock_event.application_category,
            "application_name": mock_event.application_name,
            "application_amount": mock_event.application_amount,
            "application_unit": mock_event.application_unit,
            "worktype_text": mock_event.worktype_text,
            "machine": mock_event.machine
        },
        "context": {
            "field_size": mock_context.field_size,
            "soil_type": mock_context.soil_type,
            "start_date": mock_context.start_date.isoformat(),
            "crop_type": mock_context.crop_type,
            "variety": mock_context.variety,
            "field_id": mock_context.field_id,
            "field_name": mock_context.field_name,
            "fuel_variation": mock_context.fuel_variation
        }
    }
    
    queue_file = field_dir / "2024-03-15T083005.json"
    with open(queue_file, 'w') as f:
        json.dump(queue_data, f)
    
    mock_client = Mock()
    mock_client.send_event = Mock()
    
    dispatcher = make_fast_dispatcher(mock_client, queue_dir=str(tmp_path))
    dispatcher.process_queue()
    
    assert not queue_file.exists()


def test_process_queue_keeps_file_on_failure(tmp_path, mock_event, mock_context):
    field_dir = tmp_path / "42"
    field_dir.mkdir(parents=True)
    
    queue_data = {
        "field_id": 42,
        "failed_at": "2024-03-15T08:30:05",
        "event": {
            "batch": mock_event.batch,
            "field": mock_event.field,
            "worktype": mock_event.worktype,
            "exa_id": mock_event.exa_id,
            "start_date": mock_event.start_date,
            "end_date": mock_event.end_date,
            "area": mock_event.area,
            "distance": mock_event.distance,
            "distanceWorked": mock_event.distanceWorked,
            "duration": mock_event.duration,
            "durationWorked": mock_event.durationWorked,
            "fuel": mock_event.fuel,
            "application_type": mock_event.application_type,
            "application_category": mock_event.application_category,
            "application_name": mock_event.application_name,
            "application_amount": mock_event.application_amount,
            "application_unit": mock_event.application_unit,
            "worktype_text": mock_event.worktype_text,
            "machine": mock_event.machine
        },
        "context": {
            "field_size": mock_context.field_size,
            "soil_type": mock_context.soil_type,
            "start_date": mock_context.start_date.isoformat(),
            "crop_type": mock_context.crop_type,
            "variety": mock_context.variety,
            "field_id": mock_context.field_id,
            "field_name": mock_context.field_name,
            "fuel_variation": mock_context.fuel_variation
        }
    }
    
    queue_file = field_dir / "2024-03-15T083005.json"
    with open(queue_file, 'w') as f:
        json.dump(queue_data, f)
    
    mock_client = Mock()
    mock_client.send_event.side_effect = httpx.TimeoutException("timeout")
    
    dispatcher = make_fast_dispatcher(mock_client, max_attempts=3, queue_dir=str(tmp_path))
    dispatcher.process_queue()
    
    assert queue_file.exists()


def test_process_queue_empty_queue(tmp_path):
    mock_client = Mock()
    dispatcher = make_fast_dispatcher(mock_client, queue_dir=str(tmp_path))
    
    try:
        dispatcher.process_queue()
    except Exception as e:
        pytest.fail(f"process_queue() raised exception on empty queue: {e}")
    
    mock_client.send_event.assert_not_called()


def test_process_queue_handles_multiple_files(tmp_path, mock_event, mock_context):
    field_dir = tmp_path / "42"
    field_dir.mkdir(parents=True)
    
    queue_data = {
        "field_id": 42,
        "failed_at": "2024-03-15T08:30:05",
        "event": {
            "batch": mock_event.batch,
            "field": mock_event.field,
            "worktype": mock_event.worktype,
            "exa_id": mock_event.exa_id,
            "start_date": mock_event.start_date,
            "end_date": mock_event.end_date,
            "area": mock_event.area,
            "distance": mock_event.distance,
            "distanceWorked": mock_event.distanceWorked,
            "duration": mock_event.duration,
            "durationWorked": mock_event.durationWorked,
            "fuel": mock_event.fuel,
            "application_type": mock_event.application_type,
            "application_category": mock_event.application_category,
            "application_name": mock_event.application_name,
            "application_amount": mock_event.application_amount,
            "application_unit": mock_event.application_unit,
            "worktype_text": mock_event.worktype_text,
            "machine": mock_event.machine
        },
        "context": {
            "field_size": mock_context.field_size,
            "soil_type": mock_context.soil_type,
            "start_date": mock_context.start_date.isoformat(),
            "crop_type": mock_context.crop_type,
            "variety": mock_context.variety,
            "field_id": mock_context.field_id,
            "field_name": mock_context.field_name,
            "fuel_variation": mock_context.fuel_variation
        }
    }
    
    for i in range(3):
        queue_file = field_dir / f"2024-03-15T08300{i}.json"
        with open(queue_file, 'w') as f:
            json.dump(queue_data, f)
    
    mock_client = Mock()
    mock_client.send_event = Mock()
    
    dispatcher = make_fast_dispatcher(mock_client, queue_dir=str(tmp_path))
    dispatcher.process_queue()
    
    assert mock_client.send_event.call_count == 3
    queue_files = list(field_dir.glob("*.json"))
    assert len(queue_files) == 0
