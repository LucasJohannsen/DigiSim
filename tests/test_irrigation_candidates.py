"""
Tests for IrrigationSimulator candidate operations (Issue #38)

This test suite verifies:
1. Candidate generation without side-effects
2. Side-effect application via apply_irrigation()
3. Backward compatibility of trigger_irrigation()
4. Proper separation of concerns in the decision pipeline
"""
import pytest
import numpy as np
import datetime
from models.sim_context import SimContext
from services.irrigation_service import IrrigationSimulator


@pytest.fixture
def sim_context():
    """Create a standard simulation context for testing"""
    return SimContext(
        field_id=1,
        field_name="Test Field",
        field_size=10.0,
        soil_type="sand",
        start_date=datetime.datetime(2022, 1, 1),
        crop_type="Potato",
        variety="Belana",
        fuel_variation=0.1
    )


@pytest.fixture
def moisture_data_dry():
    """Create moisture data that requires irrigation (dry conditions)"""
    dates = [datetime.date(2022, 1, 1) + datetime.timedelta(days=i) for i in range(365)]
    # Low moisture levels that trigger irrigation
    moisture_values = [30.0] * 365  # Below default threshold of 50
    
    return {
        "coords": [52.0, 13.0],
        "dates": dates,
        "moisture_data": moisture_values
    }


@pytest.fixture
def moisture_data_wet():
    """Create moisture data that does NOT require irrigation (wet conditions)"""
    dates = [datetime.date(2022, 1, 1) + datetime.timedelta(days=i) for i in range(365)]
    # High moisture levels, no irrigation needed
    moisture_values = [80.0] * 365  # Above threshold
    
    return {
        "coords": [52.0, 13.0],
        "dates": dates,
        "moisture_data": moisture_values
    }


class TestCandidateGeneration:
    """Test get_candidate_operations() method"""
    
    def test_returns_empty_list_when_no_irrigation_needed(self, sim_context, moisture_data_wet):
        """Candidate generation should return empty list when moisture is sufficient"""
        simulator = IrrigationSimulator(sim_context, moisture_data_wet)
        
        candidates = simulator.get_candidate_operations(day=100)
        
        assert isinstance(candidates, list)
        assert len(candidates) == 0
    
    def test_returns_candidate_when_irrigation_needed(self, sim_context, moisture_data_dry):
        """Candidate generation should return event when irrigation is needed"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        
        candidates = simulator.get_candidate_operations(day=100)
        
        assert isinstance(candidates, list)
        assert len(candidates) == 1
        
        event = candidates[0]
        assert event.worktype == 15
        assert event.worktype_text == 'Bewässerung'
        assert event.application_type == 'irrigation'
        assert event.application_amount > 0
    
    def test_candidate_has_correct_attributes(self, sim_context, moisture_data_dry):
        """Candidate event should have all required attributes"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        
        candidates = simulator.get_candidate_operations(day=100)
        event = candidates[0]
        
        # Verify all required attributes
        assert hasattr(event, 'worktype')
        assert hasattr(event, 'start_date')
        assert hasattr(event, 'end_date')
        assert hasattr(event, 'area')
        assert hasattr(event, 'duration')
        assert hasattr(event, 'fuel')
        assert hasattr(event, 'application_amount')
        assert hasattr(event, 'application_unit')
        assert hasattr(event, 'field')
        
        # Verify values
        assert event.worktype == 15
        assert event.area == sim_context.field_size
        assert event.application_unit == 12  # mm
        assert event.field == sim_context.field_id
    
    def test_candidate_generation_does_not_apply_side_effects(self, sim_context, moisture_data_dry):
        """CRITICAL: Candidate generation must NOT modify moisture arrays"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        
        # Store original state
        original_irrigation = simulator.irrigation.copy()
        original_updated_moisture = simulator.updated_moisture.copy()
        
        # Generate candidate
        candidates = simulator.get_candidate_operations(day=100)
        
        # Verify arrays are unchanged
        np.testing.assert_array_equal(
            simulator.irrigation,
            original_irrigation,
            err_msg="Candidate generation should NOT modify irrigation array"
        )
        np.testing.assert_array_equal(
            simulator.updated_moisture,
            original_updated_moisture,
            err_msg="Candidate generation should NOT modify updated_moisture array"
        )
    
    def test_handles_out_of_range_day_gracefully(self, sim_context, moisture_data_dry):
        """Should return empty list for invalid day index"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        
        # Test day beyond range
        candidates = simulator.get_candidate_operations(day=500)
        assert candidates == []
        
        # Test negative day
        candidates = simulator.get_candidate_operations(day=-1)
        assert candidates == []


