"""
Tests for DecisionManager priority logic with irrigation (Issue #40)

Verifies that WorkTypePriorityStrategy correctly handles irrigation candidates
and that priority rules are fully encapsulated in the strategy class.
"""
import pytest
from models.planting_plan import FieldOperationEvent
from scheduler.decision_manager import DecisionManager, WorkTypePriorityStrategy
from models.worktypes import WorkType, LOW_PRIORITY_WORKTYPES


@pytest.fixture
def decision_manager():
    """Create a DecisionManager with WorkTypePriorityStrategy"""
    return DecisionManager(WorkTypePriorityStrategy())


def create_mock_operation(worktype: int, name: str = None) -> FieldOperationEvent:
    """Helper to create a mock operation with a specific worktype"""
    event = FieldOperationEvent(
        worktype=worktype,
        start_date='2022-01-01 12:00:00',
        end_date='2022-01-01 13:00:00',
        area=10.0,
        distance=0,
        distanceWorked=0,
        duration=3600,
        durationWorked=3600,
        fuel=5.0,
        worktype_text=name or f'Operation {worktype}'
    )
    return event


class TestWorkTypePriorityStrategy:
    """Test WorkTypePriorityStrategy with various operation combinations"""
    
    def test_empty_operations_returns_none(self, decision_manager):
        """Empty operations list should return None"""
        result = decision_manager.decide([])
        assert result is None
    
    def test_single_high_priority_operation_selected(self, decision_manager):
        """Single high-priority operation should be selected"""
        planting_op = create_mock_operation(WorkType.PFLANZEN, "Planting")
        
        result = decision_manager.decide([planting_op])
        
        assert result == [planting_op]
    
    def test_single_low_priority_operation_selected(self, decision_manager):
        """Single low-priority operation should be selected when it's the only option"""
        irrigation_op = create_mock_operation(WorkType.BEREGNEN, "Irrigation")
        
        result = decision_manager.decide([irrigation_op])
        
        assert result == [irrigation_op]
    
    def test_multiple_high_priority_operations_all_selected(self, decision_manager):
        """Multiple high-priority operations should all be selected"""
        planting_op = create_mock_operation(WorkType.PFLANZEN, "Planting")
        plowing_op = create_mock_operation(WorkType.PFLUEGEN, "Plowing")
        
        result = decision_manager.decide([planting_op, plowing_op])
        
        assert len(result) == 2
        assert planting_op in result
        assert plowing_op in result
    
    def test_multiple_low_priority_operations_all_selected(self, decision_manager):
        """Multiple low-priority operations should all be selected when no high-priority ops exist"""
        irrigation_op = create_mock_operation(WorkType.BEREGNEN, "Irrigation")
        spraying_op = create_mock_operation(WorkType.SPRITZEN, "Spraying")
        
        result = decision_manager.decide([irrigation_op, spraying_op])
        
        assert len(result) == 2
        assert irrigation_op in result
        assert spraying_op in result


