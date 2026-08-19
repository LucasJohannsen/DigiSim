import pytest
import json
import datetime
from unittest.mock import Mock, patch
import signal

from config.settings import load_and_validate_config, load_sim_contexts, DaemonConfig
from models.sim_context import SimContext
import daemon as daemon_module


def test_load_config_with_required_env_vars(monkeypatch):
    monkeypatch.setenv("DIGIZERT_API_URL", "http://api.test/")
    monkeypatch.setenv("DIGIZERT_API_TOKEN", "token123")
    monkeypatch.setenv("FARM_ID", "7")
    
    config = load_and_validate_config()
    
    assert config.api_url == "http://api.test/"
    assert config.api_token == "token123"
    assert config.farm_id == 7


def test_missing_api_url_raises_value_error(monkeypatch):
    monkeypatch.delenv("DIGIZERT_API_URL", raising=False)
    monkeypatch.setenv("DIGIZERT_API_TOKEN", "token")
    monkeypatch.setenv("FARM_ID", "7")
    
    with pytest.raises(ValueError, match="DIGIZERT_API_URL"):
        load_and_validate_config()


def test_missing_api_token_raises_value_error(monkeypatch):
    monkeypatch.setenv("DIGIZERT_API_URL", "http://api.test/")
    monkeypatch.delenv("DIGIZERT_API_TOKEN", raising=False)
    monkeypatch.setenv("FARM_ID", "7")
    
    with pytest.raises(ValueError, match="DIGIZERT_API_TOKEN"):
        load_and_validate_config()


def test_missing_farm_id_raises_value_error(monkeypatch):
    monkeypatch.setenv("DIGIZERT_API_URL", "http://api.test/")
    monkeypatch.setenv("DIGIZERT_API_TOKEN", "token")
    monkeypatch.delenv("FARM_ID", raising=False)
    
    with pytest.raises(ValueError, match="FARM_ID"):
        load_and_validate_config()


def test_all_required_missing_lists_all(monkeypatch):
    monkeypatch.delenv("DIGIZERT_API_URL", raising=False)
    monkeypatch.delenv("DIGIZERT_API_TOKEN", raising=False)
    monkeypatch.delenv("FARM_ID", raising=False)
    
    with pytest.raises(ValueError) as exc_info:
        load_and_validate_config()
    
    assert "DIGIZERT_API_URL" in str(exc_info.value)
    assert "DIGIZERT_API_TOKEN" in str(exc_info.value)
    assert "FARM_ID" in str(exc_info.value)


def test_load_sim_contexts_returns_correct_count(monkeypatch, tmp_path):
    farms_file = tmp_path / "farms.json"
    farms_data = {
        "farms": [
            {
                "id": 7,
                "name": "Test Farm",
                "fields": [
                    {
                        "id": 999901,
                        "name": "Field 1",
                        "area": 10.5,
                        "soil_type": "clay"
                    },
                    {
                        "id": 999902,
                        "name": "Field 2",
                        "area": 15.3,
                        "soil_type": "sand"
                    }
                ]
            }
        ]
    }
    farms_file.write_text(json.dumps(farms_data))
    
    config = DaemonConfig(
        api_url="http://test/",
        api_token="token",
        farm_id=7,
        api_timeout=10,
        retry_max_attempts=3,
        retry_queue_dir="./retry_queue",
        tick_time="06:00",
        state_dir="./state",
        log_level="INFO",
        log_file=None,
        crop_type="Potato",
        variety="Belana",
        season_start_date=datetime.datetime(2024, 10, 1),
        fuel_variation=0.1,
        farms_config_path=str(farms_file),
        max_concurrent_fields=10
    )
    
    contexts = load_sim_contexts(config)
    
    assert len(contexts) == 2
    assert contexts[0].field_id == 999901
    assert contexts[1].field_id == 999902


def test_load_sim_contexts_unknown_farm_raises(monkeypatch, tmp_path):
    farms_file = tmp_path / "farms.json"
    farms_data = {
        "farms": [
            {
                "id": 7,
                "name": "Test Farm",
                "fields": []
            }
        ]
    }
    farms_file.write_text(json.dumps(farms_data))
    
    config = DaemonConfig(
        api_url="http://test/",
        api_token="token",
        farm_id=99,
        api_timeout=10,
        retry_max_attempts=3,
        retry_queue_dir="./retry_queue",
        tick_time="06:00",
        state_dir="./state",
        log_level="INFO",
        log_file=None,
        crop_type="Potato",
        variety="Belana",
        season_start_date=datetime.datetime(2024, 10, 1),
        fuel_variation=0.1,
        farms_config_path=str(farms_file),
        max_concurrent_fields=10
    )
    
    with pytest.raises(ValueError, match="Farm ID 99 not found"):
        load_sim_contexts(config)


