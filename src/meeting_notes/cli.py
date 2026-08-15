from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .asr import DEFAULT_ASR_MODEL, NemotronStreamingASR
from .audio import MicrophoneSource, input_devices, iter_chunks, read_wav
from .endpoint import EndpointConfig, SilenceEndpoint
from .events import SessionEvent
from .notes import ExtractiveNoteGenerator, MLXNoteGenerator
from .runner import MeetingRunner
from .session import SessionWriter

app = typer.Typer(no_args_is_help=True, help="Local English live meeting notes.")
console = Console()


@app.command()
def models() -> None:
    """Show the default local models."""
    console.print(f"ASR: [bold]{DEFAULT_ASR_MODEL}[/bold]")
    console.print("Notes: mlx-community/Qwen3.5-4B-MLX-4bit (optional)")


@app.command()
def devices() -> None:
    """List microphone input devices."""
    table = Table("Index", "Input device", "Channels", "Default rate")
    for item in input_devices():
        table.add_row(
            str(item["index"]),
            str(item["name"]),
            str(item["channels"]),
            str(item["default_rate"]),
        )
    console.print(table)


def _notes_backend(kind: str, model_id: str):
    if kind == "extractive":
        return ExtractiveNoteGenerator()
    if kind == "mlx":
        return MLXNoteGenerator(model_id)
    raise typer.BadParameter("notes backend must be 'extractive' or 'mlx'")


def _runner(
    *,
    sessions_dir: Path,
    notes_backend: str,
    notes_model: str,
    threshold_dbfs: float,
    silence_ms: int,
    metadata: dict[str, object],
    note_interval_seconds: float,
) -> tuple[MeetingRunner, SessionWriter]:
    console.print("Loading local ASR model...")
    asr = NemotronStreamingASR()
    writer = SessionWriter(
        sessions_dir,
        model_id=asr.model_id,
        metadata=metadata,
    )
    endpoint = SilenceEndpoint(
        EndpointConfig(threshold_dbfs=threshold_dbfs, silence_ms=silence_ms)
    )

    display_state = {"partial": ""}

    def show(_snapshot, partial: str) -> None:
        previous = display_state["partial"]
        addition = partial[len(previous) :] if partial.startswith(previous) else partial
        display_state["partial"] = partial
        if addition:
            console.print(addition, end="", style="dim")

    return (
        MeetingRunner(
            asr,
            writer,
            _notes_backend(notes_backend, notes_model),
            endpoint=endpoint,
            on_snapshot=show,
            note_interval_seconds=note_interval_seconds,
        ),
        writer,
    )


@app.command()
def replay(
    audio: Annotated[Path, typer.Argument(exists=True, readable=True)],
    sessions_dir: Path = Path("sessions"),
    chunk_ms: int = 320,
    realtime: bool = False,
    notes_backend: str = "extractive",
    notes_model: str = "mlx-community/Qwen3.5-4B-MLX-4bit",
    threshold_dbfs: float = -38.0,
    silence_ms: int = 900,
    note_interval_seconds: float = 60.0,
) -> None:
    """Replay a PCM WAV through the same incremental pipeline."""
    pcm = read_wav(audio)
    runner, writer = _runner(
        sessions_dir=sessions_dir,
        notes_backend=notes_backend,
        notes_model=notes_model,
        threshold_dbfs=threshold_dbfs,
        silence_ms=silence_ms,
        note_interval_seconds=note_interval_seconds,
        metadata={"source": "replay", "audio_name": audio.name, "chunk_ms": chunk_ms},
    )
    started = time.perf_counter()
    runner.run(iter_chunks(pcm, round(16_000 * chunk_ms / 1000)), realtime=realtime)
    runner.finish()
    console.print(f"Completed in {time.perf_counter() - started:.2f}s")
    console.print(f"Session: [bold]{writer.path}[/bold]")


@app.command("start")
def start_live(
    sessions_dir: Path = Path("sessions"),
    device: str | None = None,
    chunk_ms: int = 320,
    notes_backend: str = "extractive",
    notes_model: str = "mlx-community/Qwen3.5-4B-MLX-4bit",
    threshold_dbfs: float = -38.0,
    silence_ms: int = 900,
    note_interval_seconds: float = 60.0,
) -> None:
    """Capture a local microphone until Ctrl-C, then write meeting notes."""
    parsed_device: int | str | None = (
        int(device) if device and device.isdigit() else device
    )
    runner, writer = _runner(
        sessions_dir=sessions_dir,
        notes_backend=notes_backend,
        notes_model=notes_model,
        threshold_dbfs=threshold_dbfs,
        silence_ms=silence_ms,
        note_interval_seconds=note_interval_seconds,
        metadata={"source": "microphone", "device": device, "chunk_ms": chunk_ms},
    )
    console.print("Listening locally. Press Ctrl-C to finish.")
    source = None
    try:
        with MicrophoneSource(device=parsed_device, chunk_ms=chunk_ms) as source:
            runner.run(source.chunks())
    except KeyboardInterrupt:
        console.print("\nFinalizing...")
    if source is not None:
        writer.append(
            SessionEvent.create(
                "metric",
                audio_seconds=runner.audio_seconds,
                data={
                    "microphone_dropped_chunks": source.dropped_chunks,
                    "microphone_status_count": len(source.status_messages),
                },
            )
        )
        for message in source.status_messages:
            writer.append(
                SessionEvent.create(
                    "warning", audio_seconds=runner.audio_seconds, text=message
                )
            )
    runner.finish()
    console.print(f"Session: [bold]{writer.path}[/bold]")


@app.command()
def summarize(
    session_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    notes_backend: str = "extractive",
    notes_model: str = "mlx-community/Qwen3.5-4B-MLX-4bit",
) -> None:
    """Regenerate notes from a completed local transcript."""
    transcript_path = session_dir / "transcript.txt"
    if not transcript_path.exists():
        raise typer.BadParameter("session has no transcript.txt")
    notes = _notes_backend(notes_backend, notes_model).generate(
        transcript_path.read_text(encoding="utf-8")
    )
    (session_dir / "notes.md").write_text(notes.rstrip() + "\n", encoding="utf-8")
    console.print(session_dir / "notes.md")


@app.command()
def recover(
    events: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    """Recover committed transcript text from append-only session events."""
    console.print(SessionWriter.recover_transcript(events))


@app.command()
def doctor() -> None:
    """Show a non-sensitive local runtime preflight."""
    import mlx
    import mlx_audio
    import mlx_lm
    import sounddevice

    console.print(
        json.dumps(
            {
                "mlx": getattr(mlx, "__version__", "installed"),
                "mlx_audio": getattr(mlx_audio, "__version__", "installed"),
                "mlx_lm": getattr(mlx_lm, "__version__", "installed"),
                "sounddevice": sounddevice.__version__,
            },
            indent=2,
        )
    )