class TestIrrigationPriority:
    """Test irrigation-specific priority behavior"""
    
    def test_irrigation_suppressed_by_planting(self, decision_manager):
        """Irrigation should be suppressed when planting operation exists"""
        planting_op = create_mock_operation(WorkType.PFLANZEN, "Planting")
        irrigation_op = create_mock_operation(WorkType.BEREGNEN, "Irrigation")
        
        result = decision_manager.decide([planting_op, irrigation_op])
        
        assert len(result) == 1
        assert planting_op in result
        assert irrigation_op not in result
    
    def test_irrigation_suppressed_by_plowing(self, decision_manager):
        """Irrigation should be suppressed when plowing operation exists"""
        plowing_op = create_mock_operation(WorkType.PFLUEGEN, "Plowing")
        irrigation_op = create_mock_operation(WorkType.BEREGNEN, "Irrigation")
        
        result = decision_manager.decide([plowing_op, irrigation_op])
        
        assert len(result) == 1
        assert plowing_op in result
        assert irrigation_op not in result
    
    def test_irrigation_suppressed_by_fertilization(self, decision_manager):
        """Irrigation should be suppressed when fertilization operation exists"""
        fertilization_op = create_mock_operation(WorkType.MINERALISCHE_DUENGUNG, "Fertilization")
        irrigation_op = create_mock_operation(WorkType.BEREGNEN, "Irrigation")
        
        result = decision_manager.decide([fertilization_op, irrigation_op])
        
        assert len(result) == 1
        assert fertilization_op in result
        assert irrigation_op not in result
    
    def test_irrigation_suppressed_by_harvesting(self, decision_manager):
        """Irrigation should be suppressed when harvesting operation exists"""
        harvesting_op = create_mock_operation(WorkType.DRESCHEN, "Harvesting")
        irrigation_op = create_mock_operation(WorkType.BEREGNEN, "Irrigation")
        
        result = decision_manager.decide([harvesting_op, irrigation_op])
        
        assert len(result) == 1
        assert harvesting_op in result
        assert irrigation_op not in result
    
    def test_irrigation_selected_when_only_spraying_present(self, decision_manager):
        """Irrigation should be selected alongside spraying (both low-priority)"""
        spraying_op = create_mock_operation(WorkType.SPRITZEN, "Spraying")
        irrigation_op = create_mock_operation(WorkType.BEREGNEN, "Irrigation")
        
        result = decision_manager.decide([spraying_op, irrigation_op])
        
        assert len(result) == 2
        assert spraying_op in result
        assert irrigation_op in result
    
    def test_irrigation_selected_when_no_high_priority_ops(self, decision_manager):
        """Irrigation should be selected when no high-priority operations exist"""
        irrigation_op = create_mock_operation(WorkType.BEREGNEN, "Irrigation")
        
        result = decision_manager.decide([irrigation_op])
        
        assert len(result) == 1
        assert irrigation_op in result


class TestMixedOperationTypes:
    """Test complex scenarios with multiple operation types"""
    
    def test_multiple_high_priority_suppress_multiple_low_priority(self, decision_manager):
        """Multiple high-priority ops should suppress all low-priority ops"""
        planting_op = create_mock_operation(WorkType.PFLANZEN, "Planting")
        plowing_op = create_mock_operation(WorkType.PFLUEGEN, "Plowing")
        irrigation_op = create_mock_operation(WorkType.BEREGNEN, "Irrigation")
        spraying_op = create_mock_operation(WorkType.SPRITZEN, "Spraying")
        
        result = decision_manager.decide([planting_op, plowing_op, irrigation_op, spraying_op])
        
        assert len(result) == 2
        assert planting_op in result
        assert plowing_op in result
        assert irrigation_op not in result
        assert spraying_op not in result
    
    def test_single_high_priority_suppresses_multiple_low_priority(self, decision_manager):
        """Single high-priority op should suppress all low-priority ops"""
        planting_op = create_mock_operation(WorkType.PFLANZEN, "Planting")
        irrigation_op = create_mock_operation(WorkType.BEREGNEN, "Irrigation")
        spraying_op = create_mock_operation(WorkType.SPRITZEN, "Spraying")
        
        result = decision_manager.decide([planting_op, irrigation_op, spraying_op])
        
        assert len(result) == 1
        assert planting_op in result
        assert irrigation_op not in result
        assert spraying_op not in result
    
    def test_all_operation_types_together(self, decision_manager):
        """Test with soil prep, planting, fertilization, protection, irrigation"""
        plowing_op = create_mock_operation(WorkType.PFLUEGEN, "Plowing")
        planting_op = create_mock_operation(WorkType.PFLANZEN, "Planting")
        fertilization_op = create_mock_operation(WorkType.MINERALISCHE_DUENGUNG, "Fertilization")
        spraying_op = create_mock_operation(WorkType.SPRITZEN, "Spraying")
        irrigation_op = create_mock_operation(WorkType.BEREGNEN, "Irrigation")
        
        result = decision_manager.decide([
            plowing_op, planting_op, fertilization_op, spraying_op, irrigation_op
        ])
        
        # Should select all high-priority ops
        assert len(result) == 3
        assert plowing_op in result
        assert planting_op in result
        assert fertilization_op in result
        # Should suppress low-priority ops
        assert spraying_op not in result
        assert irrigation_op not in result


