"""Tests für DigiZertDataClient (D3/D4 – SoilMoistureData + WeatherData)."""
import datetime
from unittest.mock import Mock, patch

import httpx
import pytest

from services.digizert_data_client import (
    DigiZertDataClient,
    SoilMoistureMeasurement,
    WeatherMeasurement,
)


@pytest.fixture
def enabled_client():
    return DigiZertDataClient(
        api_base_url="https://api.example.com",
        api_token="test-token",
        timeout=5,
        enabled=True,
    )


@pytest.fixture
def disabled_client():
    return DigiZertDataClient(
        api_base_url="https://api.example.com",
        api_token="test-token",
        timeout=5,
        enabled=False,
    )


# ---------------------------------------------------------------------------
# Feature-Flag: disabled → No-Op
# ---------------------------------------------------------------------------


def test_disabled_client_ensure_sensor_is_noop(disabled_client):
    """When disabled, ensure_*_sensor should be no-ops."""
    with patch("httpx.post") as mock_post:
        disabled_client.ensure_soil_moisture_sensor(42, depth=15)
        disabled_client.ensure_weather_sensor(42)
        mock_post.assert_not_called()


def test_disabled_client_send_data_is_noop(disabled_client):
    """When disabled, send_*_data should be no-ops."""
    measurements = [SoilMoistureMeasurement(
        timestamp=datetime.datetime(2026, 1, 1), vwc=28.5
    )]
    with patch("httpx.post") as mock_post:
        disabled_client.send_soil_moisture_data(42, 15, measurements)
        disabled_client.send_weather_data(42, [])
        mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# Sensor-Anlage (idempotent)
# ---------------------------------------------------------------------------


def test_ensure_soil_moisture_sensor_posts_correct_payload(enabled_client):
    """Test that ensure_soil_moisture_sensor posts correct payload."""
    with patch("httpx.post") as mock_post:
        mock_response = Mock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        enabled_client.ensure_soil_moisture_sensor(42, depth=15)

        call_args = mock_post.call_args
        assert call_args.args[0] == "https://api.example.com/sensors/"
        payload = call_args.kwargs["json"]
        assert payload["field"] == 42
        assert payload["sensor_type"] == "soil_moisture"
        assert payload["depth"] == 15
        assert "15cm" in payload["name"]


def test_ensure_weather_sensor_posts_correct_payload(enabled_client):
    """Test that ensure_weather_sensor posts correct payload."""
    with patch("httpx.post") as mock_post:
        mock_response = Mock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        enabled_client.ensure_weather_sensor(42)

        call_args = mock_post.call_args
        assert call_args.args[0] == "https://api.example.com/weather-sensors/"
        payload = call_args.kwargs["json"]
        assert payload["field"] == 42
        assert payload["sensor_type"] == "rain"


def test_ensure_sensor_handles_duplicate_409(enabled_client):
    """Test that 409 (duplicate) is handled gracefully."""
    with patch("httpx.post") as mock_post:
        mock_response = Mock()
        mock_response.status_code = 409
        mock_post.return_value = mock_response

        # Should not raise
        enabled_client.ensure_soil_moisture_sensor(42, depth=15)


def test_ensure_sensor_handles_duplicate_400(enabled_client):
    """Test that 400 (duplicate validation) is handled gracefully."""
    with patch("httpx.post") as mock_post:
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response

        # Should not raise
        enabled_client.ensure_weather_sensor(42)


# ---------------------------------------------------------------------------
# Bulk-Data-Transfer
# ---------------------------------------------------------------------------


def test_send_soil_moisture_data_posts_correct_bulk(enabled_client):
    """Test that send_soil_moisture_data posts correct bulk payload."""
    measurements = [
        SoilMoistureMeasurement(
            timestamp=datetime.datetime(2026, 4, 1, 0, 0), vwc=28.5
        ),
        SoilMoistureMeasurement(
            timestamp=datetime.datetime(2026, 4, 2, 0, 0), vwc=27.8
        ),
    ]
    with patch("httpx.post") as mock_post:
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        enabled_client.send_soil_moisture_data(42, 15, measurements)

        call_args = mock_post.call_args
        assert call_args.args[0] == "https://api.example.com/soil-moisture/"
        payload = call_args.kwargs["json"]
        assert payload["field"] == 42
        assert payload["depth"] == 15
        assert len(payload["measurements"]) == 2
        assert payload["measurements"][0]["vwc"] == 28.5
        assert "timestamp" in payload["measurements"][0]


def test_send_weather_data_posts_correct_bulk(enabled_client):
    """Test that send_weather_data posts correct bulk payload."""
    measurements = [
        WeatherMeasurement(
            timestamp=datetime.datetime(2026, 4, 1, 0, 0),
            rain_fall=2.3,
            temperature=12.5,
        ),
        WeatherMeasurement(
            timestamp=datetime.datetime(2026, 4, 2, 0, 0),
            rain_fall=0.0,
            temperature=None,
        ),
    ]
    with patch("httpx.post") as mock_post:
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        enabled_client.send_weather_data(42, measurements)

        call_args = mock_post.call_args
        assert call_args.args[0] == "https://api.example.com/weather/"
        payload = call_args.kwargs["json"]
        assert payload["field"] == 42
        assert len(payload["measurements"]) == 2
        assert payload["measurements"][0]["rain_fall"] == 2.3
        assert payload["measurements"][0]["temperature"] == 12.5
        # temperature=None should be omitted
        assert "temperature" not in payload["measurements"][1]


def test_send_data_empty_measurements_is_noop(enabled_client):
    """Empty measurements list should be a no-op even when enabled."""
    with patch("httpx.post") as mock_post:
        enabled_client.send_soil_moisture_data(42, 15, [])
        enabled_client.send_weather_data(42, [])
        mock_post.assert_not_called()


def test_send_data_logs_http_error_without_crashing(enabled_client):
    """Test that HTTP errors are logged but don't crash the bootstrap."""
    measurements = [SoilMoistureMeasurement(
        timestamp=datetime.datetime(2026, 4, 1), vwc=28.5
    )]
    with patch("httpx.post") as mock_post:
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=Mock(), response=mock_response
        )
        mock_post.return_value = mock_response

        # Should NOT raise – just log the error
        enabled_client.send_soil_moisture_data(42, 15, measurements)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


def test_soil_moisture_measurement_is_frozen():
    """SoilMoistureMeasurement should be immutable."""
    m = SoilMoistureMeasurement(
        timestamp=datetime.datetime(2026, 4, 1), vwc=28.5
    )
    with pytest.raises(AttributeError):
        m.vwc = 30.0


def test_weather_measurement_defaults_temperature_none():
    """WeatherMeasurement temperature should default to None."""
    m = WeatherMeasurement(
        timestamp=datetime.datetime(2026, 4, 1), rain_fall=2.3
    )
    assert m.temperature is None
