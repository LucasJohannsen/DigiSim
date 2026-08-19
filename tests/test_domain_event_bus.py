import unittest
from datetime import datetime

from events.domain_event_bus import DomainEventBus
from models.domain_events import (
    DomainEvent,
    create_daily_tick_completed,
    create_daily_tick_started,
    create_operation_approved,
    create_operation_rejected,
)


class TestDomainEventBusBasics(unittest.TestCase):
    """Test basic DomainEventBus functionality."""

    def setUp(self):
        """Create a fresh event bus for each test."""
        self.bus = DomainEventBus()

    def test_bus_initialization(self):
        """Test that a new bus is empty."""
        self.assertEqual(len(self.bus), 0)
        self.assertEqual(len(self.bus.get_history()), 0)

    def test_publish_stores_event(self):
        """Test that publishing an event stores it in history."""
        event = create_daily_tick_started("field-1", datetime.now())
        self.bus.publish(event)

        history = self.bus.get_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].event_id, event.event_id)

    def test_publish_multiple_events(self):
        """Test that multiple events are stored in order."""
        event1 = create_daily_tick_started("field-1", datetime.now())
        event2 = create_daily_tick_completed("field-1", datetime.now(), 5)
        event3 = create_operation_approved("field-1", datetime.now(), "Test", 1)

        self.bus.publish(event1)
        self.bus.publish(event2)
        self.bus.publish(event3)

        history = self.bus.get_history()
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0].event_type, "DailyTickStarted")
        self.assertEqual(history[1].event_type, "DailyTickCompleted")
        self.assertEqual(history[2].event_type, "OperationApproved")

    def test_get_history_returns_copy(self):
        """Test that get_history returns a copy, not the original list."""
        event = create_daily_tick_started("field-1", datetime.now())
        self.bus.publish(event)

        history1 = self.bus.get_history()
        history2 = self.bus.get_history()

        self.assertIsNot(history1, history2)
        self.assertEqual(len(history1), len(history2))

    def test_clear_removes_history(self):
        """Test that clear() removes all events from history."""
        event1 = create_daily_tick_started("field-1", datetime.now())
        event2 = create_daily_tick_completed("field-1", datetime.now(), 0)

        self.bus.publish(event1)
        self.bus.publish(event2)
        self.assertEqual(len(self.bus), 2)

        self.bus.clear()
        self.assertEqual(len(self.bus), 0)
        self.assertEqual(len(self.bus.get_history()), 0)


class TestDomainEventBusSubscription(unittest.TestCase):
    """Test event subscription and handler invocation."""

    def setUp(self):
        """Create a fresh event bus for each test."""
        self.bus = DomainEventBus()
        self.received_events = []

    def test_subscribe_and_publish(self):
        """Test that subscribed handlers are called on publish."""

        def handler(event: DomainEvent):
            self.received_events.append(event)

        self.bus.subscribe("DailyTickStarted", handler)
        event = create_daily_tick_started("field-1", datetime.now())
        self.bus.publish(event)

        self.assertEqual(len(self.received_events), 1)
        self.assertEqual(self.received_events[0].event_id, event.event_id)

    def test_handler_not_called_for_different_event_type(self):
        """Test that handlers are only called for subscribed event types."""

        def handler(event: DomainEvent):
            self.received_events.append(event)

        self.bus.subscribe("DailyTickStarted", handler)

        # Publish different event type
        event = create_daily_tick_completed("field-1", datetime.now(), 0)
        self.bus.publish(event)

        self.assertEqual(len(self.received_events), 0)

    def test_multiple_handlers_same_event_type(self):
        """Test that multiple handlers can subscribe to the same event type."""
        handler1_calls = []
        handler2_calls = []

        def handler1(event: DomainEvent):
            handler1_calls.append(event)

        def handler2(event: DomainEvent):
            handler2_calls.append(event)

        self.bus.subscribe("DailyTickStarted", handler1)
        self.bus.subscribe("DailyTickStarted", handler2)

        event = create_daily_tick_started("field-1", datetime.now())
        self.bus.publish(event)

        self.assertEqual(len(handler1_calls), 1)
        self.assertEqual(len(handler2_calls), 1)

    def test_handlers_called_in_registration_order(self):
        """Test that handlers are called in the order they were registered."""
        call_order = []

        def handler1(event: DomainEvent):
            call_order.append(1)

        def handler2(event: DomainEvent):
            call_order.append(2)

        def handler3(event: DomainEvent):
            call_order.append(3)

        self.bus.subscribe("DailyTickStarted", handler1)
        self.bus.subscribe("DailyTickStarted", handler2)
        self.bus.subscribe("DailyTickStarted", handler3)

        event = create_daily_tick_started("field-1", datetime.now())
        self.bus.publish(event)

        self.assertEqual(call_order, [1, 2, 3])

    def test_subscribe_different_event_types(self):
        """Test subscribing to different event types."""
        started_events = []
        completed_events = []

        def on_started(event: DomainEvent):
            started_events.append(event)

        def on_completed(event: DomainEvent):
            completed_events.append(event)

        self.bus.subscribe("DailyTickStarted", on_started)
        self.bus.subscribe("DailyTickCompleted", on_completed)

        event1 = create_daily_tick_started("field-1", datetime.now())
        event2 = create_daily_tick_completed("field-1", datetime.now(), 0)

        self.bus.publish(event1)
        self.bus.publish(event2)

        self.assertEqual(len(started_events), 1)
        self.assertEqual(len(completed_events), 1)


