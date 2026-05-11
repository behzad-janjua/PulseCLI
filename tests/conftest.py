import sys
from unittest.mock import MagicMock

# Stub packages that are macOS-only or require hardware/large native deps.
# This lets the test suite run in headless/containerised environments where
# these packages cannot be installed or cannot connect to hardware.
for _mod in ["rumps", "sounddevice", "whisper", "pyomyo"]:
    sys.modules.setdefault(_mod, MagicMock())

# pynput installs on Linux but may fail to connect to a display/uinput at
# import time in a headless container — fall back to a stub if so.
try:
    from pynput.keyboard import Controller, Key  # noqa: F401
except Exception:
    _pynput = MagicMock()
    sys.modules.setdefault("pynput", _pynput)
    sys.modules.setdefault("pynput.keyboard", _pynput)
