import datetime
from unittest.mock import Mock, patch
import pytest
import httpx

from models.planting_plan import FieldOperationEvent
from models.sim_context import SimContext
from services.digizert_client import DigiZertClient


@pytest.fixture
def mock_event():
    return FieldOperationEvent(
        batch="test-batch",
        field=123,
        worktype=5,
        exa_id=1,
        start_date="2024-03-15",
        end_date="2024-03-15",
        area=10.5,
        distance=100.0,
        distanceWorked=95.0,
        duration=2.5,
        durationWorked=2.3,
        fuel=15.5,
        application_type="fertilizer",
        application_category="nitrogen",
        application_name="NPK",
        application_amount=200.0,
        application_unit="kg/ha",
        worktype_text="Fertilization",
        machine="Tractor XYZ"
    )


@pytest.fixture
def mock_context():
    return SimContext(
        field_size=10.5,
        soil_type="loam",
        start_date=datetime.datetime(2024, 3, 1),
        crop_type="Potato",
        variety="Belana",
        field_id=123,
        field_name="Test Field",
        fuel_variation=0.1
    )


def test_send_event_posts_correct_payload(mock_event, mock_context):
    with patch('httpx.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = DigiZertClient("http://test-api/", "test-token")
        client.send_event(mock_event, mock_context)
        
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs["json"]
        
        assert payload["model"] == "pipeline.operation"
        assert payload["pk"] == 0
        assert payload["fields"]["field"] == mock_event.field
        assert payload["fields"]["worktype"] == mock_event.worktype
        assert payload["fields"]["start_date"] == mock_event.start_date
        assert payload["fields"]["end_date"] == mock_event.end_date
        assert payload["fields"]["area"] == mock_event.area
        assert payload["fields"]["fuel"] == mock_event.fuel
        assert payload["fields"]["worktype_text"] == mock_event.worktype_text


def test_send_event_sets_auth_header(mock_event, mock_context):
    with patch('httpx.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = DigiZertClient("http://test-api/", "my-secret-token")
        client.send_event(mock_event, mock_context)
        
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Token my-secret-token"
        assert headers["Content-Type"] == "application/json"


def test_send_event_uses_correct_url(mock_event, mock_context):
    with patch('httpx.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = DigiZertClient("http://test-api.com/operations/", "token")
        client.send_event(mock_event, mock_context)
        
        call_args = mock_post.call_args
        assert call_args.args[0] == "http://test-api.com/operations/"


def test_send_event_uses_timeout(mock_event, mock_context):
    with patch('httpx.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = DigiZertClient("http://test-api/", "token", timeout=15)
        client.send_event(mock_event, mock_context)
        
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["timeout"] == 15


def test_send_event_raises_on_4xx(mock_event, mock_context):
    with patch('httpx.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "Not Found",
                request=Mock(),
                response=mock_response
            )
        )
        mock_post.return_value = mock_response
        
        client = DigiZertClient("http://test-api/", "token")
        with pytest.raises(httpx.HTTPStatusError):
            client.send_event(mock_event, mock_context)


def test_send_event_raises_on_5xx(mock_event, mock_context):
    with patch('httpx.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "Internal Server Error",
                request=Mock(),
                response=mock_response
            )
        )
        mock_post.return_value = mock_response
        
        client = DigiZertClient("http://test-api/", "token")
        with pytest.raises(httpx.HTTPStatusError):
            client.send_event(mock_event, mock_context)


def test_send_event_raises_on_timeout(mock_event, mock_context):
    with patch('httpx.post', side_effect=httpx.TimeoutException("timeout")):
        client = DigiZertClient("http://test-api/", "token")
        with pytest.raises(httpx.TimeoutException):
            client.send_event(mock_event, mock_context)


def test_tick_scheduler_dispatches_events(mock_context):
    from scheduler.tick_scheduler import TickScheduler
    
    mock_dispatcher = Mock()
    
    with patch('scheduler.tick_scheduler.CalendarDrivenRunner') as MockRunner:
        mock_runner = Mock()
        event1 = FieldOperationEvent(field=1, worktype=1, start_date="2024-03-15")
        event2 = FieldOperationEvent(field=1, worktype=2, start_date="2024-03-15")
        mock_runner.tick.return_value = [event1, event2]
        mock_runner.context = mock_context
        MockRunner.return_value = mock_runner
        
        with patch('scheduler.tick_scheduler.StateManager'):
            scheduler = TickScheduler([mock_context], event_dispatcher=mock_dispatcher)
            scheduler.daily_tick()
            
            assert mock_dispatcher.send_event.call_count == 2
            mock_dispatcher.send_event.assert_any_call(event1, mock_context)
            mock_dispatcher.send_event.assert_any_call(event2, mock_context)


def test_tick_scheduler_works_without_dispatcher(mock_context):
    from scheduler.tick_scheduler import TickScheduler
    
    with patch('scheduler.tick_scheduler.CalendarDrivenRunner') as MockRunner:
        mock_runner = Mock()
        mock_runner.tick.return_value = [
            FieldOperationEvent(field=1, worktype=1, start_date="2024-03-15")
        ]
        mock_runner.context = mock_context
        MockRunner.return_value = mock_runner
        
        with patch('scheduler.tick_scheduler.StateManager'):
            scheduler = TickScheduler([mock_context])
            
            try:
                scheduler.daily_tick()
            except Exception as e:
                pytest.fail(f"TickScheduler without dispatcher raised exception: {e}")


def test_build_payload_structure(mock_event, mock_context):
    client = DigiZertClient("http://test-api/", "token")
    payload = client._build_payload(mock_event, mock_context)
    
    assert "model" in payload
    assert "pk" in payload
    assert "fields" in payload
    assert isinstance(payload["fields"], dict)
    
    fields = payload["fields"]
    assert "field" in fields
    assert "worktype" in fields
    assert "start_date" in fields
    assert "end_date" in fields
    assert "area" in fields
    assert "fuel" in fields
    assert "worktype_text" in fields
