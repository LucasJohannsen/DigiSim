"""Tests für ISIP-Druck-Gating (P4 – Fungizid-Steuerung über Infektionsdruck).

Testet:
1. ISIPPressureService – Endpoint-Call, Caching, Fallback
2. ProtectionPlanService – Fungizid-Gating-Logik (justify, skip, fallback)
"""

import datetime
from unittest.mock import Mock, patch

import httpx
import pytest

from models.planting_plan import FieldOperation
from models.worktypes import WorkType
from services.isip_pressure_service import ISIPPressureService
from services.protection_plan_service import (
    FUNGIZID_CATEGORY,
    ProtectionPlanService,
)

# ---------------------------------------------------------------------------
# ISIPPressureService
# ---------------------------------------------------------------------------


@pytest.fixture
def enabled_isip_service():
    return ISIPPressureService(
        api_base_url="https://api.example.com/api/v1/simulator",
        api_token="test-token",
        field_id=42,
        timeout=5,
        enabled=True,
    )


@pytest.fixture
def disabled_isip_service():
    return ISIPPressureService(
        api_base_url="https://api.example.com/api/v1/simulator",
        api_token="test-token",
        field_id=42,
        timeout=5,
        enabled=False,
    )


def test_disabled_isip_always_justified(disabled_isip_service):
    """When disabled, is_justified always returns True (deterministic)."""
    assert disabled_isip_service.is_justified(datetime.date(2026, 5, 1)) is True


def test_enabled_isip_justified_from_cache(enabled_isip_service):
    """Test that is_justified returns value from cache."""
    from services.isip_pressure_service import ISIPDayData

    test_date = datetime.date(2026, 5, 1)
    enabled_isip_service._cache[test_date] = ISIPDayData(
        date=test_date,
        infection_pressure=45.0,
        infection_action=1,
        is_justified_window=True,
    )
    assert enabled_isip_service.is_justified(test_date) is True


def test_enabled_isip_not_justified_from_cache(enabled_isip_service):
    """Test that is_justified returns False from cache."""
    from services.isip_pressure_service import ISIPDayData

    test_date = datetime.date(2026, 5, 2)
    enabled_isip_service._cache[test_date] = ISIPDayData(
        date=test_date,
        infection_pressure=0.0,
        infection_action=0,
        is_justified_window=False,
    )
    assert enabled_isip_service.is_justified(test_date) is False


def test_isip_fetch_season_populates_cache(enabled_isip_service):
    """Test that fetch_season populates the cache."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {
        "field": 42,
        "model": "simphyt3",
        "daily": [
            {
                "date": "2026-05-01",
                "infection_pressure": 10.0,
                "infection_action": 0,
                "is_justified_window": False,
            },
            {
                "date": "2026-05-02",
                "infection_pressure": 45.0,
                "infection_action": 1,
                "is_justified_window": True,
            },
        ],
    }

    with patch("httpx.get", return_value=mock_response):
        enabled_isip_service.fetch_season(
            datetime.date(2026, 5, 1),
            datetime.date(2026, 5, 2),
        )

    assert len(enabled_isip_service._cache) == 2
    assert enabled_isip_service.is_justified(datetime.date(2026, 5, 1)) is False
    assert enabled_isip_service.is_justified(datetime.date(2026, 5, 2)) is True


def test_isip_fetch_season_fallback_on_error(enabled_isip_service):
    """Test that fetch_season handles errors gracefully (empty cache)."""
    with patch("httpx.get", side_effect=httpx.RequestError("Connection failed")):
        enabled_isip_service.fetch_season(
            datetime.date(2026, 5, 1),
            datetime.date(2026, 5, 2),
        )
    # Cache should be empty, is_justified falls back to True
    assert len(enabled_isip_service._cache) == 0
    assert enabled_isip_service.is_justified(datetime.date(2026, 5, 1)) is True


def test_isip_single_day_fetch(enabled_isip_service):
    """Test single-day fetch when date not in cache."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {
        "field": 42,
        "model": "simphyt3",
        "daily": [
            {
                "date": "2026-06-15",
                "infection_pressure": 50.0,
                "infection_action": 1,
                "is_justified_window": True,
            },
        ],
    }

    with patch("httpx.get", return_value=mock_response):
        result = enabled_isip_service.is_justified(datetime.date(2026, 6, 15))

    assert result is True
    assert datetime.date(2026, 6, 15) in enabled_isip_service._cache


