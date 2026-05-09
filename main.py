import sys

from pulse.config import load_config
from pulse.dispatcher import Dispatcher
from pulse.handlers.logger import log_event
from pulse.handlers.voice_trigger import VoiceTrigger
from pulse.handlers.window_navigator import navigate
from pulse.myo_reader import MyoReader
from pulse.voice_recorder import VoiceRecorder


def main() -> None:
    discover   = "--discover" in sys.argv
    use_custom = "--custom"   in sys.argv

    recorder      = VoiceRecorder(model_size="base")
    voice_trigger = VoiceTrigger(recorder)

    dispatcher = Dispatcher()
    dispatcher.register(log_event)

    config = load_config()
    if config is not None:
        from pulse.handlers.recipe_handler import RecipeHandler
        dispatcher.register(RecipeHandler(config, voice_trigger))
        print("[PULSE] recipe mode — pulse.yaml loaded", flush=True)
    else:
        dispatcher.register(voice_trigger)
        dispatcher.register(navigate)

    reader = MyoReader(dispatcher, discover=discover, use_custom=use_custom)
    reader.start()


if __name__ == "__main__":
    main()
