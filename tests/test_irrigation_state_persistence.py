"""
Tests for IrrigationSimulator state persistence (Issue #33)
"""
import pytest
import numpy as np
import datetime
from models.sim_context import SimContext
from services.irrigation_service import IrrigationSimulator


@pytest.fixture
def sim_context():
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
def moisture_data():
    """Create sample moisture data for 365 days"""
    dates = [datetime.date(2022, 1, 1) + datetime.timedelta(days=i) for i in range(365)]
    moisture_values = [60.0] * 365  # Start with 60% moisture
    
    return {
        "coords": {"lat": 52.0, "lon": 13.0},
        "dates": dates,
        "moisture_data": moisture_values
    }


def test_irrigation_simulator_get_state(sim_context, moisture_data):
    """Test that get_state returns correct structure"""
    simulator = IrrigationSimulator(sim_context, moisture_data)

    # Trigger some irrigation to change state
    simulator.trigger_irrigation(date=datetime.date(2022, 1, 10), irrigation_amount=15.0)
    simulator.trigger_irrigation(date=datetime.date(2022, 1, 20), irrigation_amount=10.0)

    state = simulator.get_state()

    assert "irrigation" in state
    assert "updated_moisture" in state
    assert isinstance(state["irrigation"], list)
    assert isinstance(state["updated_moisture"], list)
    assert len(state["irrigation"]) == 365
    assert len(state["updated_moisture"]) == 365

    # Check that irrigation was recorded
    assert state["irrigation"][10] == 15.0
    assert state["irrigation"][20] == 10.0


def test_irrigation_simulator_apply_state(sim_context, moisture_data):
    """Test that apply_state correctly restores simulator state"""
    # Create first simulator and trigger irrigation
    simulator1 = IrrigationSimulator(sim_context, moisture_data)
    simulator1.trigger_irrigation(date=datetime.date(2022, 1, 10), irrigation_amount=15.0)
    simulator1.trigger_irrigation(date=datetime.date(2022, 1, 20), irrigation_amount=10.0)

    # Get state from first simulator
    state = simulator1.get_state()

    # Create second simulator and apply state
    simulator2 = IrrigationSimulator(sim_context, moisture_data)
    simulator2.apply_state(state)

    # Verify state was restored
    np.testing.assert_array_equal(simulator2.irrigation, simulator1.irrigation)
    np.testing.assert_array_equal(simulator2.updated_moisture, simulator1.updated_moisture)


def test_irrigation_simulator_continuity_after_restore(sim_context, moisture_data):
    """
    Test that a restored simulator produces the same output as one that ran continuously.
    This is the key acceptance criterion from Issue #33.
    """
    # Simulator 1: Run continuously for 30 days
    simulator_continuous = IrrigationSimulator(sim_context, moisture_data)

    for day in range(30):
        date = sim_context.start_date + datetime.timedelta(days=day)
        status = simulator_continuous.get_status_for_day(date)
        if status["needs_irrigation"]:
            simulator_continuous.trigger_irrigation(date, irrigation_amount=status["irrigation_needed"])

    continuous_state_day30 = simulator_continuous.get_state()

    # Simulator 2: Run for 15 days, save state, restore, continue
    simulator_restored = IrrigationSimulator(sim_context, moisture_data)

    # Run first 15 days
    for day in range(15):
        date = sim_context.start_date + datetime.timedelta(days=day)
        status = simulator_restored.get_status_for_day(date)
        if status["needs_irrigation"]:
            simulator_restored.trigger_irrigation(date, irrigation_amount=status["irrigation_needed"])

    # Save and restore state
    saved_state = simulator_restored.get_state()
    simulator_restored = IrrigationSimulator(sim_context, moisture_data)
    simulator_restored.apply_state(saved_state)

    # Continue for remaining 15 days
    for day in range(15, 30):
        date = sim_context.start_date + datetime.timedelta(days=day)
        status = simulator_restored.get_status_for_day(date)
        if status["needs_irrigation"]:
            simulator_restored.trigger_irrigation(date, irrigation_amount=status["irrigation_needed"])

    restored_state_day30 = simulator_restored.get_state()

    # Both simulators should have identical state after 30 days
    np.testing.assert_array_almost_equal(
        np.array(continuous_state_day30["irrigation"]),
        np.array(restored_state_day30["irrigation"]),
        decimal=2,
        err_msg="Irrigation arrays should match after restore"
    )

    np.testing.assert_array_almost_equal(
        np.array(continuous_state_day30["updated_moisture"]),
        np.array(restored_state_day30["updated_moisture"]),
        decimal=2,
        err_msg="Updated moisture arrays should match after restore"
    )


def test_irrigation_simulator_apply_empty_state(sim_context, moisture_data):
    """Test that apply_state handles None/empty state gracefully"""
    simulator = IrrigationSimulator(sim_context, moisture_data)
    
    # Should not raise error
    simulator.apply_state(None)
    simulator.apply_state({})
    
    # Arrays should be initialized to defaults
    assert len(simulator.irrigation) == 365
    assert len(simulator.updated_moisture) == 365


def test_irrigation_simulator_apply_malformed_state(sim_context, moisture_data):
    """Test that apply_state handles malformed state by resetting to defaults"""
    simulator = IrrigationSimulator(sim_context, moisture_data)
    
    # Apply state with wrong array lengths
    malformed_state = {
        "irrigation": [1.0, 2.0, 3.0],  # Too short
        "updated_moisture": [50.0, 51.0]  # Too short
    }
    
    simulator.apply_state(malformed_state)
    
    # Arrays should be reset to correct length
    assert len(simulator.irrigation) == 365
    assert len(simulator.updated_moisture) == 365
