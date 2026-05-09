from typing import Callable

from pulse.events import GestureEvent


class Dispatcher:
    def __init__(self) -> None:
        self._handlers: list[Callable[[GestureEvent], None]] = []

    def register(self, handler: Callable[[GestureEvent], None]) -> None:
        self._handlers.append(handler)

    def dispatch(self, event: GestureEvent) -> None:
        for handler in self._handlers:
            handler(event)
