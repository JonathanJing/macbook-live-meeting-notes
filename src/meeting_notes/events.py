from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class TranscriptSnapshot:
    text: str
    audio_seconds: float
    compute_seconds: float
    final: bool = False


@dataclass(frozen=True)
class SessionEvent:
    kind: Literal["session", "partial", "utterance", "marker", "metric", "warning"]
    at: str
    audio_seconds: float
    text: str = ""
    data: dict[str, object] | None = None

    @classmethod
    def create(
        cls,
        kind: Literal["session", "partial", "utterance", "marker", "metric", "warning"],
        *,
        audio_seconds: float = 0.0,
        text: str = "",
        data: dict[str, object] | None = None,
    ) -> SessionEvent:
        return cls(kind, utc_now(), audio_seconds, text, data)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
