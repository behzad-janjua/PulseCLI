import sys
import warnings

# PyTorch registers a named POSIX semaphore for its thread pool that it never
# unlinks on exit. The resource_tracker cleans it up correctly — the warning
# is noise from a known upstream PyTorch issue.
warnings.filterwarnings(
    "ignore",
    message="resource_tracker: There appear to be",
    category=UserWarning,
)

from pulse.engine import PulseEngine


def main() -> None:
    discover   = "--discover" in sys.argv
    use_custom = "--custom"   in sys.argv

    engine = PulseEngine(discover=discover, use_custom=use_custom)

    if discover:
        engine.run_blocking()
        return

    from pulse.menu_bar import PulseApp
    app = PulseApp(engine)
    engine.start()
    app.run()


if __name__ == "__main__":
    main()