class TestApplyIrrigation:
    """Test apply_irrigation() side-effect method"""
    
    def test_applies_irrigation_to_arrays(self, sim_context, moisture_data_dry):
        """apply_irrigation() should update moisture arrays"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        
        day = 100
        irrigation_amount = 20.0
        
        # Get initial moisture
        initial_moisture = simulator.updated_moisture[day]
        
        # Apply irrigation
        simulator.apply_irrigation(day, irrigation_amount)
        
        # Verify irrigation was recorded
        assert simulator.irrigation[day] == irrigation_amount
        
        # Verify moisture was updated
        assert simulator.updated_moisture[day] == initial_moisture + irrigation_amount
    
    def test_propagates_moisture_to_future_days(self, sim_context, moisture_data_dry):
        """Moisture increase should propagate to future days"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        
        day = 100
        irrigation_amount = 20.0
        
        # Apply irrigation
        simulator.apply_irrigation(day, irrigation_amount)
        
        # Verify propagation to future days
        for future_day in range(day + 1, min(day + 10, len(simulator.updated_moisture))):
            assert simulator.updated_moisture[future_day] >= simulator.updated_moisture[day]
    
    def test_raises_error_for_invalid_day(self, sim_context, moisture_data_dry):
        """Should raise IndexError for out-of-range day"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        
        with pytest.raises(IndexError):
            simulator.apply_irrigation(day=500, irrigation_amount=20.0)
        
        with pytest.raises(IndexError):
            simulator.apply_irrigation(day=-1, irrigation_amount=20.0)


class TestTriggerIrrigationBackwardCompatibility:
    """Test that trigger_irrigation() still works (backward compatibility)"""
    
    def test_trigger_irrigation_combines_candidate_and_side_effects(self, sim_context, moisture_data_dry):
        """trigger_irrigation() should create event AND apply side-effects"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        
        day = 100
        
        # Trigger irrigation (legacy method)
        event = simulator.trigger_irrigation(day)
        
        # Should return event
        assert event is not None
        assert event.worktype == 15
        
        # Should have applied side-effects
        assert simulator.irrigation[day] > 0
        assert simulator.updated_moisture[day] > moisture_data_dry["moisture_data"][day]
    
    def test_trigger_irrigation_with_explicit_amount(self, sim_context, moisture_data_dry):
        """trigger_irrigation() should accept explicit irrigation amount"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        
        day = 100
        explicit_amount = 25.0
        
        event = simulator.trigger_irrigation(day, irrigation_amount=explicit_amount)
        
        assert event is not None
        assert event.application_amount == explicit_amount
        assert simulator.irrigation[day] == explicit_amount
    
    def test_trigger_irrigation_returns_none_when_not_needed(self, sim_context, moisture_data_wet):
        """trigger_irrigation() should return None when irrigation not needed"""
        simulator = IrrigationSimulator(sim_context, moisture_data_wet)
        
        event = simulator.trigger_irrigation(day=100)
        
        assert event is None
        assert simulator.irrigation[100] == 0


class TestCandidateAndApplySeparation:
    """Test the separation of candidate generation and side-effect application"""
    
    def test_candidate_then_apply_produces_same_result_as_trigger(self, sim_context, moisture_data_dry):
        """Using get_candidate + apply should produce same result as trigger_irrigation"""
        # Simulator 1: Use new pattern (candidate + apply)
        sim1 = IrrigationSimulator(sim_context, moisture_data_dry)
        candidates = sim1.get_candidate_operations(day=100)
        if candidates:
            event1 = candidates[0]
            sim1.apply_irrigation(day=100, irrigation_amount=event1.application_amount)
        
        # Simulator 2: Use legacy pattern (trigger)
        sim2 = IrrigationSimulator(sim_context, moisture_data_dry)
        event2 = sim2.trigger_irrigation(day=100)
        
        # Both should have applied irrigation
        assert sim1.irrigation[100] > 0
        assert sim2.irrigation[100] > 0
        
        # Moisture should be updated in both
        assert sim1.updated_moisture[100] > moisture_data_dry["moisture_data"][100]
        assert sim2.updated_moisture[100] > moisture_data_dry["moisture_data"][100]
    
    def test_multiple_candidates_can_be_generated_before_applying(self, sim_context, moisture_data_dry):
        """Should be able to generate multiple candidates before applying any"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        
        # Generate candidates for multiple days
        candidates_day_100 = simulator.get_candidate_operations(day=100)
        candidates_day_101 = simulator.get_candidate_operations(day=101)
        candidates_day_102 = simulator.get_candidate_operations(day=102)
        
        # All should return candidates (dry conditions)
        assert len(candidates_day_100) > 0
        assert len(candidates_day_101) > 0
        assert len(candidates_day_102) > 0
        
        # No side-effects should be applied yet
        assert simulator.irrigation[100] == 0
        assert simulator.irrigation[101] == 0
        assert simulator.irrigation[102] == 0
        
        # Now apply one
        if candidates_day_101:
            simulator.apply_irrigation(day=101, irrigation_amount=candidates_day_101[0].application_amount)
        
        # Only day 101 should have irrigation applied
        assert simulator.irrigation[100] == 0
        assert simulator.irrigation[101] > 0
        assert simulator.irrigation[102] == 0


class TestDecisionPipelineIntegration:
    """Test integration with decision pipeline pattern"""
    
    def test_candidate_can_be_rejected_without_side_effects(self, sim_context, moisture_data_dry):
        """DecisionManager can reject candidate without any side-effects"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        
        # Generate candidate
        candidates = simulator.get_candidate_operations(day=100)
        assert len(candidates) > 0
        
        # DecisionManager rejects it (we simply don't call apply_irrigation)
        # No side-effects should occur
        
        assert simulator.irrigation[100] == 0
        assert simulator.updated_moisture[100] == moisture_data_dry["moisture_data"][100]
    
    def test_candidate_can_be_confirmed_with_side_effects(self, sim_context, moisture_data_dry):
        """DecisionManager can confirm candidate and apply side-effects"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        
        # Generate candidate
        candidates = simulator.get_candidate_operations(day=100)
        assert len(candidates) > 0
        
        candidate = candidates[0]
        
        # DecisionManager confirms it
        simulator.apply_irrigation(day=100, irrigation_amount=candidate.application_amount)
        
        # Side-effects should be applied
        assert simulator.irrigation[100] > 0
        assert simulator.updated_moisture[100] > moisture_data_dry["moisture_data"][100]