def test_load_sim_contexts_maps_fields_correctly(tmp_path):
    farms_file = tmp_path / "farms.json"
    farms_data = {
        "farms": [
            {
                "id": 7,
                "name": "Test Farm",
                "fields": [
                    {
                        "id": 999901,
                        "name": "Test Field",
                        "area": 12.5,
                        "soil_type": "loam"
                    }
                ]
            }
        ]
    }
    farms_file.write_text(json.dumps(farms_data))
    
    config = DaemonConfig(
        api_url="http://test/",
        api_token="token",
        farm_id=7,
        api_timeout=10,
        retry_max_attempts=3,
        retry_queue_dir="./retry_queue",
        tick_time="06:00",
        state_dir="./state",
        log_level="INFO",
        log_file=None,
        crop_type="Wheat",
        variety="Spelt",
        season_start_date=datetime.datetime(2024, 11, 1),
        fuel_variation=0.2,
        farms_config_path=str(farms_file),
        max_concurrent_fields=10
    )
    
    contexts = load_sim_contexts(config)
    
    assert len(contexts) == 1
    context = contexts[0]
    assert context.field_id == 999901
    assert context.field_name == "Test Field"
    assert context.field_size == 12.5
    assert context.soil_type == "loam"
    assert context.crop_type == "Wheat"
    assert context.variety == "Spelt"
    assert context.start_date == datetime.datetime(2024, 11, 1)
    assert context.fuel_variation == 0.2


def test_optional_env_vars_have_defaults(monkeypatch):
    monkeypatch.setenv("DIGIZERT_API_URL", "http://api.test/")
    monkeypatch.setenv("DIGIZERT_API_TOKEN", "token123")
    monkeypatch.setenv("FARM_ID", "7")
    
    for key in ["API_TIMEOUT_SECONDS", "RETRY_MAX_ATTEMPTS", "TICK_TIME", "STATE_DIR", 
                "LOG_LEVEL", "LOG_FILE", "CROP_TYPE", "VARIETY", "SEASON_START_DATE", 
                "FUEL_VARIATION", "FARMS_CONFIG_PATH"]:
        monkeypatch.delenv(key, raising=False)
    
    config = load_and_validate_config()
    
    assert config.tick_time == "06:00"
    assert config.retry_max_attempts == 3
    assert config.crop_type == "Potato"
    assert config.variety == "Belana"
    assert config.api_timeout == 10
    assert config.state_dir == "./state"
    assert config.log_level == "INFO"
    assert config.fuel_variation == 0.1
    assert config.farms_config_path == "./config/farms.json"


def test_sigterm_registers_shutdown_handler(monkeypatch):
    monkeypatch.setenv("DIGIZERT_API_URL", "http://api.test/")
    monkeypatch.setenv("DIGIZERT_API_TOKEN", "token123")
    monkeypatch.setenv("FARM_ID", "7")
    
    registered_handlers = {}
    
    def capture_signal(sig, handler):
        registered_handlers[sig] = handler
    
    mock_scheduler = Mock()
    mock_scheduler.start = Mock()
    mock_scheduler._running = False
    
    with patch('daemon.load_and_validate_config') as mock_config, \
         patch('daemon.load_sim_contexts', return_value=[Mock()]), \
         patch('daemon.setup_logging'), \
         patch('daemon.get_logger'), \
         patch('daemon.DigiZertClient'), \
         patch('daemon.RetryDispatcher'), \
         patch('daemon.TickScheduler', return_value=mock_scheduler), \
         patch('signal.signal', side_effect=capture_signal), \
         patch.object(mock_scheduler, 'start', return_value=None), \
         patch('sys.argv', ['daemon.py']):
        
        mock_config.return_value = Mock(
            log_level="INFO", log_file=None, farm_id=7,
            api_url="http://test/", api_token="token", api_timeout=10,
            retry_max_attempts=3, tick_time="06:00", state_dir="./state"
        )
        daemon_module.main()
    
    assert signal.SIGTERM in registered_handlers
    assert signal.SIGINT in registered_handlers
    
    registered_handlers[signal.SIGTERM](signal.SIGTERM, None)
    mock_scheduler.stop.assert_called_once()


