from __future__ import annotations


class TranscriptStabilizer:
    """Separate cumulative ASR hypotheses from committed utterances."""

    def __init__(self) -> None:
        self._committed = ""
        self._latest = ""

    @property
    def committed(self) -> str:
        return self._committed.strip()

    @property
    def partial(self) -> str:
        latest = self._latest.strip()
        committed = self._committed.strip()
        if not committed:
            return latest
        if latest.startswith(committed):
            return latest[len(committed) :].strip()
        return latest

    def update(self, cumulative_text: str) -> str:
        self._latest = " ".join(cumulative_text.split())
        return self.partial

    def commit(self) -> str:
        fragment = self.partial
        if not fragment:
            return ""
        self._committed = " ".join(
            piece for piece in (self._committed.strip(), fragment) if piece
        )
        return fragment