class TestLowPriorityWorktypes:
    """Test that LOW_PRIORITY_WORKTYPES constant is correctly defined"""
    
    def test_low_priority_worktypes_includes_irrigation(self):
        """LOW_PRIORITY_WORKTYPES should include irrigation (worktype 15)"""
        assert WorkType.BEREGNEN in LOW_PRIORITY_WORKTYPES
        assert 15 in LOW_PRIORITY_WORKTYPES
    
    def test_low_priority_worktypes_includes_spraying(self):
        """LOW_PRIORITY_WORKTYPES should include spraying (worktype 14)"""
        assert WorkType.SPRITZEN in LOW_PRIORITY_WORKTYPES
        assert 14 in LOW_PRIORITY_WORKTYPES
    
    def test_low_priority_worktypes_count(self):
        """LOW_PRIORITY_WORKTYPES should contain exactly 2 worktypes"""
        assert len(LOW_PRIORITY_WORKTYPES) == 2


class TestStrategyEncapsulation:
    """Test that priority logic is fully encapsulated in strategy"""
    
    def test_strategy_has_select_operation_method(self):
        """Strategy should have select_operation method"""
        strategy = WorkTypePriorityStrategy()
        assert hasattr(strategy, 'select_operation')
        assert callable(strategy.select_operation)
    
    def test_decision_manager_delegates_to_strategy(self, decision_manager):
        """DecisionManager should delegate to strategy"""
        planting_op = create_mock_operation(WorkType.PFLANZEN, "Planting")
        irrigation_op = create_mock_operation(WorkType.BEREGNEN, "Irrigation")
        
        # DecisionManager.decide should call strategy.select_operation
        result = decision_manager.decide([planting_op, irrigation_op])
        
        # Verify result matches expected strategy behavior
        assert len(result) == 1
        assert planting_op in result
    
    def test_strategy_is_swappable(self):
        """Strategy should be swappable (Strategy Pattern)"""
        # Create a custom strategy
        class AlwaysSelectAllStrategy:
            def select_operation(self, operations):
                return operations if operations else None
        
        custom_manager = DecisionManager(AlwaysSelectAllStrategy())
        
        planting_op = create_mock_operation(WorkType.PFLANZEN, "Planting")
        irrigation_op = create_mock_operation(WorkType.BEREGNEN, "Irrigation")
        
        result = custom_manager.decide([planting_op, irrigation_op])
        
        # Custom strategy should select all
        assert len(result) == 2
        assert planting_op in result
        assert irrigation_op in result


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_operation_without_worktype_attribute(self, decision_manager):
        """Operations without worktype attribute should be handled gracefully"""
        class MockOp:
            pass
        
        mock_op = MockOp()
        planting_op = create_mock_operation(WorkType.PFLANZEN, "Planting")
        
        # Should not crash
        result = decision_manager.decide([mock_op, planting_op])
        
        # Should filter out the mock_op (no worktype)
        assert planting_op in result
    
    def test_operation_with_none_worktype(self, decision_manager):
        """Operations with None worktype should be handled gracefully"""
        class MockOp:
            worktype = None
        
        mock_op = MockOp()
        planting_op = create_mock_operation(WorkType.PFLANZEN, "Planting")
        
        # Should not crash
        result = decision_manager.decide([mock_op, planting_op])
        
        # Should filter out the mock_op (None worktype)
        assert planting_op in result
    
    def test_operation_with_unknown_worktype(self, decision_manager):
        """Operations with unknown worktype should be treated as high-priority"""
        unknown_op = create_mock_operation(9999, "Unknown Operation")
        irrigation_op = create_mock_operation(WorkType.BEREGNEN, "Irrigation")
        
        result = decision_manager.decide([unknown_op, irrigation_op])
        
        # Unknown worktype (9999) is not in LOW_PRIORITY_WORKTYPES
        # So it should be treated as high-priority and suppress irrigation
        assert len(result) == 1
        assert unknown_op in result
        assert irrigation_op not in result