class TestDomainEventBusUnsubscribe(unittest.TestCase):
    """Test handler unsubscription."""

    def setUp(self):
        """Create a fresh event bus for each test."""
        self.bus = DomainEventBus()

    def test_unsubscribe_removes_handler(self):
        """Test that unsubscribe removes a handler."""
        calls = []

        def handler(event: DomainEvent):
            calls.append(event)

        self.bus.subscribe("DailyTickStarted", handler)
        result = self.bus.unsubscribe("DailyTickStarted", handler)

        self.assertTrue(result)

        event = create_daily_tick_started("field-1", datetime.now())
        self.bus.publish(event)

        self.assertEqual(len(calls), 0)

    def test_unsubscribe_nonexistent_handler(self):
        """Test that unsubscribing a non-existent handler returns False."""

        def handler(event: DomainEvent):
            pass

        result = self.bus.unsubscribe("DailyTickStarted", handler)
        self.assertFalse(result)

    def test_unsubscribe_nonexistent_event_type(self):
        """Test that unsubscribing from non-existent event type returns False."""

        def handler(event: DomainEvent):
            pass

        result = self.bus.unsubscribe("NonExistentEvent", handler)
        self.assertFalse(result)

    def test_clear_handlers_specific_type(self):
        """Test clearing handlers for a specific event type."""
        calls1 = []
        calls2 = []

        def handler1(event: DomainEvent):
            calls1.append(event)

        def handler2(event: DomainEvent):
            calls2.append(event)

        self.bus.subscribe("DailyTickStarted", handler1)
        self.bus.subscribe("DailyTickCompleted", handler2)

        self.bus.clear_handlers("DailyTickStarted")

        event1 = create_daily_tick_started("field-1", datetime.now())
        event2 = create_daily_tick_completed("field-1", datetime.now(), 0)

        self.bus.publish(event1)
        self.bus.publish(event2)

        self.assertEqual(len(calls1), 0)
        self.assertEqual(len(calls2), 1)

    def test_clear_all_handlers(self):
        """Test clearing all handlers."""
        calls1 = []
        calls2 = []

        def handler1(event: DomainEvent):
            calls1.append(event)

        def handler2(event: DomainEvent):
            calls2.append(event)

        self.bus.subscribe("DailyTickStarted", handler1)
        self.bus.subscribe("DailyTickCompleted", handler2)

        self.bus.clear_handlers()

        event1 = create_daily_tick_started("field-1", datetime.now())
        event2 = create_daily_tick_completed("field-1", datetime.now(), 0)

        self.bus.publish(event1)
        self.bus.publish(event2)

        self.assertEqual(len(calls1), 0)
        self.assertEqual(len(calls2), 0)