def test_find_next_justified_date(enabled_isip_service):
    """Test find_next_justified_date."""
    from services.isip_pressure_service import ISIPDayData

    # Set up cache: justified on day 3 and 5
    for i, justified in [(1, False), (2, False), (3, True), (4, False), (5, True)]:
        d = datetime.date(2026, 5, i)
        enabled_isip_service._cache[d] = ISIPDayData(
            date=d,
            infection_pressure=0,
            infection_action=0,
            is_justified_window=justified,
        )

    result = enabled_isip_service.find_next_justified_date(datetime.date(2026, 5, 1), max_days=7)
    assert result == datetime.date(2026, 5, 3)


def test_find_next_justified_date_none(enabled_isip_service):
    """Test find_next_justified_date returns None if no justified day."""
    from services.isip_pressure_service import ISIPDayData

    # Cache days 1-8 (max_days=7 checks range(8) = days 1-8)
    for i in range(1, 9):
        d = datetime.date(2026, 5, i)
        enabled_isip_service._cache[d] = ISIPDayData(
            date=d,
            infection_pressure=0,
            infection_action=0,
            is_justified_window=False,
        )

    result = enabled_isip_service.find_next_justified_date(datetime.date(2026, 5, 1), max_days=7)
    assert result is None


# ---------------------------------------------------------------------------
# ProtectionPlanService – ISIP-Gating
# ---------------------------------------------------------------------------


def _make_fungicide_op(planned_date, name="Fungizid A"):
    """Helper: create a fungicide FieldOperation."""
    op = FieldOperation(
        operation="Spritzen",
        worktype=WorkType.SPRITZEN,
        planned_date=planned_date,
        application_type="protection",
        application_category=FUNGIZID_CATEGORY,
        application_name=name,
    )
    return op


def _make_herbicide_op(planned_date, name="Herbizid A"):
    """Helper: create a herbicide FieldOperation."""
    op = FieldOperation(
        operation="Spritzen",
        worktype=WorkType.SPRITZEN,
        planned_date=planned_date,
        application_type="protection",
        application_category=26,  # Herbizid
        application_name=name,
    )
    return op


def test_fungicide_executed_when_justified():
    """Fungicide should be returned when is_justified_window=True."""
    service = ProtectionPlanService.__new__(ProtectionPlanService)
    service.operations = [
        _make_fungicide_op(datetime.datetime(2026, 5, 10)),
    ]
    service.isip_service = Mock()
    service.isip_service.enabled = True
    service.isip_service.is_justified.return_value = True

    # Mock context for logger
    service.context = Mock()
    service.context.field_id = 42

    result = service.get_next_operations(datetime.datetime(2026, 5, 10))
    assert len(result) == 1
    assert result[0].application_category == FUNGIZID_CATEGORY


def test_fungicide_delayed_when_not_justified():
    """Fungicide should NOT be returned when not justified (delayed)."""
    service = ProtectionPlanService.__new__(ProtectionPlanService)
    service.operations = [
        _make_fungicide_op(datetime.datetime(2026, 5, 10)),
    ]
    service.isip_service = Mock()
    service.isip_service.enabled = True
    service.isip_service.is_justified.return_value = False

    service.context = Mock()
    service.context.field_id = 42

    result = service.get_next_operations(datetime.datetime(2026, 5, 10))
    assert len(result) == 0  # Not executed, will be retried


def test_fungicide_skipped_when_next_close():
    """Fungicide should be skipped when next fungicide is ≤ +2 days away."""
    service = ProtectionPlanService.__new__(ProtectionPlanService)
    service.operations = [
        _make_fungicide_op(datetime.datetime(2026, 5, 10), "Fungizid A"),
        _make_fungicide_op(datetime.datetime(2026, 5, 12), "Fungizid B"),
    ]
    service.isip_service = Mock()
    service.isip_service.enabled = True
    service.isip_service.is_justified.return_value = False

    service.context = Mock()
    service.context.field_id = 42

    # Tick on 10.05. – A is due, not justified, B is +2 days → skip A
    result = service.get_next_operations(datetime.datetime(2026, 5, 10))
    assert len(result) == 0  # A skipped, B not yet due
    assert service.operations[0].actual_date is not None  # A marked as skipped


