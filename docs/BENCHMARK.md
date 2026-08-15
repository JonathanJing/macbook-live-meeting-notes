# Benchmark and validation evidence

## Test system

- Mac: Apple M1 Max
- Unified memory: 64 GB
- macOS: 27.0 build 26A5388g
- Python: 3.12.8
- ASR: `mlx-community/nemotron-3.5-asr-streaming-0.6b-8bit`
- `mlx-audio`: commit `727fc9301de58b2179eff415710b7d95dda59169`
- Notes: `mlx-community/Qwen3.5-4B-MLX-4bit`

Measurements below are from 2026-08-14/15. They are POC evidence, not portable
performance guarantees.

## ASR preflight

A private 20-second English single-speaker sample was converted temporarily to
16 kHz mono PCM. Neither the media nor its transcript is included in this repo.

| Configuration | Compute time | RTFx | First non-empty result at audio position |
|---|---:|---:|---:|
| `[56, 0]`, 80 ms | 5.709 s | 3.50x | 2.32 s |
| `[56, 3]`, 320 ms | 1.911 s | 10.47x | 2.56 s |
| `[56, 6]`, 560 ms | 1.335 s | 14.98x | 2.80 s |
| `[56, 13]`, 1120 ms | 0.903 s | 22.16x | 3.36 s |

The POC defaults to `[56, 3]` with 320 ms microphone chunks. “First non-empty
result” is affected by when the model emits its first tokens and is not the same as
compute latency after speech is available.

The upstream whole-file streaming path peaked at about 1.34 GB resident memory in
the measured run.

## End-to-end replay

The repository's own incremental `feed()` adapter processed the 20-second sample
with 320 ms input chunks:

- ASR compute: 1.87-1.91 seconds
- Throughput: 10.46-10.70x real-time
- Final local 4B note generation: 1.31-1.33 seconds
- Combined ASR and 4B note process peak resident memory: about 3.86 GB
- Output: manifest, append-only events, transcript, and Markdown notes

The ASR result contained a proper-name error (`Mariners` rendered as `Mary's`), so
this evidence proves performance and plumbing, not the final accuracy gate.

## Microphone smoke

The MacBook Pro microphone was captured at 16 kHz in 320 ms chunks:

- 10-chunk capture: zero dropped chunks and no Core Audio status errors
- 5-chunk full ASR/session smoke: zero dropped chunks, clean finalization
- Silent-session regression: an explicit empty `notes.md` is produced

No microphone audio was retained.

## Offline smoke

With both `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, cached ASR and note
models completed the full replay pipeline and produced non-empty transcript and
note artifacts.

## Automated checks

At the time this report was written:

- pytest: 11 passed
- Ruff lint: passed
- Ruff format check: passed

## Remaining acceptance work

The following design gates remain intentionally unclaimed:

- a 15-minute live spoken meeting test;
- p50/p95 latency measured against actual speech/token availability;
- independently reviewed short-fragment and meeting WER;
- sustained concurrent incremental MLX note updates during a long session;
- testing across additional Apple Silicon generations and memory sizes.
