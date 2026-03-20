import unittest
from datetime import datetime
from models.domain_events import (
    DomainEvent,
    create_daily_tick_started,
    create_daily_tick_completed,
    create_crop_cycle_started,
    create_harvest_completed,
    create_operation_considered,
    create_operation_approved,
    create_operation_rejected,
    create_operation_applied
)


class TestDomainEvent(unittest.TestCase):
    """Test the base DomainEvent class."""
    
    def test_to_dict_serialization(self):
        """Test that DomainEvent can be serialized to dict."""
        event = DomainEvent(
            event_id="test-123",
            event_type="TestEvent",
            timestamp=datetime(2026, 3, 20, 12, 0, 0),
            field_id="field-1",
            payload={"key": "value"}
        )
        
        result = event.to_dict()
        
        self.assertEqual(result['event_id'], "test-123")
        self.assertEqual(result['event_type'], "TestEvent")
        self.assertEqual(result['timestamp'], "2026-03-20T12:00:00")
        self.assertEqual(result['field_id'], "field-1")
        self.assertEqual(result['payload'], {"key": "value"})
    
    def test_from_dict_deserialization(self):
        """Test that DomainEvent can be deserialized from dict."""
        data = {
            'event_id': "test-456",
            'event_type': "TestEvent",
            'timestamp': "2026-03-20T12:00:00",
            'field_id': "field-2",
            'payload': {"foo": "bar"}
        }
        
        event = DomainEvent.from_dict(data)
        
        self.assertEqual(event.event_id, "test-456")
        self.assertEqual(event.event_type, "TestEvent")
        self.assertEqual(event.timestamp, datetime(2026, 3, 20, 12, 0, 0))
        self.assertEqual(event.field_id, "field-2")
        self.assertEqual(event.payload, {"foo": "bar"})
    
    def test_serialization_roundtrip(self):
        """Test that serialization and deserialization are inverse operations."""
        original = DomainEvent(
            event_id="roundtrip-test",
            event_type="RoundtripEvent",
            timestamp=datetime(2026, 3, 20, 15, 30, 45),
            field_id="field-3",
            payload={"nested": {"data": 123}}
        )
        
        serialized = original.to_dict()
        deserialized = DomainEvent.from_dict(serialized)
        
        self.assertEqual(deserialized.event_id, original.event_id)
        self.assertEqual(deserialized.event_type, original.event_type)
        self.assertEqual(deserialized.timestamp, original.timestamp)
        self.assertEqual(deserialized.field_id, original.field_id)
        self.assertEqual(deserialized.payload, original.payload)


class TestDailyTickEvents(unittest.TestCase):
    """Test DailyTick event factory functions."""
    
    def test_create_daily_tick_started(self):
        """Test creation of DailyTickStarted event."""
        test_date = datetime(2026, 3, 20, 0, 0, 0)
        event = create_daily_tick_started(
            field_id="field-1",
            date=test_date
        )
        
        self.assertEqual(event.event_type, "DailyTickStarted")
        self.assertEqual(event.field_id, "field-1")
        self.assertIn('date', event.payload)
        self.assertIsNotNone(event.event_id)
        self.assertIsInstance(event.timestamp, datetime)
    
    def test_create_daily_tick_completed(self):
        """Test creation of DailyTickCompleted event."""
        test_date = datetime(2026, 3, 20, 0, 0, 0)
        event = create_daily_tick_completed(
            field_id="field-2",
            date=test_date,
            events_dispatched=5
        )
        
        self.assertEqual(event.event_type, "DailyTickCompleted")
        self.assertEqual(event.field_id, "field-2")
        self.assertEqual(event.payload['events_dispatched'], 5)
        self.assertIn('date', event.payload)
    
    def test_daily_tick_events_serialization(self):
        """Test that DailyTick events can be serialized."""
        event = create_daily_tick_started(
            field_id="field-3",
            date=datetime(2026, 3, 20)
        )
        
        serialized = event.to_dict()
        deserialized = DomainEvent.from_dict(serialized)
        
        self.assertEqual(deserialized.event_type, "DailyTickStarted")
        self.assertEqual(deserialized.field_id, "field-3")


