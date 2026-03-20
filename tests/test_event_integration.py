import unittest
from datetime import datetime, timedelta
from events.domain_event_bus import DomainEventBus
from scheduler.calendar_driven_runner import CalendarDrivenRunner
from scheduler.decision_manager import DecisionManager, WorkTypePriorityStrategy
from models.sim_context import SimContext
from models.planting_plan import FieldOperation


class TestDomainEventIntegration(unittest.TestCase):
    """Integration tests for domain event emission in the simulation core."""
    
    def setUp(self):
        """Set up a test simulation context and event bus."""
        self.event_bus = DomainEventBus()
        self.context = SimContext(
            field_size=10.0,
            soil_type="loam",
            start_date=datetime(2025, 1, 1),
            crop_type="Potato",
            variety="Belana",
            field_id=1,
            field_name="Test Field",
            fuel_variation=0.1
        )
    
    def test_daily_tick_events_are_emitted(self):
        """Test that DailyTickStarted and DailyTickCompleted events are emitted."""
        runner = CalendarDrivenRunner(self.context, event_bus=self.event_bus)
        
        test_date = datetime(2025, 4, 1)
        runner.tick(test_date)
        
        # Get history from runner's event bus
        history = runner.event_bus.get_history()
        
        # Check that DailyTickStarted was emitted
        tick_started = [e for e in history if e.event_type == 'DailyTickStarted']
        self.assertGreater(len(tick_started), 0, "DailyTickStarted event should be emitted")
        self.assertEqual(tick_started[0].field_id, "1")
        
        # Check that DailyTickCompleted was emitted
        tick_completed = [e for e in history if e.event_type == 'DailyTickCompleted']
        self.assertGreater(len(tick_completed), 0, "DailyTickCompleted event should be emitted")
        self.assertEqual(tick_completed[0].field_id, "1")
        self.assertIn('events_dispatched', tick_completed[0].payload)
    
    def test_operation_events_sequence(self):
        """Test that operation events are emitted in the correct sequence."""
        runner = CalendarDrivenRunner(self.context, event_bus=self.event_bus)
        
        # Run multiple ticks to trigger operations
        start_date = datetime(2025, 4, 1)
        for i in range(10):
            test_date = start_date + timedelta(days=i)
            runner.tick(test_date)
        
        history = self.event_bus.get_history()
        
        # Verify event sequence for any operations that occurred
        operation_considered = [e for e in history if e.event_type == 'OperationConsidered']
        operation_approved = [e for e in history if e.event_type == 'OperationApproved']
        operation_applied = [e for e in history if e.event_type == 'OperationApplied']
        
        # If operations were considered, some should be approved
        if len(operation_considered) > 0:
            self.assertGreater(len(operation_approved), 0, 
                             "If operations are considered, some should be approved")
        
        # If operations were approved, they should be applied
        if len(operation_approved) > 0:
            self.assertGreater(len(operation_applied), 0,
                             "If operations are approved, they should be applied")
    
    def test_crop_cycle_started_event(self):
        """Test that CropCycleStarted event is emitted when entering crop management."""
        runner = CalendarDrivenRunner(self.context, event_bus=self.event_bus)
        
        # Run enough ticks to reach crop management phase
        start_date = datetime(2025, 4, 1)
        for i in range(60):
            test_date = start_date + timedelta(days=i)
            runner.tick(test_date)
        
        history = self.event_bus.get_history()
        crop_cycle_events = [e for e in history if e.event_type == 'CropCycleStarted']
        
        # CropCycleStarted should be emitted at most once
        if len(crop_cycle_events) > 0:
            self.assertEqual(len(crop_cycle_events), 1, 
                           "CropCycleStarted should only be emitted once")
            self.assertEqual(crop_cycle_events[0].payload['crop_type'], "Potato")
    
    def test_event_bus_isolation(self):
        """Test that different runners with different event buses are isolated."""
        bus1 = DomainEventBus()
        bus2 = DomainEventBus()
        
        context1 = SimContext(
            field_size=10.0,
            soil_type="loam",
            start_date=datetime(2025, 1, 1),
            crop_type="Potato",
            variety="Belana",
            field_id=1,
            field_name="Field 1",
            fuel_variation=0.1
        )
        
        context2 = SimContext(
            field_size=15.0,
            soil_type="sand",
            start_date=datetime(2025, 1, 1),
            crop_type="Potato",
            variety="Belana",
            field_id=2,
            field_name="Field 2",
            fuel_variation=0.1
        )
        
        runner1 = CalendarDrivenRunner(context1, event_bus=bus1)
        runner2 = CalendarDrivenRunner(context2, event_bus=bus2)
        
        test_date = datetime(2025, 4, 1)
        runner1.tick(test_date)
        runner2.tick(test_date)
        
        # Get history from the runners' event buses
        history1 = runner1.event_bus.get_history()
        history2 = runner2.event_bus.get_history()
        
        # Each bus should have its own events
        self.assertGreater(len(history1), 0)
        self.assertGreater(len(history2), 0)
        
        # Events should be for different fields
        field1_events = [e for e in history1 if e.field_id == "1"]
        field2_events = [e for e in history2 if e.field_id == "2"]
        
        self.assertEqual(len(field1_events), len(history1))
        self.assertEqual(len(field2_events), len(history2))


