import datetime
import json
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from models.sim_context import SimContext
from models.planting_plan import FieldOperation
from scheduler.calendar_driven_runner import CalendarDrivenRunner
from utils.state_manager import StateManager, FieldStateSnapshot


@pytest.fixture
def basic_context():
    return SimContext(
        field_id=42,
        field_name="Test Field",
        field_size=10.0,
        start_date=datetime.datetime(2024, 10, 1),
        crop_type="Potato",
        variety="Belana"
    )


def test_save_creates_json_file(tmp_path, basic_context):
    """
    Test 1: save() erstellt Datei mit korrektem Inhalt
    """
    state_manager = StateManager(str(tmp_path))
    
    runner = CalendarDrivenRunner(basic_context)
    runner.tick(datetime.date(2024, 10, 15))
    
    state_manager.save(runner)
    
    state_file = tmp_path / "field_42.json"
    assert state_file.exists()
    
    with open(state_file, 'r') as f:
        data = json.load(f)
    
    assert data["field_id"] == 42
    assert "context" in data
    assert "planting_operations" in data
    assert "protection_operations" in data


def test_load_returns_none_for_unknown_field(tmp_path):
    """
    Test 2: load() gibt None zurück für unbekanntes Feld
    """
    state_manager = StateManager(str(tmp_path))
    snapshot = state_manager.load(999)
    
    assert snapshot is None


def test_save_and_load_roundtrip(tmp_path, basic_context):
    """
    Test 3: load() stellt gespeicherten State korrekt wieder her
    """
    state_manager = StateManager(str(tmp_path))
    
    runner = CalendarDrivenRunner(basic_context)
    runner.tick(datetime.date(2024, 10, 15))
    
    state_manager.save(runner)
    
    snapshot = state_manager.load(42)
    
    assert snapshot is not None
    assert snapshot.field_id == 42
    assert snapshot.context.field_id == 42
    assert len(snapshot.planting_ops) > 0


def test_apply_snapshot_prevents_re_execution(basic_context):
    """
    Test 4 (Integration): apply_state_snapshot() verhindert Re-Execution
    """
    runner = CalendarDrivenRunner(basic_context)
    events_first = runner.tick(datetime.date(2024, 11, 1))
    
    snapshot = runner.get_state_snapshot(last_tick_date=datetime.date(2024, 11, 1))
    
    runner2 = CalendarDrivenRunner(basic_context)
    runner2.apply_state_snapshot(snapshot)
    
    events_second = runner2.tick(datetime.date(2024, 11, 1))
    assert len(events_second) == 0


def test_tick_scheduler_restores_state_on_init(tmp_path):
    """
    Test 5: TickScheduler lädt State beim Start
    """
    from scheduler.tick_scheduler import TickScheduler
    
    context = SimContext(
        field_id=1,
        field_name="Field 1",
        field_size=10.0,
        start_date=datetime.datetime(2024, 10, 1),
        crop_type="Potato",
        variety="Belana"
    )
    
    state_file = tmp_path / "field_1.json"
    state_data = {
        "field_id": 1,
        "last_tick_date": "2024-11-01",
        "context": {
            "field_id": 1,
            "field_name": "Field 1",
            "field_size": 10.0,
            "soil_type": "sand",
            "start_date": "2024-10-01T00:00:00",
            "crop_type": "Potato",
            "variety": "Belana",
            "fuel_variation": 0.1
        },
        "planting_operations": [
            {"phase": "soil_preparation", "sequence": 1, "actual_date": "2024-10-05T08:30:00"}
        ],
        "protection_operations": []
    }
    
    with open(state_file, 'w') as f:
        json.dump(state_data, f)
    
    scheduler = TickScheduler([context], state_dir=str(tmp_path))
    
    assert 1 in scheduler.runners
    runner = scheduler.runners[1]
    
    soil_prep_phase = runner.planting_plan_service.planting_plan.phases[0]
    first_op = soil_prep_phase.operations[0]
    assert first_op.actual_date is not None


def test_get_state_snapshot_captures_current_state(basic_context):
    """
    Test 6: get_state_snapshot() erfasst den aktuellen State korrekt
    """
    runner = CalendarDrivenRunner(basic_context)
    runner.tick(datetime.date(2024, 10, 15))
    
    snapshot = runner.get_state_snapshot(last_tick_date=datetime.date(2024, 10, 15))
    
    assert snapshot.field_id == 42
    assert snapshot.last_tick_date == datetime.date(2024, 10, 15)
    assert snapshot.context.field_id == 42
    assert len(snapshot.planting_ops) > 0


def test_apply_snapshot_restores_protection_ops(basic_context):
    """
    Test 7: apply_state_snapshot() stellt auch Protection-Ops wieder her
    """
    runner = CalendarDrivenRunner(basic_context)
    
    runner.tick(datetime.date(2025, 5, 1))
    
    if runner.protection_plan_service:
        snapshot = runner.get_state_snapshot(last_tick_date=datetime.date(2025, 5, 1))
        
        runner2 = CalendarDrivenRunner(basic_context)
        runner2.apply_state_snapshot(snapshot)
        
        if runner2.protection_plan_service and len(snapshot.protection_ops) > 0:
            first_protection_op = runner2.protection_plan_service.operations[0]
            if snapshot.protection_ops[0].get('actual_date'):
                assert first_protection_op.actual_date is not None
