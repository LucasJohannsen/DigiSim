import datetime
import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx
from tenacity import wait_none

from config.settings import DaemonConfig, load_sim_contexts, load_sim_contexts_from_api
from models.planting_plan import FieldOperationEvent
from models.sim_context import SimContext
from scheduler.tick_scheduler import TickScheduler
from services.digizert_client import DigiZertClient
from services.retry_dispatcher import RetryDispatcher
from utils.state_manager import FieldStateSnapshot, StateManager

API_URL = "http://api.test"
FARM_ID = 7
FIELDS_URL = f"{API_URL}/api/v1/fields/{FARM_ID}/enterprise/"
EVENTS_URL = f"{API_URL}/operations/"

MOCK_FIELDS = {
    "results": [
        {"id": 1, "name": "Field 1", "area": 10.5, "soil_type": "sand"},
        {"id": 2, "name": "Field 2", "area": 15.0, "soil_type": "loam"},
    ],
    "next": None,
}


def make_config(tmp_path: Path, farms_config: str | None = None) -> DaemonConfig:
    return DaemonConfig(
        api_url=API_URL,
        api_token="testtoken",
        farm_id=FARM_ID,
        api_timeout=5,
        retry_max_attempts=1,
        retry_queue_dir=str(tmp_path / "queue"),
        tick_time="06:00",
        state_dir=str(tmp_path / "state"),
        log_level="ERROR",
        log_file=None,
        crop_type="Potato",
        variety="Belana",
        season_start_date=datetime.datetime(2024, 10, 1),
        fuel_variation=0.1,
        farms_config_path=farms_config
        or str(Path(__file__).parent.parent / "config" / "farms.json"),
        max_concurrent_fields=5,
    )


def make_sim_context(field_id: int = 1) -> SimContext:
    return SimContext(
        field_id=field_id,
        field_name=f"Field {field_id}",
        field_size=10.5,
        soil_type="sand",
        start_date=datetime.datetime(2024, 10, 1),
        crop_type="Potato",
        variety="Belana",
        fuel_variation=0.1,
    )


def make_snapshot(field_id: int = 1) -> FieldStateSnapshot:
    return FieldStateSnapshot(
        field_id=field_id,
        last_tick_date=datetime.date(2024, 11, 1),
        context=make_sim_context(field_id),
        planting_ops=[],
        protection_ops=[],
    )


def make_fast_dispatcher(tmp_path: Path) -> RetryDispatcher:
    client = DigiZertClient(api_url=EVENTS_URL, api_token="testtoken", timeout=5)
    return RetryDispatcher(
        client,
        max_attempts=1,
        queue_dir=str(tmp_path / "queue"),
        _wait_strategy=wait_none(),
    )


@pytest.mark.integration
def test_api_loads_fields_happy_path(tmp_path):
    """Farm-Felder werden korrekt aus Mock-API geladen und als SimContexts aufgebaut."""
    config = make_config(tmp_path)
    state_manager = StateManager(str(tmp_path / "state"))

    with respx.mock:
        respx.get(FIELDS_URL).mock(return_value=httpx.Response(200, json=MOCK_FIELDS))
        contexts = load_sim_contexts_from_api(config, state_manager)

    assert len(contexts) == 2
    assert contexts[0].field_id == 1
    assert contexts[0].field_name == "Field 1"
    assert contexts[0].field_size == 10.5
    assert contexts[1].field_id == 2
    assert contexts[1].soil_type == "loam"
    assert all(c.crop_type == "Potato" for c in contexts)
    assert all(c.variety == "Belana" for c in contexts)


