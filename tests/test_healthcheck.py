import datetime
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scheduler.tick_scheduler import TickScheduler


def make_heartbeat(tmp_path: Path, age_hours: float) -> Path:
    last_tick = datetime.datetime.now() - datetime.timedelta(hours=age_hours)
    heartbeat = {
        "last_tick": last_tick.isoformat(),
        "successful_fields": 3,
        "total_fields": 3,
    }
    path = tmp_path / "heartbeat.json"
    path.write_text(json.dumps(heartbeat))
    return path


def run_healthcheck(state_dir: str, max_age_hours: int = 25) -> int:
    """Run healthcheck.main() and return the exit code."""
    import scripts.healthcheck as hc

    with patch.dict(
        "os.environ", {"STATE_DIR": state_dir, "HEALTHCHECK_MAX_AGE_HOURS": str(max_age_hours)}
    ):
        with pytest.raises(SystemExit) as exc:
            hc.main()
        return exc.value.code


def test_healthcheck_exits_0_when_no_heartbeat(tmp_path):
    """Daemon just started – no heartbeat yet → healthy."""
    code = run_healthcheck(str(tmp_path))
    assert code == 0


def test_healthcheck_exits_0_for_recent_heartbeat(tmp_path):
    """Heartbeat written 1 hour ago → healthy."""
    make_heartbeat(tmp_path, age_hours=1)
    code = run_healthcheck(str(tmp_path), max_age_hours=25)
    assert code == 0


def test_healthcheck_exits_1_for_old_heartbeat(tmp_path):
    """Heartbeat written 30 hours ago → unhealthy."""
    make_heartbeat(tmp_path, age_hours=30)
    code = run_healthcheck(str(tmp_path), max_age_hours=25)
    assert code == 1


def test_healthcheck_exits_1_for_corrupt_file(tmp_path):
    """Corrupt heartbeat.json → unhealthy."""
    (tmp_path / "heartbeat.json").write_text("not valid json{{{")
    code = run_healthcheck(str(tmp_path))
    assert code == 1


def test_healthcheck_exits_1_for_missing_last_tick_key(tmp_path):
    """heartbeat.json missing 'last_tick' key → unhealthy."""
    (tmp_path / "heartbeat.json").write_text(json.dumps({"successful_fields": 3}))
    code = run_healthcheck(str(tmp_path))
    assert code == 1


def test_healthcheck_respects_custom_max_age(tmp_path):
    """Custom HEALTHCHECK_MAX_AGE_HOURS=2 → 3h old heartbeat is unhealthy."""
    make_heartbeat(tmp_path, age_hours=3)
    code = run_healthcheck(str(tmp_path), max_age_hours=2)
    assert code == 1


@pytest.mark.asyncio
async def test_tick_scheduler_writes_heartbeat(tmp_path):
    """daily_tick() writes heartbeat.json with correct structure."""
    context = MagicMock()
    context.field_id = 1

    runner = MagicMock()
    runner.context = context
    runner.tick.return_value = []

    scheduler = TickScheduler(
        contexts=[context],
        state_dir=str(tmp_path),
        event_dispatcher=None,
    )
    scheduler.runners = {1: runner}

    await scheduler.daily_tick()

    heartbeat_path = tmp_path / "heartbeat.json"
    assert heartbeat_path.exists()

    data = json.loads(heartbeat_path.read_text())
    assert "last_tick" in data
    assert "successful_fields" in data
    assert "total_fields" in data
    assert data["total_fields"] == 1


@pytest.mark.asyncio
async def test_tick_scheduler_heartbeat_reflects_failures(tmp_path):
    """Heartbeat successful_fields is 0 when tick raises an exception."""
    context = MagicMock()
    context.field_id = 1

    runner = MagicMock()
    runner.context = context
    runner.tick.side_effect = RuntimeError("boom")

    scheduler = TickScheduler(
        contexts=[context],
        state_dir=str(tmp_path),
        event_dispatcher=None,
    )
    scheduler.runners = {1: runner}

    await scheduler.daily_tick()

    data = json.loads((tmp_path / "heartbeat.json").read_text())
    assert data["total_fields"] == 1
    assert data["successful_fields"] == 0
