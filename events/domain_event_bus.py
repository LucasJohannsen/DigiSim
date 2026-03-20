from typing import Callable, Any
from models.domain_events import DomainEvent


class DomainEventBus:
    """
    Synchronous in-memory event bus for Domain Events.
    
    Provides infrastructure to publish, subscribe to, and store Domain Events
    within the simulation process. This is a lightweight mechanism designed for
    single-process simulation with no external message broker.
    
    The bus is designed to be injectable (not a global singleton) to maintain
    testability and allow multiple independent simulation contexts.
    
    Usage:
        bus = DomainEventBus()
        
        # Subscribe to events
        def handler(event: DomainEvent):
            print(f"Received: {event.event_type}")
        
        bus.subscribe('DailyTickStarted', handler)
        
        # Publish events
        event = create_daily_tick_started(field_id="1", date=datetime.now())
        bus.publish(event)
        
        # Access history
        history = bus.get_history()
        
        # Clear between ticks
        bus.clear()
    
    Attributes:
        _handlers: Dictionary mapping event types to lists of handler functions
        _history: Ordered list of all published events
    """
    
    def __init__(self) -> None:
        """Initialize an empty event bus."""
        self._handlers: dict[str, list[Callable[[DomainEvent], None]]] = {}
        self._history: list[DomainEvent] = []
    
    def publish(self, event: DomainEvent) -> None:
        """
        Publish a domain event to the bus.
        
        The event is:
        1. Stored in the internal history (ordered by publication time)
        2. Dispatched to all registered handlers for this event type
        
        Handlers are called synchronously in registration order.
        
        Args:
            event: The DomainEvent to publish
            
        Example:
            event = create_daily_tick_started(field_id="1", date=datetime.now())
            bus.publish(event)
        """
        self._history.append(event)
        
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            handler(event)
    
    def subscribe(self, event_type: str, handler: Callable[[DomainEvent], None]) -> None:
        """
        Register a handler function for a specific event type.
        
        Multiple handlers can be registered for the same event type.
        Handlers are called in the order they were registered.
        
        Args:
            event_type: The type of event to subscribe to (e.g., 'DailyTickStarted')
            handler: Callable that accepts a DomainEvent
            
        Example:
            def on_tick_started(event: DomainEvent):
                print(f"Tick started: {event.payload['date']}")
            
            bus.subscribe('DailyTickStarted', on_tick_started)
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        
        self._handlers[event_type].append(handler)
    
    def get_history(self) -> list[DomainEvent]:
        """
        Retrieve all published events in chronological order.
        
        Returns a copy of the internal history to prevent external modification.
        
        Returns:
            List of DomainEvents ordered by publication time
            
        Example:
            history = bus.get_history()
            for event in history:
                print(f"{event.timestamp}: {event.event_type}")
        """
        return self._history.copy()
    
    def clear(self) -> None:
        """
        Reset the event history.
        
        This clears all stored events but does NOT remove registered handlers.
        Useful for:
        - Resetting state between simulation ticks
        - Test isolation
        - Memory management in long-running simulations
        
        Note: Handlers remain registered after clear().
        
        Example:
            bus.clear()  # History is empty, handlers still registered
        """
        self._history.clear()
    
    def unsubscribe(self, event_type: str, handler: Callable[[DomainEvent], None]) -> bool:
        """
        Remove a specific handler for an event type.
        
        Args:
            event_type: The event type to unsubscribe from
            handler: The handler function to remove
            
        Returns:
            True if handler was found and removed, False otherwise
            
        Example:
            bus.unsubscribe('DailyTickStarted', on_tick_started)
        """
        if event_type not in self._handlers:
            return False
        
        try:
            self._handlers[event_type].remove(handler)
            return True
        except ValueError:
            return False
    
    def clear_handlers(self, event_type: str | None = None) -> None:
        """
        Clear all handlers for a specific event type, or all handlers.
        
        Args:
            event_type: Event type to clear handlers for. If None, clears all handlers.
            
        Example:
            bus.clear_handlers('DailyTickStarted')  # Clear specific type
            bus.clear_handlers()  # Clear all handlers
        """
        if event_type is None:
            self._handlers.clear()
        elif event_type in self._handlers:
            self._handlers[event_type].clear()
    
    def get_events_by_type(self, event_type: str) -> list[DomainEvent]:
        """
        Filter history by event type.
        
        Args:
            event_type: The event type to filter for
            
        Returns:
            List of events matching the specified type
            
        Example:
            tick_events = bus.get_events_by_type('DailyTickStarted')
        """
        return [event for event in self._history if event.event_type == event_type]
    
    def get_events_by_field(self, field_id: str) -> list[DomainEvent]:
        """
        Filter history by field ID.
        
        Args:
            field_id: The field ID to filter for
            
        Returns:
            List of events for the specified field
            
        Example:
            field_events = bus.get_events_by_field('field-1')
        """
        return [event for event in self._history if event.field_id == field_id]
    
    def __len__(self) -> int:
        """Return the number of events in history."""
        return len(self._history)
    
    def __repr__(self) -> str:
        """String representation of the event bus."""
        handler_count = sum(len(handlers) for handlers in self._handlers.values())
        return f"DomainEventBus(events={len(self._history)}, handlers={handler_count})"
