import logging

import numpy as np
import sounddevice as sd
import whisper

logger = logging.getLogger(__name__)

MIN_TRANSCRIPT_CHARS = 3


class VoiceRecorder:
    def __init__(self, model_size: str = "base", sample_rate: int = 16000) -> None:
        self._sample_rate = sample_rate
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        logger.info("[PULSE] loading Whisper model '%s'...", model_size)
        self._model = whisper.load_model(model_size)
        logger.info("[PULSE] voice model ready")

    def start(self) -> None:
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata: np.ndarray, frames: int, time, status) -> None:
        self._frames.append(indata.copy())

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def stop_and_transcribe(self) -> str | None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._frames:
            return None

        audio = np.concatenate(self._frames, axis=0).flatten()
        self._frames = []

        try:
            result = self._model.transcribe(audio, fp16=False)
            text = result["text"].strip()
            return text if len(text) >= MIN_TRANSCRIPT_CHARS else None
        except Exception as e:
            logger.error("[PULSE] transcription error: %s", e)
            return None