class TestCropCycleEvents(unittest.TestCase):
    """Test CropCycle event factory functions."""
    
    def test_create_crop_cycle_started(self):
        """Test creation of CropCycleStarted event."""
        test_date = datetime(2026, 4, 15)
        event = create_crop_cycle_started(
            field_id="field-1",
            date=test_date,
            crop_type="Kartoffel"
        )
        
        self.assertEqual(event.event_type, "CropCycleStarted")
        self.assertEqual(event.field_id, "field-1")
        self.assertEqual(event.payload['crop_type'], "Kartoffel")
        self.assertIn('date', event.payload)
    
    def test_create_harvest_completed(self):
        """Test creation of HarvestCompleted event."""
        test_date = datetime(2026, 9, 20)
        event = create_harvest_completed(
            field_id="field-2",
            date=test_date,
            yield_estimate=45.5
        )
        
        self.assertEqual(event.event_type, "HarvestCompleted")
        self.assertEqual(event.field_id, "field-2")
        self.assertEqual(event.payload['yield_estimate'], 45.5)
    
    def test_harvest_completed_without_yield(self):
        """Test HarvestCompleted event without yield estimate."""
        event = create_harvest_completed(
            field_id="field-3",
            date=datetime(2026, 9, 20)
        )
        
        self.assertIsNone(event.payload['yield_estimate'])


class TestOperationEvents(unittest.TestCase):
    """Test Operation event factory functions."""
    
    def test_create_operation_considered(self):
        """Test creation of OperationConsidered event."""
        test_date = datetime(2026, 5, 10)
        event = create_operation_considered(
            field_id="field-1",
            date=test_date,
            operation_type="Pflügen",
            worktype=1
        )
        
        self.assertEqual(event.event_type, "OperationConsidered")
        self.assertEqual(event.field_id, "field-1")
        self.assertEqual(event.payload['operation_type'], "Pflügen")
        self.assertEqual(event.payload['worktype'], 1)
    
    def test_create_operation_approved(self):
        """Test creation of OperationApproved event."""
        test_date = datetime(2026, 5, 10)
        event = create_operation_approved(
            field_id="field-2",
            date=test_date,
            operation_type="Düngen",
            worktype=3
        )
        
        self.assertEqual(event.event_type, "OperationApproved")
        self.assertEqual(event.payload['operation_type'], "Düngen")
        self.assertEqual(event.payload['worktype'], 3)
    
    def test_create_operation_rejected(self):
        """Test creation of OperationRejected event."""
        test_date = datetime(2026, 5, 10)
        event = create_operation_rejected(
            field_id="field-3",
            date=test_date,
            operation_type="Bewässerung",
            worktype=15,
            reason="low_priority"
        )
        
        self.assertEqual(event.event_type, "OperationRejected")
        self.assertEqual(event.payload['operation_type'], "Bewässerung")
        self.assertEqual(event.payload['worktype'], 15)
        self.assertEqual(event.payload['reason'], "low_priority")
    
    def test_create_operation_applied(self):
        """Test creation of OperationApplied event."""
        test_date = datetime(2026, 5, 10)
        event = create_operation_applied(
            field_id="field-4",
            date=test_date,
            operation_type="Ernten",
            worktype=9,
            integration_event_id="int-event-123"
        )
        
        self.assertEqual(event.event_type, "OperationApplied")
        self.assertEqual(event.payload['operation_type'], "Ernten")
        self.assertEqual(event.payload['worktype'], 9)
        self.assertEqual(event.payload['integration_event_id'], "int-event-123")
    
    def test_operation_applied_without_integration_event(self):
        """Test OperationApplied event without integration event ID."""
        event = create_operation_applied(
            field_id="field-5",
            date=datetime(2026, 5, 10),
            operation_type="Test",
            worktype=1
        )
        
        self.assertIsNone(event.payload['integration_event_id'])


class TestEventUniqueness(unittest.TestCase):
    """Test that events have unique IDs."""
    
    def test_events_have_unique_ids(self):
        """Test that multiple events get different UUIDs."""
        event1 = create_daily_tick_started("field-1", datetime.now())
        event2 = create_daily_tick_started("field-1", datetime.now())
        
        self.assertNotEqual(event1.event_id, event2.event_id)
    
    def test_all_event_types_have_unique_ids(self):
        """Test that all event types generate unique IDs."""
        test_date = datetime(2026, 5, 10)
        
        events = [
            create_daily_tick_started("field-1", test_date),
            create_daily_tick_completed("field-1", test_date, 0),
            create_crop_cycle_started("field-1", test_date, "Kartoffel"),
            create_harvest_completed("field-1", test_date),
            create_operation_considered("field-1", test_date, "Test", 1),
            create_operation_approved("field-1", test_date, "Test", 1),
            create_operation_rejected("field-1", test_date, "Test", 1, "reason"),
            create_operation_applied("field-1", test_date, "Test", 1)
        ]
        
        event_ids = [e.event_id for e in events]
        self.assertEqual(len(event_ids), len(set(event_ids)), "All event IDs should be unique")


if __name__ == '__main__':
    unittest.main()
