"""R.I.O. Runtime Background Event Listener and Dispatcher.

Provides a safe, non-invasive event bus for background tasks, lifecycle events,
and authorized system triggers.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, List, Optional
import uuid

logger = logging.getLogger("rio.runtime.events")


class RuntimeEvent:
    """An internal typed event within the device runtime."""

    def __init__(self, event_type: str, payload: Optional[Dict[str, Any]] = None, source: str = "runtime"):
        self.id = str(uuid.uuid4())
        self.type = event_type
        self.payload = payload or {}
        self.source = source
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "payload": self.payload,
            "source": self.source,
            "timestamp": self.timestamp,
        }


class EventListener:
    """Decoupled async event bus for runtime lifecycle and trigger handling."""

    def __init__(self):
        self._listeners: Dict[str, List[Callable[[RuntimeEvent], Any]]] = {}
        self._global_listeners: List[Callable[[RuntimeEvent], Any]] = []

    def subscribe(self, event_type: str, callback: Callable[[RuntimeEvent], Any]) -> None:
        """Subscribe to a specific event type."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def subscribe_all(self, callback: Callable[[RuntimeEvent], Any]) -> None:
        """Subscribe to all runtime events."""
        self._global_listeners.append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[RuntimeEvent], Any]) -> None:
        """Unsubscribe from a specific event type."""
        if event_type in self._listeners and callback in self._listeners[event_type]:
            self._listeners[event_type].remove(callback)

    async def emit(self, event: RuntimeEvent) -> None:
        """Dispatch an event to all subscribed listeners."""
        logger.debug(f"Runtime event emitted: {event.type}")
        callbacks = list(self._listeners.get(event.type, [])) + list(self._global_listeners)
        for cb in callbacks:
            try:
                res = cb(event)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error(f"Error executing listener for {event.type}: {e}")
