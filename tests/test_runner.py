import numpy as np

from meeting_notes.endpoint import EndpointConfig, SilenceEndpoint
from meeting_notes.events import TranscriptSnapshot
from meeting_notes.notes import ExtractiveNoteGenerator
from meeting_notes.runner import MeetingRunner
from meeting_notes.session import SessionWriter


class FakeASR:
    sample_rate = 1000

    def __init__(self) -> None:
        self.calls = 0

    def feed(self, samples, *, final=False):
        self.calls += 1
        texts = {
            1: "Hello team.",
            2: "Hello team. We decided to ship Friday.",
            3: "Hello team. We decided to ship Friday.",
        }
        text = texts.get(self.calls, texts[3])
        return TranscriptSnapshot(text, self.calls * 0.1, 0.01, final)


def test_runner_commits_on_endpoint_and_writes_notes(tmp_path) -> None:
    writer = SessionWriter(tmp_path, model_id="fake", session_id="run")
    endpoint = SilenceEndpoint(
        EndpointConfig(
            sample_rate=1000,
            threshold_dbfs=-30,
            minimum_speech_ms=100,
            silence_ms=100,
        )
    )
    runner = MeetingRunner(
        FakeASR(), writer, ExtractiveNoteGenerator(), endpoint=endpoint
    )
    runner.run(
        [
            np.full(100, 0.1, dtype=np.float32),
            np.zeros(100, dtype=np.float32),
        ]
    )
    runner.finish()
    assert "We decided to ship Friday." in writer.transcript()
    assert "## Decisions" in writer.notes_path.read_text(encoding="utf-8")
    assert '"rtfx"' in writer.events_path.read_text(encoding="utf-8")


class EmptyASR:
    sample_rate = 1000

    def feed(self, samples, *, final=False):
        return TranscriptSnapshot("", 0.0, 0.0, final)


def test_runner_writes_notes_for_silent_session(tmp_path) -> None:
    writer = SessionWriter(tmp_path, model_id="fake", session_id="silent")
    runner = MeetingRunner(EmptyASR(), writer, ExtractiveNoteGenerator())
    runner.run([])
    runner.finish()
    assert writer.notes_path.exists()
    assert "No finalized transcript yet." in writer.notes_path.read_text(
        encoding="utf-8"
    )
