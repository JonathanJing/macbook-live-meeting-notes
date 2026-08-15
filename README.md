# MacBook Live Meeting Notes

Local-first English live transcription and rapid meeting-note generation on
Apple Silicon. Audio, transcript, and notes stay on the Mac.

This proof of concept combines:

- `mlx-community/nemotron-3.5-asr-streaming-0.6b-8bit` for incremental ASR;
- a deterministic extractive note backend that always works offline; and
- optional `mlx-community/Qwen3.5-4B-MLX-4bit` notes for higher-quality summaries.

## POC status

The CLI, true incremental model adapter, microphone input, WAV replay, durable
session artifacts, extractive notes, optional MLX-LM notes, and offline cached-model
flow are implemented. See [measured evidence](docs/BENCHMARK.md) and
[known limitations](#known-limitations) before relying on it for a meeting.

## Requirements

- Apple Silicon Mac
- macOS 14 or newer
- Python 3.11-3.13 (3.12 tested)
- `uv`
- microphone permission for the terminal application

Model downloads require network access once. Cached models can then run offline.

## Install

```bash
git clone https://github.com/JonathanJing/macbook-live-meeting-notes.git
cd macbook-live-meeting-notes
uv sync --extra dev --extra notes --python 3.12
uv run meeting-notes doctor
```

The first ASR run downloads approximately 756 MB of weights. The optional 4-bit
note model uses several additional gigabytes.

## Use

List inputs:

```bash
uv run meeting-notes devices
```

Start local microphone transcription with fast extractive notes:

```bash
uv run meeting-notes start
```

Use the local 4B note model:

```bash
uv run meeting-notes start --notes-backend mlx
```

Press `Ctrl-C` to finalize the transcript and notes.

Replay a 16-bit PCM WAV through the same incremental pipeline:

```bash
uv run meeting-notes replay meeting.wav --notes-backend mlx
```

Regenerate notes from a completed session:

```bash
uv run meeting-notes summarize sessions/SESSION_ID --notes-backend mlx
```

## Session artifacts

```text
sessions/<UTC timestamp>/
  manifest.json
  events.jsonl
  transcript.txt
  transcript.md
  notes.md
```

`events.jsonl` is append-only. Recover committed text with:

```bash
uv run meeting-notes recover sessions/SESSION_ID/events.jsonl
```

Raw audio is not saved by the POC. The complete `sessions/` directory is ignored
by Git.

## Privacy

- No OpenAI API or other cloud inference API is used.
- No API key is required.
- Model files are loaded from the local Hugging Face cache after initial download.
- Set `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` to require cached-model operation.
- Transcripts and meeting notes are local session artifacts and are excluded from
  Git.

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
python -m build
```

The unit suite does not load model weights or access a microphone.

## Known limitations

- English only in the POC interface.
- No speaker diarization or speaker identity.
- Endpointing uses a simple configurable energy threshold, not a learned VAD.
- Proper nouns can be wrong; the measured sample confused `Mariners`/`Mary's`.
- The low-level Nemotron adapter is pinned to a specific `mlx-audio` commit because
  the upstream package does not yet expose a complete live-microphone `feed()` API.
- The current terminal view emits incremental text but is not a polished full-screen
  UI.
- Meeting notes are generated text and must be checked against the transcript.
- The 15-minute live acceptance run and independently reviewed short-fragment WER
  gate remain outstanding.

## Project documents

- [System design](docs/DESIGN.md)
- [Development plan](docs/DEVELOPMENT_PLAN.md)
- [Benchmark and validation evidence](docs/BENCHMARK.md)
- [Model attribution](MODEL_ATTRIBUTION.md)

## License

Repository code is MIT licensed. Model weights have separate upstream terms; see
[MODEL_ATTRIBUTION.md](MODEL_ATTRIBUTION.md).