def test_config_with_custom_optional_values(monkeypatch):
    monkeypatch.setenv("DIGIZERT_API_URL", "http://api.test/")
    monkeypatch.setenv("DIGIZERT_API_TOKEN", "token123")
    monkeypatch.setenv("FARM_ID", "7")
    monkeypatch.setenv("API_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("RETRY_MAX_ATTEMPTS", "5")
    monkeypatch.setenv("TICK_TIME", "08:30")
    monkeypatch.setenv("STATE_DIR", "/custom/state")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FILE", "/custom/log.log")
    monkeypatch.setenv("CROP_TYPE", "Wheat")
    monkeypatch.setenv("VARIETY", "Spelt")
    monkeypatch.setenv("SEASON_START_DATE", "2025-03-15")
    monkeypatch.setenv("FUEL_VARIATION", "0.25")
    monkeypatch.setenv("FARMS_CONFIG_PATH", "/custom/farms.json")
    
    config = load_and_validate_config()
    
    assert config.api_timeout == 30
    assert config.retry_max_attempts == 5
    assert config.tick_time == "08:30"
    assert config.state_dir == "/custom/state"
    assert config.log_level == "DEBUG"
    assert config.log_file == "/custom/log.log"
    assert config.crop_type == "Wheat"
    assert config.variety == "Spelt"
    assert config.season_start_date == datetime.datetime(2025, 3, 15)
    assert config.fuel_variation == 0.25
    assert config.farms_config_path == "/custom/farms.json"


def test_load_sim_contexts_with_multiple_farms_selects_correct_one(tmp_path):
    farms_file = tmp_path / "farms.json"
    farms_data = {
        "farms": [
            {
                "id": 5,
                "name": "Farm 5",
                "fields": [
                    {"id": 1, "name": "F5-Field1", "area": 5.0, "soil_type": "sand"}
                ]
            },
            {
                "id": 7,
                "name": "Farm 7",
                "fields": [
                    {"id": 999901, "name": "F7-Field1", "area": 10.0, "soil_type": "clay"}
                ]
            },
            {
                "id": 9,
                "name": "Farm 9",
                "fields": [
                    {"id": 2, "name": "F9-Field1", "area": 15.0, "soil_type": "loam"}
                ]
            }
        ]
    }
    farms_file.write_text(json.dumps(farms_data))
    
    config = DaemonConfig(
        api_url="http://test/",
        api_token="token",
        farm_id=7,
        api_timeout=10,
        retry_max_attempts=3,
        retry_queue_dir="./retry_queue",
        tick_time="06:00",
        state_dir="./state",
        log_level="INFO",
        log_file=None,
        crop_type="Potato",
        variety="Belana",
        season_start_date=datetime.datetime(2024, 10, 1),
        fuel_variation=0.1,
        farms_config_path=str(farms_file),
        max_concurrent_fields=10
    )
    
    contexts = load_sim_contexts(config)
    
    assert len(contexts) == 1
    assert contexts[0].field_id == 999901
    assert contexts[0].field_name == "F7-Field1"


def test_retry_queue_dir_from_env(monkeypatch):
    monkeypatch.setenv("DIGIZERT_API_URL", "http://test/")
    monkeypatch.setenv("DIGIZERT_API_TOKEN", "token")
    monkeypatch.setenv("FARM_ID", "7")
    monkeypatch.setenv("RETRY_QUEUE_DIR", "/custom/queue")
    
    config = load_and_validate_config()
    assert config.retry_queue_dir == "/custom/queue"


def test_retry_queue_dir_default(monkeypatch):
    monkeypatch.setenv("DIGIZERT_API_URL", "http://test/")
    monkeypatch.setenv("DIGIZERT_API_TOKEN", "token")
    monkeypatch.setenv("FARM_ID", "7")
    monkeypatch.delenv("RETRY_QUEUE_DIR", raising=False)
    
    config = load_and_validate_config()
    assert config.retry_queue_dir == "./retry_queue"


def test_retry_dispatcher_uses_config_queue_dir(tmp_path):
    import httpx
    from services.retry_dispatcher import RetryDispatcher
    from models.planting_plan import FieldOperationEvent
    from tenacity import wait_none
    
    custom_queue = tmp_path / "custom_queue"
    mock_client = Mock()
    mock_client.send_event.side_effect = httpx.TimeoutException("timeout")
    
    dispatcher = RetryDispatcher(
        mock_client,
        max_attempts=3,
        queue_dir=str(custom_queue),
        _wait_strategy=wait_none()
    )
    
    mock_event = FieldOperationEvent(
        field=1,
        worktype=6,
        start_date="2024-10-01",
        end_date="2024-10-01",
        machine="Test Machine",
        area=10.0,
        distance=5.0,
        distanceWorked=4.5,
        duration=3600.0,
        durationWorked=3400.0,
        fuel=15.0
    )
    
    mock_context = SimContext(
        field_id=1,
        field_name="Test Field",
        field_size=10.0,
        soil_type="sand",
        crop_type="Potato",
        variety="Belana",
        start_date=datetime.datetime(2024, 10, 1),
        fuel_variation=0.1
    )
    
    dispatcher.send_event(mock_event, mock_context)
    
    queue_files = list(custom_queue.rglob("*.json"))
    assert len(queue_files) == 1
