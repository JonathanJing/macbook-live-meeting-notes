from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class EndpointConfig:
    sample_rate: int = 16_000
    threshold_dbfs: float = -38.0
    silence_ms: int = 900
    minimum_speech_ms: int = 250


class SilenceEndpoint:
    def __init__(self, config: EndpointConfig | None = None) -> None:
        self.config = config or EndpointConfig()
        self._speech_samples = 0
        self._silence_samples = 0
        self._in_speech = False

    def feed(self, samples: np.ndarray) -> bool:
        mono = np.asarray(samples, dtype=np.float32).reshape(-1)
        if mono.size == 0:
            return False
        rms = float(np.sqrt(np.mean(np.square(mono), dtype=np.float64)))
        dbfs = 20.0 * np.log10(max(rms, 1e-8))
        is_speech = dbfs >= self.config.threshold_dbfs
        if is_speech:
            self._speech_samples += mono.size
            self._silence_samples = 0
            if self._speech_samples >= self._samples(self.config.minimum_speech_ms):
                self._in_speech = True
            return False
        if not self._in_speech:
            self._speech_samples = 0
            return False
        self._silence_samples += mono.size
        if self._silence_samples < self._samples(self.config.silence_ms):
            return False
        self.reset()
        return True

    def reset(self) -> None:
        self._speech_samples = 0
        self._silence_samples = 0
        self._in_speech = False

    def _samples(self, milliseconds: int) -> int:
        return round(self.config.sample_rate * milliseconds / 1000)