@pytest.mark.integration
def test_field_sync_detects_inactive_fields(tmp_path):
    """Inaktive Felder (in State, aber nicht in API) erscheinen nicht in den Contexts."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "field_99.json").write_text('{"last_tick_date": "2024-10-01"}')

    config = make_config(tmp_path)
    state_manager = StateManager(str(state_dir))

    with respx.mock:
        respx.get(FIELDS_URL).mock(return_value=httpx.Response(200, json=MOCK_FIELDS))
        contexts = load_sim_contexts_from_api(config, state_manager)

    field_ids = {c.field_id for c in contexts}
    assert field_ids == {1, 2}
    assert 99 not in field_ids


@pytest.mark.integration
def test_degraded_path_falls_back_to_json(tmp_path):
    """Bei API-Fehler (500) fällt load_sim_contexts auf die lokale farms.json zurück."""
    config = make_config(tmp_path)
    state_manager = StateManager(str(tmp_path / "state"))

    with respx.mock:
        respx.get(FIELDS_URL).mock(return_value=httpx.Response(500))
        contexts = load_sim_contexts(config, state_manager)

    assert len(contexts) > 0
    field_ids = {c.field_id for c in contexts}
    assert all(fid >= 999900 for fid in field_ids)


@pytest.mark.integration
def test_event_dispatch_success_no_queue(tmp_path):
    """Erfolgreiches Event-Dispatch (201) hinterlässt keine Queue-Dateien."""
    dispatcher = make_fast_dispatcher(tmp_path)
    event = FieldOperationEvent(
        field=1,
        worktype="sowing",
        exa_id=None,
        start_date="2024-10-01",
        end_date="2024-10-01",
        area=10.5,
        distance=None,
        distanceWorked=None,
        duration=None,
        durationWorked=None,
        fuel=5.0,
        application_type=None,
        application_category=None,
        application_name=None,
        application_amount=None,
        application_unit=None,
        worktype_text="Saat",
        machine=None,
    )
    context = make_sim_context(1)

    with respx.mock:
        respx.post(EVENTS_URL).mock(return_value=httpx.Response(201))
        dispatcher.send_event(event, context)

    queue_dir = tmp_path / "queue"
    assert not queue_dir.exists() or not any(queue_dir.rglob("*.json"))


@pytest.mark.integration
def test_event_queued_on_persistent_failure(tmp_path):
    """Bei dauerhaftem API-Fehler (503) wird das Event in die Queue geschrieben."""
    dispatcher = make_fast_dispatcher(tmp_path)
    event = FieldOperationEvent(
        field=1,
        worktype="sowing",
        exa_id=None,
        start_date="2024-10-01",
        end_date="2024-10-01",
        area=10.5,
        distance=None,
        distanceWorked=None,
        duration=None,
        durationWorked=None,
        fuel=5.0,
        application_type=None,
        application_category=None,
        application_name=None,
        application_amount=None,
        application_unit=None,
        worktype_text="Saat",
        machine=None,
    )
    context = make_sim_context(1)

    with respx.mock:
        respx.post(EVENTS_URL).mock(return_value=httpx.Response(503))
        dispatcher.send_event(event, context)

    queue_files = list((tmp_path / "queue").rglob("*.json"))
    assert len(queue_files) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_daily_tick_persists_state(tmp_path):
    """daily_tick() schreibt field_N.json und heartbeat.json in den State-Ordner."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)

    sim_context = make_sim_context(1)
    snapshot = make_snapshot(1)

    runner = MagicMock()
    runner.context = sim_context
    runner.tick.return_value = []
    runner.get_state_snapshot.return_value = snapshot

    scheduler = TickScheduler(
        contexts=[sim_context],
        state_dir=str(state_dir),
        event_dispatcher=None,
    )
    scheduler.runners = {1: runner}

    await scheduler.daily_tick()

    assert (state_dir / "field_1.json").exists()
    assert (state_dir / "heartbeat.json").exists()

    state_data = json.loads((state_dir / "field_1.json").read_text())
    assert state_data["field_id"] == 1
    assert state_data["last_tick_date"] == "2024-11-01"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_daily_tick_dispatches_events(tmp_path):
    """daily_tick() ruft event_dispatcher.send_event für jedes Event eines Ticks auf."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)

    sim_context = make_sim_context(1)
    snapshot = make_snapshot(1)

    event = FieldOperationEvent(
        field=1,
        worktype="sowing",
        exa_id=None,
        start_date="2024-10-01",
        end_date="2024-10-01",
        area=10.5,
        distance=None,
        distanceWorked=None,
        duration=None,
        durationWorked=None,
        fuel=5.0,
        application_type=None,
        application_category=None,
        application_name=None,
        application_amount=None,
        application_unit=None,
        worktype_text="Saat",
        machine=None,
    )

    runner = MagicMock()
    runner.context = sim_context
    runner.tick.return_value = [event]
    runner.get_state_snapshot.return_value = snapshot

    dispatcher = MagicMock()

    scheduler = TickScheduler(
        contexts=[sim_context],
        state_dir=str(state_dir),
        event_dispatcher=dispatcher,
    )
    scheduler.runners = {1: runner}

    await scheduler.daily_tick()

    dispatcher.send_event.assert_called_once_with(event, sim_context)
