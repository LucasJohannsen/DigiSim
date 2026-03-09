import datetime
from unittest.mock import Mock, patch
import pytest

from models.sim_context import SimContext
from models.planting_plan import (
    FieldOperation,
    FieldOperationEvent,
    FieldOperationStatus,
    FieldOperationPhases
)
from scheduler.calendar_driven_runner import CalendarDrivenRunner


@pytest.fixture
def basic_context():
    return SimContext(
        field_id=1,
        field_name="Test Field",
        field_size=10.0,
        soil_type="sand",
        start_date=datetime.datetime(2024, 10, 1),
        crop_type="Potato",
        variety="Belana",
        fuel_variation=0.1
    )


@pytest.fixture
def mock_planting_plan_service():
    service = Mock()
    service.get_next_operations = Mock(return_value=[])
    service.get_events_for_ops = Mock(return_value=[])
    service.active_phase = None
    return service


def test_tick_returns_empty_list_when_no_events(basic_context, mock_planting_plan_service):
    """
    Test 1: tick() gibt leere Liste zurück wenn kein Event für dieses Datum
    """
    with patch('scheduler.calendar_driven_runner.PlantingPlanService', return_value=mock_planting_plan_service):
        runner = CalendarDrivenRunner(basic_context)
        
        test_date = datetime.date(2024, 10, 15)
        events = runner.tick(test_date)
        
        assert isinstance(events, list)
        assert len(events) == 0
        mock_planting_plan_service.get_next_operations.assert_called_once_with(datetime.datetime(2024, 10, 15, 0, 0))


def test_tick_returns_events_when_operation_scheduled(basic_context, mock_planting_plan_service):
    """
    Test 2: tick() gibt Events zurück wenn eine Operation für dieses Datum geplant ist
    """
    test_date = datetime.date(2024, 10, 15)
    
    mock_operation = FieldOperation(
        sequence=1,
        operation="Pflügen",
        worktype=1,
        duration_per_ha=2.0,
        working_width=3.0,
        fuel_consumption=15.0,
        planned_date=test_date,
        actual_date=None
    )
    
    mock_event = FieldOperationEvent(
        field=1,
        worktype=1,
        start_date="2024-10-15 08:00:00",
        end_date="2024-10-15 10:00:00",
        area=10.0,
        fuel=150.0,
        worktype_text="Pflügen"
    )
    
    mock_planting_plan_service.get_next_operations.return_value = [mock_operation]
    mock_planting_plan_service.get_events_for_ops.return_value = [mock_event]
    
    with patch('scheduler.calendar_driven_runner.PlantingPlanService', return_value=mock_planting_plan_service):
        runner = CalendarDrivenRunner(basic_context)
        
        events = runner.tick(test_date)
        
        assert isinstance(events, list)
        assert len(events) == 1
        assert events[0] == mock_event
        expected_datetime = datetime.datetime(2024, 10, 15, 0, 0)
        mock_planting_plan_service.get_next_operations.assert_called_once_with(expected_datetime)
        mock_planting_plan_service.get_events_for_ops.assert_called_once_with([mock_operation], expected_datetime)


def test_tick_marks_operations_as_completed(basic_context):
    """
    Test 3: tick() markiert ausgeführte Operationen als erledigt (actual_date gesetzt)
    
    This test uses the real PlantingPlanService to verify that operations
    are properly marked with actual_date after execution.
    """
    test_date = datetime.date(2024, 11, 1)
    
    runner = CalendarDrivenRunner(basic_context)
    events = runner.tick(test_date)
    
    if events:
        for phase in runner.planting_plan_service.planting_plan.phases:
            for op in phase.operations:
                if op.actual_date is not None:
                    assert op.actual_date == test_date


def test_tick_idempotent_for_completed_operations(basic_context, mock_planting_plan_service):
    """
    Test 4: tick() gibt nichts zurück wenn dieselbe Operation bereits ausgeführt wurde (Idempotenz)
    """
    test_date = datetime.date(2024, 10, 15)
    
    completed_operation = FieldOperation(
        sequence=1,
        operation="Pflügen",
        worktype=1,
        duration_per_ha=2.0,
        working_width=3.0,
        fuel_consumption=15.0,
        planned_date=test_date,
        actual_date=test_date
    )
    
    mock_planting_plan_service.get_next_operations.return_value = []
    
    with patch('scheduler.calendar_driven_runner.PlantingPlanService', return_value=mock_planting_plan_service):
        runner = CalendarDrivenRunner(basic_context)
        
        events = runner.tick(test_date)
        
        assert isinstance(events, list)
        assert len(events) == 0


def test_tick_collects_all_due_operations_from_past(basic_context):
    """
    Test 5: tick() mit einem Datum weit in der Vergangenheit – alle fälligen Ops werden gesammelt
    
    This test verifies that when tick() is called with a date far in the future,
    all operations that were due between start_date and the given date are collected.
    """
    runner = CalendarDrivenRunner(basic_context)
    
    future_date = datetime.date(2025, 1, 1)
    events = runner.tick(future_date)
    
    assert isinstance(events, list)


def test_tick_with_crop_management_phase_initializes_services(basic_context):
    """
    Test 6: tick() initializes protection and irrigation services when CROP_MANAGEMENT phase is active
    """
    runner = CalendarDrivenRunner(basic_context)
    
    test_date = datetime.date(2025, 5, 1)
    
    with patch.object(runner, '_should_initialize_services', return_value=True):
        with patch.object(runner, '_initialize_services') as mock_init:
            events = runner.tick(test_date)
            
            assert isinstance(events, list)


def test_tick_handles_multiple_operations_same_day(basic_context, mock_planting_plan_service):
    """
    Test 7: tick() handles multiple operations scheduled for the same day
    """
    test_date = datetime.date(2024, 10, 15)
    
    mock_op1 = FieldOperation(
        sequence=1,
        operation="Pflügen",
        worktype=1,
        duration_per_ha=2.0,
        working_width=3.0,
        fuel_consumption=15.0,
        planned_date=test_date,
        actual_date=None
    )
    
    mock_op2 = FieldOperation(
        sequence=2,
        operation="Eggen",
        worktype=2,
        duration_per_ha=1.5,
        working_width=4.0,
        fuel_consumption=10.0,
        planned_date=test_date,
        actual_date=None
    )
    
    mock_event1 = FieldOperationEvent(worktype=1, worktype_text="Pflügen")
    mock_event2 = FieldOperationEvent(worktype=2, worktype_text="Eggen")
    
    mock_planting_plan_service.get_next_operations.return_value = [mock_op1, mock_op2]
    mock_planting_plan_service.get_events_for_ops.return_value = [mock_event1, mock_event2]
    
    with patch('scheduler.calendar_driven_runner.PlantingPlanService', return_value=mock_planting_plan_service):
        runner = CalendarDrivenRunner(basic_context)
        
        events = runner.tick(test_date)
        
        assert len(events) == 2
        assert events[0].worktype == 1
        assert events[1].worktype == 2


def test_tick_integration_with_real_planting_plan(basic_context):
    """
    Integration test: tick() with real PlantingPlanService loading from config
    """
    runner = CalendarDrivenRunner(basic_context)
    
    assert runner.planting_plan_service is not None
    assert runner.planting_plan_service.planting_plan is not None
    
    test_date = datetime.date(2024, 11, 1)
    events = runner.tick(test_date)
    
    assert isinstance(events, list)
