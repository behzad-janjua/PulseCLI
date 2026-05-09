from dataclasses import dataclass, field
from time import time

from pulse.gestures import Gesture


@dataclass
class GestureEvent:
    gesture: Gesture
    timestamp: float = field(default_factory=time)
    metadata: dict = field(default_factory=dict)
