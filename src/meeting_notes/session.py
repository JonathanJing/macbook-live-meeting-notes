from __future__ import annotations

import json
import platform
from datetime import UTC, datetime
from pathlib import Path

from .events import SessionEvent


class SessionWriter:
    def __init__(
        self,
        root: Path,
        *,
        model_id: str,
        metadata: dict[str, object] | None = None,
        session_id: str | None = None,
    ) -> None:
        self.session_id = session_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        self.path = root / self.session_id
        self.path.mkdir(parents=True, exist_ok=False)
        self.events_path = self.path / "events.jsonl"
        self.transcript_path = self.path / "transcript.txt"
        self.transcript_markdown_path = self.path / "transcript.md"
        self.notes_path = self.path / "notes.md"
        self.manifest_path = self.path / "manifest.json"
        manifest = {
            "schema_version": 1,
            "session_id": self.session_id,
            "created_at": datetime.now(UTC).isoformat(),
            "model_id": model_id,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "metadata": metadata or {},
        }
        self.manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        self.append(SessionEvent.create("session", data=manifest))

    def append(self, event: SessionEvent) -> None:
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    def append_utterance(self, text: str, audio_seconds: float) -> None:
        clean = " ".join(text.split())
        if not clean:
            return
        with self.transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(clean + "\n")
        with self.transcript_markdown_path.open("a", encoding="utf-8") as handle:
            handle.write(f"- [{_clock(audio_seconds)}] {clean}\n")
        self.append(
            SessionEvent.create("utterance", audio_seconds=audio_seconds, text=clean)
        )

    def transcript(self) -> str:
        if not self.transcript_path.exists():
            return ""
        return self.transcript_path.read_text(encoding="utf-8").strip()

    def write_notes(self, content: str) -> None:
        temporary = self.notes_path.with_suffix(".md.tmp")
        temporary.write_text(content.rstrip() + "\n", encoding="utf-8")
        temporary.replace(self.notes_path)

    @staticmethod
    def recover_transcript(events_path: Path) -> str:
        utterances: list[str] = []
        for line in events_path.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event.get("kind") == "utterance" and event.get("text"):
                utterances.append(str(event["text"]))
        return "\n".join(utterances)


def _clock(seconds: float) -> str:
    total = max(0, round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
