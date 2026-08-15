from __future__ import annotations

import time
from typing import Protocol

import numpy as np

from .events import TranscriptSnapshot

DEFAULT_ASR_MODEL = "mlx-community/nemotron-3.5-asr-streaming-0.6b-8bit"


class StreamingASR(Protocol):
    sample_rate: int

    def feed(
        self, samples: np.ndarray, *, final: bool = False
    ) -> TranscriptSnapshot | None: ...


class NemotronStreamingASR:
    """True incremental adapter over mlx-audio's reusable Nemotron states."""

    sample_rate = 16_000

    def __init__(
        self,
        model_id: str = DEFAULT_ASR_MODEL,
        *,
        language: str = "en-US",
        att_context_size: tuple[int, int] = (56, 3),
    ) -> None:
        import mlx.core as mx
        from mlx_audio.stt import load
        from mlx_audio.stt.models.nemo.alignment import (
            AlignedToken,
            sentences_to_result,
            tokens_to_sentences,
        )
        from mlx_audio.stt.models.nemotron_asr import tokenizer
        from mlx_audio.stt.models.nemotron_asr.audio import StreamingLogMelSpectrogram
        from mlx_audio.stt.models.nemotron_asr.streaming import ConformerStreamingState

        self.mx = mx
        self.AlignedToken = AlignedToken
        self.sentences_to_result = sentences_to_result
        self.tokens_to_sentences = tokens_to_sentences
        self.tokenizer = tokenizer
        self.model_id = model_id
        self.language = language
        self.att_context_size = list(att_context_size)
        self.model = load(model_id)
        self.frontend = StreamingLogMelSpectrogram(self.model.preprocessor_config)
        self.encoder_state = ConformerStreamingState(
            self.model.encoder,
            chunk_frames=att_context_size[1] + 1,
            att_context_size=self.att_context_size,
        )
        self._last_token = self.model.blank_id
        self._decoder_hidden = None
        self._hypothesis: list[object] = []
        self._global_time = 0
        self._audio_samples = 0
        self._closed = False

    def feed(
        self, samples: np.ndarray, *, final: bool = False
    ) -> TranscriptSnapshot | None:
        if self._closed:
            raise RuntimeError("ASR stream is closed")
        started = time.perf_counter()
        pcm = np.asarray(samples, dtype=np.float32).reshape(-1)
        self._audio_samples += len(pcm)
        mel = self.frontend.push(self.mx.array(pcm), final=final)
        encoded_chunks = self.encoder_state.push(mel, final=final)
        emitted = False
        for encoded in encoded_chunks:
            prompted = self.model.apply_prompt(encoded, self.language)
            self._decode(prompted)
            emitted = True
        if final:
            self._closed = True
        if not emitted and not final:
            return None
        result = self.sentences_to_result(self.tokens_to_sentences(self._hypothesis))
        self.mx.clear_cache()
        return TranscriptSnapshot(
            text=result.text,
            audio_seconds=self._audio_samples / self.sample_rate,
            compute_seconds=time.perf_counter() - started,
            final=final,
        )

    def _decode(self, prompted) -> None:
        chunk_len = prompted.shape[1]
        frame_sec = (
            self.model.encoder_config.subsampling_factor
            * self.model.preprocessor_config.hop_length
            / self.model.preprocessor_config.sample_rate
        )
        frame = 0
        new_symbols = 0
        while frame < chunk_len:
            feature = prompted[:, frame : frame + 1]
            current_token = (
                self.mx.array([[self._last_token]], dtype=self.mx.int32)
                if self._last_token != self.model.blank_id
                else None
            )
            decoder_output, (hidden, cell) = self.model.decoder(
                current_token, self._decoder_hidden
            )
            decoder_output = decoder_output.astype(feature.dtype)
            proposed_hidden = (
                hidden.astype(feature.dtype),
                cell.astype(feature.dtype),
            )
            joint_output = self.model.joint(feature, decoder_output)
            predicted = int(self.mx.argmax(joint_output))
            if predicted == self.model.blank_id:
                frame += 1
                new_symbols = 0
                continue
            self._last_token = predicted
            self._decoder_hidden = proposed_hidden
            if not self.tokenizer.is_special_token(predicted, self.model.vocabulary):
                self._hypothesis.append(
                    self.AlignedToken(
                        predicted,
                        start=(self._global_time + frame) * frame_sec,
                        duration=frame_sec,
                        text=self.tokenizer.decode([predicted], self.model.vocabulary),
                    )
                )
            new_symbols += 1
            if (
                self.model.max_symbols is not None
                and new_symbols >= self.model.max_symbols
            ):
                frame += 1
                new_symbols = 0
        self._global_time += chunk_len
