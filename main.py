import sys

from pulse.dispatcher import Dispatcher
from pulse.handlers.keyboard_trigger import keyboard_trigger
from pulse.handlers.logger import log_event
from pulse.myo_reader import MyoReader


def main() -> None:
    discover = "--discover" in sys.argv

    dispatcher = Dispatcher()
    dispatcher.register(log_event)
    dispatcher.register(keyboard_trigger)

    reader = MyoReader(dispatcher, discover=discover)
    reader.start()


if __name__ == "__main__":
    main()
