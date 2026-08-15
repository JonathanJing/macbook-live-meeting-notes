from __future__ import annotations

import time
from collections.abc import Iterable
from queue import Empty, Full, Queue
from threading import Thread

import numpy as np

from .asr import StreamingASR
from .endpoint import SilenceEndpoint
from .events import SessionEvent, TranscriptSnapshot
from .notes import NoteGenerator
from .session import SessionWriter
from .transcript import TranscriptStabilizer


class MeetingRunner:
    def __init__(
        self,
        asr: StreamingASR,
        writer: SessionWriter,
        note_generator: NoteGenerator,
        *,
        endpoint: SilenceEndpoint | None = None,
        on_snapshot=None,
        note_interval_seconds: float = 60.0,
    ) -> None:
        self.asr = asr
        self.writer = writer
        self.note_generator = note_generator
        self.endpoint = endpoint or SilenceEndpoint()
        self.stabilizer = TranscriptStabilizer()
        self.on_snapshot = on_snapshot
        self.note_interval_seconds = note_interval_seconds
        self.audio_seconds = 0.0
        self.compute_seconds = 0.0
        self._last_note_audio = 0.0
        self._note_worker = _NoteWorker(note_generator, writer)
        self._note_worker.start()

    def run(self, chunks: Iterable[np.ndarray], *, realtime: bool = False) -> None:
        for chunk in chunks:
            started = time.perf_counter()
            snapshot = self.asr.feed(chunk)
            self.audio_seconds += len(chunk) / self.asr.sample_rate
            if realtime:
                delay = len(chunk) / self.asr.sample_rate - (
                    time.perf_counter() - started
                )
                if delay > 0:
                    time.sleep(delay)
            self._handle_snapshot(snapshot)
            if self.endpoint.feed(chunk):
                self._commit()

    def finish(self) -> None:
        snapshot = self.asr.feed(np.zeros(0, dtype=np.float32), final=True)
        self._handle_snapshot(snapshot)
        self._commit()
        self._note_worker.submit(self.writer.transcript())
        self._note_worker.close()
        rtfx = self.audio_seconds / max(self.compute_seconds, 1e-9)
        self.writer.append(
            SessionEvent.create(
                "metric",
                audio_seconds=self.audio_seconds,
                data={
                    "asr_compute_seconds": round(self.compute_seconds, 6),
                    "rtfx": round(rtfx, 3),
                    "last_note_seconds": round(
                        self._note_worker.last_generation_seconds, 6
                    ),
                },
            )
        )

    def _handle_snapshot(self, snapshot: TranscriptSnapshot | None) -> None:
        if snapshot is None:
            return
        self.compute_seconds += snapshot.compute_seconds
        partial = self.stabilizer.update(snapshot.text)
        self.writer.append(
            SessionEvent.create(
                "partial",
                audio_seconds=snapshot.audio_seconds,
                text=partial,
                data={"compute_seconds": snapshot.compute_seconds},
            )
        )
        if self.on_snapshot is not None:
            self.on_snapshot(snapshot, partial)

    def _commit(self) -> None:
        fragment = self.stabilizer.commit()
        if fragment:
            self.writer.append_utterance(fragment, self.audio_seconds)
            if self.audio_seconds - self._last_note_audio >= self.note_interval_seconds:
                self._note_worker.submit(self.writer.transcript())
                self._last_note_audio = self.audio_seconds


class _NoteWorker:
    """Single local note worker that coalesces stale incremental requests."""

    def __init__(self, generator: NoteGenerator, writer: SessionWriter) -> None:
        self.generator = generator
        self.writer = writer
        self.queue: Queue[str | None] = Queue(maxsize=1)
        self.error: BaseException | None = None
        self.last_generation_seconds = 0.0
        self.thread = Thread(
            target=self._run, name="meeting-notes-summary", daemon=True
        )

    def start(self) -> None:
        self.thread.start()

    def submit(self, transcript: str) -> None:
        try:
            self.queue.put_nowait(transcript)
        except Full:
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except Empty:
                pass
            self.queue.put_nowait(transcript)

    def close(self) -> None:
        self.queue.join()
        self.queue.put(None)
        self.thread.join()
        if self.error is not None:
            raise RuntimeError("local note generation failed") from self.error

    def _run(self) -> None:
        while True:
            transcript = self.queue.get()
            try:
                if transcript is None:
                    return
                started = time.perf_counter()
                self.writer.write_notes(self.generator.generate(transcript))
                self.last_generation_seconds = time.perf_counter() - started
            except BaseException as exc:
                self.error = exc
            finally:
                self.queue.task_done()
