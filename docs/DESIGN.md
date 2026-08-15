# System Design

## 1. Objective

Build a MacBook-local POC that:

1. captures one English audio stream from a microphone;
2. displays incremental transcription with low perceived latency;
3. finalizes short utterances quickly after silence;
4. maintains an evolving set of meeting notes; and
5. exports the transcript and notes without sending audio or text to a cloud
   service.

The primary user experience is a terminal application. A native menu-bar or
desktop UI is intentionally deferred until the audio and latency path is proven.

## 2. Scope

### In scope

- Apple Silicon MacBook.
- English speech.
- One selected microphone or virtual audio input.
- Short, stateful streaming chunks.
- Live partial text and finalized utterances.
- Local structured notes containing summary, decisions, action items, and open
  questions.
- Markdown, plain-text, and JSONL session artifacts.
- File-replay mode for repeatable tests.

### Out of scope for the POC

- Speaker identification or diarization.
- Cloud transcription or cloud summarization.
- A production macOS GUI, installer, or App Store distribution.
- Calendar integrations, bots joining online meetings, or automatic sharing.
- Capturing protected system audio without an explicitly configured input.
- Treating generated notes as an authoritative record without human review.

## 3. Model choices

### Live transcription

Default model:

`mlx-community/nemotron-3.5-asr-streaming-0.6b-8bit`

It is selected because it is a small, cache-aware streaming ASR model and the
MLX runtime exposes stateful streaming generation. The model remains
configurable so the same harness can compare a later checkpoint without
rewriting the application.

### Meeting-note generation

Default candidate:

`mlx-community/Qwen3.5-4B-MLX-4bit`

The summarizer is deliberately behind an interface. The POC must also include a
deterministic extractive fallback so transcription, storage, and export remain
usable when the language model is unavailable.

### Optional quality pass

`mlx-community/whisper-large-v3-turbo-q4` may later re-transcribe completed
10-30 second utterances. It is not on the POC critical path because the first
question to answer is whether native streaming provides a good live experience.

## 4. Architecture

```text
Microphone / WAV replay
        |
        v
Audio capture -> bounded chunk queue -> adaptive silence endpointing
        |                                  |
        +----------------------------------v
                            Nemotron streaming ASR
                                      |
                         partial and final ASR events
                                      |
                             transcript stabilizer
                               /              \
                              v                v
                    terminal live view     session writer
                                               |
                                      finalized text batches
                                               |
                                      local note generator
                                               |
                                  notes.md + session.jsonl
```

## 5. Components

### 5.1 Audio capture

- Capture 16 kHz mono floating-point PCM.
- Use a callback that only copies audio into a bounded queue; inference never
  runs on the real-time audio callback.
- Start with 320 ms chunks and make 160, 320, 560, and 1120 ms selectable.
- Record queue overrun events rather than blocking and silently losing audio.
- Do not retain raw audio by default. `--save-audio` explicitly enables it.
- File-replay mode feeds the same queue and can run in wall-clock or accelerated
  mode.

### 5.2 Endpointing

- Use a lightweight adaptive RMS/noise-floor detector for the first POC.
- A short silence marks an utterance boundary; default target is 900 ms.
- Keep pre-roll and post-roll samples so consonants are not clipped.
- Manual `mark` and `flush` commands provide a safe fallback when endpointing is
  imperfect.
- A learned VAD can replace this component after latency and failure modes are
  measured.

### 5.3 Streaming ASR adapter

- Load and warm the model once per process.
- Preserve model streaming state across chunks.
- Emit typed events: `partial`, `final`, `language`, `warning`, and `metric`.
- Support configurable look-ahead/attention context.
- Keep model-specific objects inside the adapter so the rest of the application
  is model-independent.

### 5.4 Transcript stabilizer

- Keep partial hypotheses separate from committed text.
- Replace partial text in the terminal rather than appending duplicates.
- Commit only final text or text explicitly flushed at an endpoint.
- Attach monotonic timestamps and session-relative audio offsets.
- Normalize whitespace while preserving model punctuation and capitalization.

### 5.5 Session storage

Each session is written under a user-selected data directory:

```text
sessions/<timestamp>/
  manifest.json
  events.jsonl
  transcript.txt
  transcript.md
  notes.md
  audio.wav          # only with --save-audio
```

`events.jsonl` is append-only and is the recovery source if the process exits
unexpectedly. The manifest records model IDs, package versions, input device,
configuration, timings, and hashes, but no secrets.

