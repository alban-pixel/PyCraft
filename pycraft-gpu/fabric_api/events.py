"""Fabric Event system with callback registration and dispatching."""
from typing import Any, Callable, List, Optional


class Event:
    """Represents a lifecycle or interaction event with a list of callbacks."""

    def __init__(self, name: str = "") -> None:
        self.name = name
        self._callbacks: List[Callable[..., Any]] = []

    def register(self, callback: Callable[..., Any]) -> None:
        """Register a callback to this event."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def invoker(self, *args: Any, **kwargs: Any) -> Any:
        """Invoke all registered callbacks in order. Returns the last non-None result."""
        result: Any = None
        for cb in self._callbacks:
            res = cb(*args, **kwargs)
            if res is not None:
                result = res
        return result

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.invoker(*args, **kwargs)

    def clear(self) -> None:
        """Clear all registered callbacks."""
        self._callbacks.clear()


class EventBus:
    """Standard Fabric-compatible event bus."""

    ServerTickEvents: Event = Event("ServerTickEvents")
    ClientTickEvents: Event = Event("ClientTickEvents")
    AttackBlockCallback: Event = Event("AttackBlockCallback")
    UseBlockCallback: Event = Event("UseBlockCallback")
    UseItemCallback: Event = Event("UseItemCallback")
    PlayerBlockBreakEvents: Event = Event("PlayerBlockBreakEvents")
    EntityDamageEvents: Event = Event("EntityDamageEvents")
    HudRenderCallback: Event = Event("HudRenderCallback")
