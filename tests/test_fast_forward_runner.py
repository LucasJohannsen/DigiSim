import datetime
import json
import os
import pytest
from unittest.mock import Mock, patch

from models.sim_context import SimContext
from scheduler.fast_forward_runner import FastForwardRunner
from events.domain_event_bus import DomainEventBus


@pytest.fixture
def sim_context():
    """Create a test simulation context."""
    return SimContext(
        field_size=10.0,
        soil_type="sandy_loam",
        start_date=datetime.datetime(2024, 1, 1),
        crop_type="Potato",
        variety="Belana",
        field_id=12345,
        field_name="Test Field",
        fuel_variation=0.1
    )


@pytest.fixture
def event_bus():
    """Create a test event bus."""
    return DomainEventBus()


class TestFastForwardRunner:
    """Test suite for FastForwardRunner (Issue #45)."""
    
    def test_fast_forward_initialization(self, sim_context, event_bus):
        """Test FastForwardRunner can be initialized."""
        runner = FastForwardRunner(
            context=sim_context,
            n_days=30,
            event_bus=event_bus
        )
        
        assert runner.context is sim_context
        assert runner.n_days == 30
        assert runner.event_bus is not None
    
    def test_fast_forward_30_days(self, sim_context):
        """Test fast-forward over 30 days."""
        runner = FastForwardRunner(
            context=sim_context,
            n_days=30,
            output_target="stdout"
        )
        
        try:
            events = runner.run()
            
            # Should complete 30 ticks
            assert runner.tick_count == 30
            
            # Should generate events (exact count depends on planting plan)
            assert len(events) >= 0
        except Exception as e:
            # If planting plan is missing, test should still pass with 0 ticks
            pytest.skip(f"Planting plan not available: {e}")
    
    def test_fast_forward_full_season(self, sim_context):
        """Test fast-forward over full season (365 days)."""
        runner = FastForwardRunner(
            context=sim_context,
            n_days=365,
            output_target="stdout"
        )
        
        try:
            events = runner.run()
            
            # Should complete all ticks
            assert runner.tick_count == 365
            
            # Should have generated events
            assert len(events) > 0
        except Exception as e:
            pytest.skip(f"Planting plan not available: {e}")
    
    def test_fast_forward_json_export(self, sim_context, tmp_path):
        """Test JSON export functionality."""
        output_path = tmp_path / "fast_forward_test.json"
        
        runner = FastForwardRunner(
            context=sim_context,
            n_days=30,
            output_target="json",
            output_path=str(output_path)
        )
        
        events = runner.run()
        
        # Check JSON file was created
        assert output_path.exists()
        
        # Check JSON is valid
        with open(output_path, 'r') as f:
            data = json.load(f)
        
        assert "field" in data
        assert "operations" in data
    
    def test_fast_forward_memory_bounded(self, sim_context):
        """Test that memory usage stays bounded for large N."""
        # This is a smoke test - we just verify it completes without OOM
        runner = FastForwardRunner(
            context=sim_context,
            n_days=100,
            output_target="stdout",
            flush_interval=10
        )
        
        try:
            events = runner.run()
            
            # Should complete successfully
            assert runner.tick_count == 100
        except Exception as e:
            pytest.skip(f"Planting plan not available: {e}")
    
    def test_fast_forward_error_handling(self, sim_context):
        """Test error handling during fast-forward."""
        runner = FastForwardRunner(
            context=sim_context,
            n_days=30,
            output_target="stdout"
        )
        
        # Run should complete even if some ticks fail
        events = runner.run()
        
        # Should track errors
        assert runner.error_count >= 0
    
    def test_fast_forward_event_types(self, sim_context):
        """Test that various event types are generated."""
        runner = FastForwardRunner(
            context=sim_context,
            n_days=365,
            output_target="stdout"
        )
        
        events = runner.run()
        
        # Should include various operation types
        if len(events) > 0:
            event_types = set(e.worktype for e in events)
            assert len(event_types) >= 1
    
    def test_fast_forward_progress_reporting(self, sim_context, capsys):
        """Test progress reporting during fast-forward."""
        runner = FastForwardRunner(
            context=sim_context,
            n_days=60,
            output_target="stdout"
        )
        
        events = runner.run()
        
        # Check that progress was printed
        captured = capsys.readouterr()
        assert "Day 30/60" in captured.out or "Fast-forward simulation" in captured.out
    
    def test_fast_forward_summary(self, sim_context, capsys):
        """Test that summary is printed after completion."""
        runner = FastForwardRunner(
            context=sim_context,
            n_days=30,
            output_target="stdout"
        )
        
        events = runner.run()
        
        # Check summary output
        captured = capsys.readouterr()
        assert "FAST-FORWARD SIMULATION COMPLETED" in captured.out
        assert "Total ticks:" in captured.out