### 5.6 Note generator

- Update notes only from finalized transcript text.
- Batch updates every 30-60 seconds or on explicit `summarize`.
- Send the previous structured state plus new transcript delta to the local LLM,
  rather than regenerating from the complete transcript every time.
- Require a fixed schema:

```text
Summary
Decisions
Action items (owner, action, due date when stated)
Open questions
```

- Never invent an owner or due date. Use `Unassigned` and `Not stated`.
- Preserve a link from every decision/action item to the relevant transcript
  time span when available.
- Final export performs one consolidation pass after the user stops the session.

### 5.7 Terminal interface

Planned commands:

```text
meeting-notes devices
meeting-notes models
meeting-notes start [--device ...] [--save-audio]
meeting-notes replay sample.wav [--realtime]
meeting-notes summarize SESSION_DIR
meeting-notes benchmark fixtures/
```

During a session:

- live partial transcript is visible but visually distinct;
- committed utterances remain stable;
- `m` inserts a meeting marker;
- `s` refreshes notes;
- `q` finalizes and exits cleanly.

## 6. Concurrency and backpressure

Use one process with bounded asynchronous stages:

1. the audio callback writes chunks;
2. the ASR worker owns model state and consumes chunks in order;
3. the session writer persists events;
4. the summarizer runs only after committed batches and never blocks ASR.

If the summarizer falls behind, coalesce pending transcript deltas. If ASR falls
behind, report queue depth and an overrun metric; do not discard events without
recording the loss.

## 7. Privacy and security

- No API keys or cloud endpoints.
- After model weights are cached, an offline test must succeed with network
  access disabled.
- Raw audio retention is opt-in.
- Session directories are ignored by Git.
- Logs must not contain environment variables or unrelated filesystem content.
- Model licenses and upstream attribution must be included before public release.

## 8. Observability

Record the following without storing sensitive process data:

- model load and warm-up time;
- chunk duration and queue depth;
- audio duration processed;
- ASR compute time and real-time factor;
- partial-result latency;
- utterance-finalization latency;
- note-update latency;
- peak resident memory;
- dropped/overrun audio duration;
- model and dependency versions.

## 9. POC acceptance criteria

The POC is accepted only when all of the following are demonstrated on the
target MacBook:

1. A cached-model, network-disabled run completes successfully.
2. A 15-minute live or wall-clock replay session has no unreported audio loss.
3. Median partial-result latency is at most 1.0 second and p95 is at most 1.8
   seconds.
4. A finalized utterance appears within 2.0 seconds after detected end of speech
   at p95.
5. ASR sustains at least 1.5x real-time throughput while note generation is
   enabled.
6. Clean single-speaker English WER is at most 8%; meeting English WER is at most
   12% on an independently reviewed reference.
7. Final notes are written within 10 seconds after stopping a 15-minute session.
8. Every action item either cites transcript evidence or is clearly marked as
   uncertain.
9. Unit tests, replay integration tests, Ruff, and package build all pass.

These are product targets, not claims about current performance. The existing
batch benchmark does not validate live MacBook latency.

## 10. Main risks

| Risk | Impact | Mitigation |
|---|---|---|
| MLX Nemotron streaming API is still evolving | Installation or API breakage | Pin an exact commit for the POC and isolate it behind an adapter |
| Small chunks reduce recognition accuracy | Incorrect names and sentence boundaries | Tune look-ahead, retain context, and test an optional Whisper quality pass |
| Concurrent ASR and LLM compete for unified memory/GPU | Latency spikes | Use bounded queues, a 4-bit summarizer, and suspend updates under ASR pressure |
| Energy endpointing fails in noisy rooms | Late or fragmented utterances | Adaptive noise floor, configurable silence, manual flush, later learned VAD |
| Generated notes overstate uncertain content | Misleading meeting record | Evidence spans, fixed schema, conservative prompts, human-review notice |
| Hardware differences are large | Targets pass on one Mac and fail on another | Record chip/RAM/macOS and publish device-specific benchmark results |

## 11. Decisions deferred until evidence exists

- Whether a Whisper background correction pass materially improves final notes.
- Whether speaker diarization is worth its latency and complexity.
- Whether the final product should be a native Swift menu-bar app or retain a
  Python service behind a thin UI.
- Which local summarizer size provides the best latency/quality tradeoff on the
  target MacBook.
