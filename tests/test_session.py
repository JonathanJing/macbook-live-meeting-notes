import json

from meeting_notes.events import SessionEvent
from meeting_notes.session import SessionWriter


def test_session_writes_and_recovers_committed_text(tmp_path) -> None:
    writer = SessionWriter(tmp_path, model_id="test-model", session_id="fixed")
    writer.append_utterance("Hello world.", 1.2)
    writer.append(SessionEvent.create("partial", audio_seconds=1.4, text="ignored"))
    writer.append_utterance("We decided to ship.", 2.5)
    assert writer.transcript() == "Hello world.\nWe decided to ship."
    assert "[00:00:01] Hello world." in writer.transcript_markdown_path.read_text(
        encoding="utf-8"
    )
    assert SessionWriter.recover_transcript(writer.events_path) == writer.transcript()
    manifest = json.loads(writer.manifest_path.read_text(encoding="utf-8"))
    assert manifest["model_id"] == "test-model"
    assert writer.transcript_path.name == "fixed_transcript.txt"
    assert writer.notes_path.name == "fixed_notes.md"
    assert writer.audio_path.name == "fixed_audio.wav"


def test_session_creates_empty_transcript_artifacts_immediately(tmp_path) -> None:
    writer = SessionWriter(tmp_path, model_id="test-model", session_id="empty")
    assert writer.transcript_path.read_text(encoding="utf-8") == ""
    assert writer.transcript_markdown_path.read_text(encoding="utf-8") == ""
