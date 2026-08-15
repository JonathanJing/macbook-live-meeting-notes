from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol


class NoteGenerator(Protocol):
    def generate(self, transcript: str) -> str: ...


def _sentences(text: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"(?<=[.!?])\s+|\n+", text.strip())
        if item.strip()
    ]


@dataclass
class ExtractiveNoteGenerator:
    summary_sentences: int = 5
    action_patterns: tuple[re.Pattern[str], ...] = field(
        default_factory=lambda: (
            re.compile(r"\b(?:I|we|you|they)\s+(?:will|need to|should|must)\b", re.I),
            re.compile(r"\baction item\b", re.I),
        )
    )
    decision_pattern: re.Pattern[str] = field(
        default_factory=lambda: re.compile(
            r"\b(?:we decided|decision is|agreed to|approved|will proceed)\b", re.I
        )
    )

    def generate(self, transcript: str) -> str:
        sentences = _sentences(transcript)
        decisions = [s for s in sentences if self.decision_pattern.search(s)]
        actions = [
            s
            for s in sentences
            if any(pattern.search(s) for pattern in self.action_patterns)
        ]
        questions = [s for s in sentences if s.endswith("?")]
        summary = sentences[: self.summary_sentences]
        return "\n".join(
            (
                "# Meeting notes",
                "",
                "## Summary",
                _bullets(summary, "No finalized transcript yet."),
                "",
                "## Decisions",
                _bullets(decisions, "None detected."),
                "",
                "## Action items",
                _bullets(actions, "None detected. Owners and dates require review."),
                "",
                "## Open questions",
                _bullets(questions, "None detected."),
                "",
                (
                    "> Extractive POC output. Review against the transcript before "
                    "sharing."
                ),
            )
        )


class MLXNoteGenerator:
    def __init__(
        self,
        model_id: str = "mlx-community/Qwen3.5-4B-MLX-4bit",
        *,
        max_tokens: int = 500,
    ) -> None:
        from mlx_lm import load

        self.model_id = model_id
        self.max_tokens = max_tokens
        self.model, self.tokenizer = load(model_id)

    def generate(self, transcript: str) -> str:
        from mlx_lm import generate

        prompt = (
            "Create concise English meeting notes from the transcript. Use exactly "
            "these Markdown headings: Summary, Decisions, Action items, Open "
            "questions. Do not invent owners, dates, or decisions. Mark missing "
            "owners as Unassigned and missing dates as Not stated.\n\nTranscript:\n"
            + transcript
        )
        messages = [{"role": "user", "content": prompt}]
        rendered = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        output = generate(
            self.model,
            self.tokenizer,
            prompt=rendered,
            max_tokens=self.max_tokens,
            verbose=False,
        ).strip()
        required = ("Summary", "Decisions", "Action items", "Open questions")
        if not all(heading in output for heading in required):
            raise ValueError("local note model returned an incomplete note structure")
        return output


def _bullets(items: list[str], empty: str) -> str:
    return "\n".join(f"- {item}" for item in items) if items else f"- {empty}"