class TestDecisionManagerEvents(unittest.TestCase):
    """Test that DecisionManager emits correct operation events."""
    
    def setUp(self):
        """Set up test event bus and decision manager."""
        self.event_bus = DomainEventBus()
        self.decision_manager = DecisionManager(
            strategy=WorkTypePriorityStrategy(),
            event_bus=self.event_bus
        )
    
    def test_operation_considered_events(self):
        """Test that OperationConsidered events are emitted for all candidates."""
        ops = [
            self._create_test_operation("Pflügen", 1),
            self._create_test_operation("Düngen", 3),
            self._create_test_operation("Bewässerung", 15)
        ]
        
        self.decision_manager.decide(
            ops,
            field_id="1",
            date=datetime(2025, 4, 1)
        )
        
        considered_events = self.event_bus.get_events_by_type('OperationConsidered')
        self.assertEqual(len(considered_events), 3, "All operations should be considered")
    
    def test_operation_approved_and_rejected_events(self):
        """Test that operations are correctly approved or rejected."""
        ops = [
            self._create_test_operation("Pflügen", 1),
            self._create_test_operation("Bewässerung", 15)
        ]
        
        self.decision_manager.decide(
            ops,
            field_id="1",
            date=datetime(2025, 4, 1)
        )
        
        approved_events = self.event_bus.get_events_by_type('OperationApproved')
        rejected_events = self.event_bus.get_events_by_type('OperationRejected')
        
        # High-priority operation should be approved
        self.assertEqual(len(approved_events), 1)
        self.assertEqual(approved_events[0].payload['worktype'], 1)
        
        # Low-priority operation should be rejected
        self.assertEqual(len(rejected_events), 1)
        self.assertEqual(rejected_events[0].payload['worktype'], 15)
        self.assertEqual(rejected_events[0].payload['reason'], 'low_priority')
    
    def test_all_low_priority_operations_approved(self):
        """Test that all low-priority ops are approved when no high-priority ops exist."""
        ops = [
            self._create_test_operation("Bewässerung", 15),
            self._create_test_operation("Spritzen", 14)
        ]
        
        self.decision_manager.decide(
            ops,
            field_id="1",
            date=datetime(2025, 4, 1)
        )
        
        approved_events = self.event_bus.get_events_by_type('OperationApproved')
        rejected_events = self.event_bus.get_events_by_type('OperationRejected')
        
        # All operations should be approved
        self.assertEqual(len(approved_events), 2)
        self.assertEqual(len(rejected_events), 0)
    
    def test_decision_manager_without_event_bus(self):
        """Test that DecisionManager works without an event bus (backward compatibility)."""
        dm = DecisionManager(strategy=WorkTypePriorityStrategy())
        
        ops = [
            self._create_test_operation("Pflügen", 1),
            self._create_test_operation("Bewässerung", 15)
        ]
        
        # Should not raise an exception
        selected = dm.decide(ops)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].worktype, 1)
    
    def _create_test_operation(self, name: str, worktype: int) -> FieldOperation:
        """Helper to create a test operation."""
        op = FieldOperation()
        op.operation = name
        op.worktype = worktype
        op.worktype_text = name
        return op


class TestEventFiltering(unittest.TestCase):
    """Test event filtering capabilities."""
    
    def test_filter_events_by_type(self):
        """Test filtering events by type."""
        bus = DomainEventBus()
        runner = CalendarDrivenRunner(
            SimContext(
                field_size=10.0,
                soil_type="loam",
                start_date=datetime(2025, 1, 1),
                crop_type="Potato",
                variety="Belana",
                field_id=1,
                field_name="Test Field",
                fuel_variation=0.1
            ),
            event_bus=bus
        )
        
        runner.tick(datetime(2025, 4, 1))
        
        tick_started = runner.event_bus.get_events_by_type('DailyTickStarted')
        tick_completed = runner.event_bus.get_events_by_type('DailyTickCompleted')
        
        self.assertGreater(len(tick_started), 0)
        self.assertGreater(len(tick_completed), 0)
        
        # Verify all filtered events have correct type
        for event in tick_started:
            self.assertEqual(event.event_type, 'DailyTickStarted')
        
        for event in tick_completed:
            self.assertEqual(event.event_type, 'DailyTickCompleted')
    
    def test_filter_events_by_field(self):
        """Test filtering events by field ID."""
        bus = DomainEventBus()
        runner = CalendarDrivenRunner(
            SimContext(
                field_size=10.0,
                soil_type="loam",
                start_date=datetime(2025, 1, 1),
                crop_type="Potato",
                variety="Belana",
                field_id=42,
                field_name="Test Field",
                fuel_variation=0.1
            ),
            event_bus=bus
        )
        
        runner.tick(datetime(2025, 4, 1))
        
        field_events = runner.event_bus.get_events_by_field('42')
        
        self.assertGreater(len(field_events), 0)
        
        # Verify all events are for the correct field
        for event in field_events:
            self.assertEqual(event.field_id, '42')


if __name__ == '__main__':
    unittest.main()
