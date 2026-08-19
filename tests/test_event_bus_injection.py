import unittest
from datetime import datetime

from events.domain_event_bus import DomainEventBus
from models.planting_plan import FieldOperation
from scheduler.decision_manager import DecisionManager, WorkTypePriorityStrategy


class TestEventBusInjection(unittest.TestCase):
    """Test that event bus is correctly injected into components."""

    def test_decision_manager_uses_injected_bus(self):
        """Test that DecisionManager uses the injected event bus."""
        bus = DomainEventBus()
        dm = DecisionManager(strategy=WorkTypePriorityStrategy(), event_bus=bus)

        # Verify same instance
        self.assertIs(dm.event_bus, bus)

        # Create test operations
        ops = [self._create_test_operation("Test", 1)]

        # Make decision
        dm.decide(ops, field_id="1", date=datetime.now())

        # Verify events were published to the injected bus
        history = bus.get_history()
        self.assertGreater(len(history), 0, "Events should be in the injected bus")

    def _create_test_operation(self, name: str, worktype: int) -> FieldOperation:
        """Helper to create a test operation."""
        op = FieldOperation()
        op.operation = name
        op.worktype = worktype
        op.worktype_text = name
        return op


if __name__ == "__main__":
    unittest.main()
