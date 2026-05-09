import logging

from pulse.events import GestureEvent

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def log_event(event: GestureEvent) -> None:
    logger.info("[EVENT] %s  ts=%.2f", event.gesture.value, event.timestamp)
