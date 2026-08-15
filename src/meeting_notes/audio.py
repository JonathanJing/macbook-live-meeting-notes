from __future__ import annotations

import queue
import wave
from collections.abc import Iterator
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

TARGET_SAMPLE_RATE = 16_000


def read_wav(path: Path, target_rate: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        source_rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if width != 2:
        raise ValueError("WAV replay currently requires 16-bit PCM")
    audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if source_rate != target_rate:
        audio = resample_poly(audio, target_rate, source_rate).astype(np.float32)
    return np.ascontiguousarray(audio)


def iter_chunks(audio: np.ndarray, chunk_samples: int) -> Iterator[np.ndarray]:
    if chunk_samples <= 0:
        raise ValueError("chunk_samples must be positive")
    for offset in range(0, len(audio), chunk_samples):
        yield np.ascontiguousarray(audio[offset : offset + chunk_samples])


def input_devices() -> list[dict[str, object]]:
    import sounddevice as sd

    devices: list[dict[str, object]] = []
    for index, item in enumerate(sd.query_devices()):
        if int(item["max_input_channels"]) > 0:
            devices.append(
                {
                    "index": index,
                    "name": str(item["name"]),
                    "channels": int(item["max_input_channels"]),
                    "default_rate": float(item["default_samplerate"]),
                }
            )
    return devices


class MicrophoneSource:
    """Non-blocking Core Audio capture with explicit overflow accounting."""

    def __init__(
        self,
        *,
        device: int | str | None = None,
        sample_rate: int = TARGET_SAMPLE_RATE,
        chunk_ms: int = 320,
        queue_chunks: int = 32,
    ) -> None:
        self.device = device
        self.sample_rate = sample_rate
        self.chunk_samples = round(sample_rate * chunk_ms / 1000)
        self._queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=queue_chunks)
        self._stream = None
        self.dropped_chunks = 0
        self.status_messages: list[str] = []

    def __enter__(self) -> MicrophoneSource:
        import sounddevice as sd

        def callback(indata, _frames, _time_info, status) -> None:
            if status:
                self.status_messages.append(str(status))
            chunk = np.asarray(indata[:, 0], dtype=np.float32).copy()
            try:
                self._queue.put_nowait(chunk)
            except queue.Full:
                self.dropped_chunks += 1

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=self.chunk_samples,
            device=self.device,
            channels=1,
            dtype="float32",
            callback=callback,
        )
        self._stream.start()
        return self

    def __exit__(self, *_args: object) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()

    def chunks(self) -> Iterator[np.ndarray]:
        while True:
            yield self._queue.get()
