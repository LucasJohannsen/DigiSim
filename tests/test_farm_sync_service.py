import pytest
import httpx
from unittest.mock import Mock, MagicMock, patch

from services.farm_sync_service import FarmSyncService, FieldData, SyncResult


def test_load_farm_fields_success():
    mock_response = {
        "results": [
            {"id": 1, "name": "Field 1", "area": 10.5, "soil_type": "sand"},
            {"id": 2, "name": "Field 2", "area": 15.0, "soil_type": "loam"}
        ]
    }
    
    with patch('httpx.Client') as MockClient:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.get.return_value = Mock(
            status_code=200,
            json=lambda: mock_response
        )
        MockClient.return_value = mock_client
        
        service = FarmSyncService("http://api.test", "token123")
        fields = service.load_farm_fields(farm_id=7)
        
        assert len(fields) == 2
        assert fields[0].field_id == 1
        assert fields[0].field_name == "Field 1"
        assert fields[0].field_size == 10.5
        assert fields[1].soil_type == "loam"


def test_load_farm_fields_http_error():
    with patch('httpx.Client') as MockClient:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_response = Mock(status_code=404)
        mock_client.get.return_value = mock_response
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=Mock(), response=mock_response
        )
        MockClient.return_value = mock_client
        
        service = FarmSyncService("http://api.test", "token123")
        
        with pytest.raises(ValueError, match="HTTP 404"):
            service.load_farm_fields(farm_id=999)


def test_sync_fields_new_fields():
    api_fields = [
        FieldData(1, "F1", 10.0, "sand"),
        FieldData(2, "F2", 15.0, "loam"),
        FieldData(3, "F3", 20.0, "clay")
    ]
    local_field_ids = [1, 2]
    
    service = FarmSyncService("http://api.test", "token123")
    result = service.sync_fields(api_fields, local_field_ids)
    
    assert result.new_fields == [3]
    assert set(result.existing_fields) == {1, 2}
    assert result.inactive_fields == []


def test_sync_fields_inactive_fields():
    api_fields = [
        FieldData(1, "F1", 10.0, "sand"),
        FieldData(2, "F2", 15.0, "loam")
    ]
    local_field_ids = [1, 2, 3, 4]
    
    service = FarmSyncService("http://api.test", "token123")
    result = service.sync_fields(api_fields, local_field_ids)
    
    assert result.new_fields == []
    assert set(result.existing_fields) == {1, 2}
    assert set(result.inactive_fields) == {3, 4}


def test_sync_fields_all_new():
    api_fields = [FieldData(10, "F10", 10.0, "sand")]
    local_field_ids = []
    
    service = FarmSyncService("http://api.test", "token123")
    result = service.sync_fields(api_fields, local_field_ids)
    
    assert result.new_fields == [10]
    assert result.existing_fields == []
    assert result.inactive_fields == []


def test_state_manager_get_all_field_ids(tmp_path):
    from utils.state_manager import StateManager
    
    (tmp_path / "field_1.json").write_text('{"last_tick_date": "2024-10-01"}')
    (tmp_path / "field_42.json").write_text('{"last_tick_date": "2024-10-02"}')
    (tmp_path / "field_999.json").write_text('{"last_tick_date": "2024-10-03"}')
    (tmp_path / "invalid.json").write_text('{}')
    
    manager = StateManager(str(tmp_path))
    field_ids = manager.get_all_field_ids()
    
    assert set(field_ids) == {1, 42, 999}
