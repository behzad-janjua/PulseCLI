import sys

from pulse.dispatcher import Dispatcher
from pulse.handlers.logger import log_event
from pulse.handlers.voice_trigger import VoiceTrigger
from pulse.handlers.window_navigator import navigate
from pulse.myo_reader import MyoReader
from pulse.voice_recorder import VoiceRecorder


def main() -> None:
    discover    = "--discover" in sys.argv
    use_custom  = "--custom"   in sys.argv

    recorder     = VoiceRecorder(model_size="base")
    voice_trigger = VoiceTrigger(recorder)

    dispatcher = Dispatcher()
    dispatcher.register(log_event)
    dispatcher.register(voice_trigger)
    dispatcher.register(navigate)

    reader = MyoReader(dispatcher, discover=discover, use_custom=use_custom)
    reader.start()


if __name__ == "__main__":
    main()