def test_fungicide_not_skipped_when_next_far():
    """Fungicide should NOT be skipped when next fungicide is > +2 days away."""
    service = ProtectionPlanService.__new__(ProtectionPlanService)
    service.operations = [
        _make_fungicide_op(datetime.datetime(2026, 5, 10), "Fungizid A"),
        _make_fungicide_op(datetime.datetime(2026, 5, 20), "Fungizid B"),
    ]
    service.isip_service = Mock()
    service.isip_service.enabled = True
    service.isip_service.is_justified.return_value = False

    service.context = Mock()
    service.context.field_id = 42

    # Tick on 10.05. – A is due, not justified, B is +10 days → delay A
    result = service.get_next_operations(datetime.datetime(2026, 5, 10))
    assert len(result) == 0  # A delayed (not skipped)
    assert service.operations[0].actual_date is None  # A not marked


def test_fungicide_fallback_after_7_days():
    """Fungicide should execute deterministically after 7 days."""
    service = ProtectionPlanService.__new__(ProtectionPlanService)
    service.operations = [
        _make_fungicide_op(datetime.datetime(2026, 5, 10)),
    ]
    service.isip_service = Mock()
    service.isip_service.enabled = True
    service.isip_service.is_justified.return_value = False

    service.context = Mock()
    service.context.field_id = 42

    # Tick on 18.05. – planned_date + 7 days = 17.05. → fallback
    result = service.get_next_operations(datetime.datetime(2026, 5, 18))
    assert len(result) == 1  # Executed deterministically


def test_herbicide_not_gated():
    """Herbicide should always execute (not gated by ISIP)."""
    service = ProtectionPlanService.__new__(ProtectionPlanService)
    service.operations = [
        _make_herbicide_op(datetime.datetime(2026, 5, 10)),
    ]
    service.isip_service = Mock()
    service.isip_service.enabled = True
    service.isip_service.is_justified.return_value = False  # Not justified

    service.context = Mock()
    service.context.field_id = 42

    result = service.get_next_operations(datetime.datetime(2026, 5, 10))
    assert len(result) == 1  # Herbizide executes regardless


def test_no_isip_service_deterministic():
    """Without ISIP service, all operations execute deterministically."""
    service = ProtectionPlanService.__new__(ProtectionPlanService)
    service.operations = [
        _make_fungicide_op(datetime.datetime(2026, 5, 10)),
    ]
    service.isip_service = None

    service.context = Mock()
    service.context.field_id = 42

    result = service.get_next_operations(datetime.datetime(2026, 5, 10))
    assert len(result) == 1


def test_isip_service_disabled_deterministic():
    """With disabled ISIP service, all operations execute deterministically."""
    service = ProtectionPlanService.__new__(ProtectionPlanService)
    service.operations = [
        _make_fungicide_op(datetime.datetime(2026, 5, 10)),
    ]
    service.isip_service = Mock()
    service.isip_service.enabled = False

    service.context = Mock()
    service.context.field_id = 42

    result = service.get_next_operations(datetime.datetime(2026, 5, 10))
    assert len(result) == 1


def test_skip_logic_recursive():
    """Test recursive skip: A skipped, B checked next."""
    service = ProtectionPlanService.__new__(ProtectionPlanService)
    service.operations = [
        _make_fungicide_op(datetime.datetime(2026, 5, 10), "Fungizid A"),
        _make_fungicide_op(datetime.datetime(2026, 5, 12), "Fungizid B"),
    ]
    service.isip_service = Mock()
    service.isip_service.enabled = True
    # Not justified on 10.05., justified on 12.05.
    service.isip_service.is_justified.side_effect = lambda d: d == datetime.date(2026, 5, 12)

    service.context = Mock()
    service.context.field_id = 42

    # Tick on 10.05. – A not justified, B +2 days → skip A
    result_10 = service.get_next_operations(datetime.datetime(2026, 5, 10))
    assert len(result_10) == 0
    assert service.operations[0].actual_date is not None  # A skipped

    # Tick on 12.05. – B is due, justified → execute
    result_12 = service.get_next_operations(datetime.datetime(2026, 5, 12))
    assert len(result_12) == 1
    assert result_12[0].application_name == "Fungizid B"