class TestDomainEventBusFiltering(unittest.TestCase):
    """Test event filtering methods."""

    def setUp(self):
        """Create a fresh event bus with test data."""
        self.bus = DomainEventBus()

        # Publish various events
        self.bus.publish(create_daily_tick_started("field-1", datetime.now()))
        self.bus.publish(create_daily_tick_completed("field-1", datetime.now(), 2))
        self.bus.publish(create_daily_tick_started("field-2", datetime.now()))
        self.bus.publish(create_operation_approved("field-1", datetime.now(), "Test", 1))
        self.bus.publish(
            create_operation_rejected("field-2", datetime.now(), "Test", 15, "low_priority")
        )

    def test_get_events_by_type(self):
        """Test filtering events by type."""
        tick_started = self.bus.get_events_by_type("DailyTickStarted")
        self.assertEqual(len(tick_started), 2)

        tick_completed = self.bus.get_events_by_type("DailyTickCompleted")
        self.assertEqual(len(tick_completed), 1)

        approved = self.bus.get_events_by_type("OperationApproved")
        self.assertEqual(len(approved), 1)

    def test_get_events_by_field(self):
        """Test filtering events by field ID."""
        field1_events = self.bus.get_events_by_field("field-1")
        self.assertEqual(len(field1_events), 3)

        field2_events = self.bus.get_events_by_field("field-2")
        self.assertEqual(len(field2_events), 2)

    def test_get_events_by_nonexistent_type(self):
        """Test filtering for non-existent event type returns empty list."""
        events = self.bus.get_events_by_type("NonExistentEvent")
        self.assertEqual(len(events), 0)

    def test_get_events_by_nonexistent_field(self):
        """Test filtering for non-existent field returns empty list."""
        events = self.bus.get_events_by_field("field-999")
        self.assertEqual(len(events), 0)


class TestDomainEventBusIsolation(unittest.TestCase):
    """Test that event buses are isolated from each other."""

    def test_multiple_buses_are_independent(self):
        """Test that multiple event bus instances don't share state."""
        bus1 = DomainEventBus()
        bus2 = DomainEventBus()

        event1 = create_daily_tick_started("field-1", datetime.now())
        event2 = create_daily_tick_started("field-2", datetime.now())

        bus1.publish(event1)
        bus2.publish(event2)

        self.assertEqual(len(bus1.get_history()), 1)
        self.assertEqual(len(bus2.get_history()), 1)
        self.assertEqual(bus1.get_history()[0].field_id, "field-1")
        self.assertEqual(bus2.get_history()[0].field_id, "field-2")

    def test_handlers_are_independent(self):
        """Test that handlers on different buses are independent."""
        bus1 = DomainEventBus()
        bus2 = DomainEventBus()

        calls1 = []
        calls2 = []

        def handler1(event: DomainEvent):
            calls1.append(event)

        def handler2(event: DomainEvent):
            calls2.append(event)

        bus1.subscribe("DailyTickStarted", handler1)
        bus2.subscribe("DailyTickStarted", handler2)

        event = create_daily_tick_started("field-1", datetime.now())
        bus1.publish(event)

        self.assertEqual(len(calls1), 1)
        self.assertEqual(len(calls2), 0)


class TestDomainEventBusRepr(unittest.TestCase):
    """Test string representation."""

    def test_repr_empty_bus(self):
        """Test repr of empty bus."""
        bus = DomainEventBus()
        repr_str = repr(bus)

        self.assertIn("DomainEventBus", repr_str)
        self.assertIn("events=0", repr_str)
        self.assertIn("handlers=0", repr_str)

    def test_repr_with_events_and_handlers(self):
        """Test repr with events and handlers."""
        bus = DomainEventBus()

        def handler1(event: DomainEvent):
            pass

        def handler2(event: DomainEvent):
            pass

        bus.subscribe("DailyTickStarted", handler1)
        bus.subscribe("DailyTickStarted", handler2)
        bus.subscribe("DailyTickCompleted", handler1)

        bus.publish(create_daily_tick_started("field-1", datetime.now()))
        bus.publish(create_daily_tick_completed("field-1", datetime.now(), 0))

        repr_str = repr(bus)

        self.assertIn("events=2", repr_str)
        self.assertIn("handlers=3", repr_str)


class TestDomainEventBusClearBehavior(unittest.TestCase):
    """Test that clear() only affects history, not handlers."""

    def test_clear_preserves_handlers(self):
        """Test that clear() does not remove handlers."""
        bus = DomainEventBus()
        calls = []

        def handler(event: DomainEvent):
            calls.append(event)

        bus.subscribe("DailyTickStarted", handler)

        event1 = create_daily_tick_started("field-1", datetime.now())
        bus.publish(event1)

        bus.clear()

        event2 = create_daily_tick_started("field-2", datetime.now())
        bus.publish(event2)

        self.assertEqual(len(calls), 2)
        self.assertEqual(len(bus.get_history()), 1)


if __name__ == "__main__":
    unittest.main()
