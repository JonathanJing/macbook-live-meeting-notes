# Development Plan

## Working rules

- Complete each phase's verification gate before starting the next phase.
- Keep all model and audio backends behind interfaces so tests do not download
  weights or require a microphone.
- Commit generated sessions, recordings, model weights, and caches to neither
  Git nor GitHub.
- Treat live latency, quality, and offline operation as acceptance evidence;
  passing unit tests alone is insufficient.

## Phase 0: Environment preflight

### Work

- Record the target Mac chip, memory, macOS version, Python version, microphone
  permissions, and available disk space.
- Confirm the selected model loads through `mlx-audio`.
- Confirm stateful `stream_generate` works on a short English WAV file.
- Measure model load time, first-result latency, memory, and real-time factor.
- Choose and pin the exact `mlx-audio` revision used by the POC.

### Gate

- A 60-second English file produces ordered streaming results locally.
- No source build or dependency requires an unsupported platform.
- Exact dependency and model revisions are recorded.

## Phase 1: Repository and test skeleton

### Work

- Create a Python `src/` package with `pyproject.toml` and a locked environment.
- Add CLI entry points and configuration models.
- Define typed events and protocols for audio input, ASR, session storage, and
  note generation.
- Add Ruff and pytest configuration.
- Add `.gitignore`, license, contribution notes, and a model-attribution file.

### Gate

- Package installs in a clean virtual environment.
- CLI help runs without loading model weights.
- Unit tests and Ruff pass.

## Phase 2: File-replay streaming core

### Work

- Implement WAV decoding/resampling to 16 kHz mono.
- Implement bounded chunk queues and wall-clock replay.
- Implement the Nemotron adapter with persistent streaming state.
- Implement partial/final ASR event handling and transcript stabilization.
- Add fixture audio and reviewed reference text with redistribution permission.

### Gate

- Replay produces deterministic, ordered events without duplicate committed
  text.
- Queue-overflow behavior is covered by tests.
- Latency and WER report generation works before microphone integration.

## Phase 3: Microphone capture

### Work

- Enumerate and select Core Audio input devices through `sounddevice`.
- Add non-blocking capture and explicit macOS microphone-permission guidance.
- Add adaptive endpointing, pre-roll, post-roll, manual marker, and flush.
- Ensure Ctrl-C and `q` finalize files without corrupting JSONL.

### Gate

- A 15-minute live session completes with no unreported audio loss.
- Device disconnect and queue-overrun conditions produce actionable errors.
- Partial and finalized text are visually distinguishable.

## Phase 4: Durable session artifacts

### Work

- Implement append-only event logging and crash recovery.
- Generate transcript text and Markdown with timestamps.
- Write a manifest containing versions, timings, hashes, and input settings.
- Make audio retention opt-in and verify ignored paths.

### Gate

- Forced termination leaves recoverable committed text.
- Rebuilding transcript artifacts from JSONL is deterministic.
- No session content appears in Git status.

## Phase 5: Local meeting-note generation

### Work

- Implement the note-generator protocol and deterministic fallback.
- Integrate a configurable MLX-LM backend, initially testing a 4-bit 4B model.
- Add incremental structured-state updates and final consolidation.
- Add transcript evidence spans for decisions and action items.
- Coalesce summaries under backpressure so ASR remains the priority.

### Gate

- Notes update during a live session without blocking ASR.
- Final notes are produced within the latency target.
- Frozen transcript cases verify that absent owners/dates are not invented.

## Phase 6: Benchmark and tuning

### Work

- Reuse English single-speaker and meeting audio from the ASR work benchmark
  only through local, ignored configuration; do not copy private media into Git.
- Add short-utterance cases, silence/noise cases, names, acronyms, numbers, and
  interruptions.
- Measure latency distributions, WER, memory, throughput, dropped audio, and
  note latency.
- Compare 160, 320, 560, and 1120 ms chunks and supported look-ahead settings.
- Test with networking disabled after models are cached.

### Gate

- Produce a hardware-stamped benchmark report.
- Meet every POC acceptance criterion or explicitly mark the POC as not yet
  accepted.
- Document any gap between replay and live microphone behavior.

## Phase 7: Release preparation

### Work

- Write setup, model-download, microphone-permission, usage, troubleshooting,
  privacy, and benchmark documentation.
- Verify all model and code licenses and include attribution.
- Add a short, redistributable demo or synthetic fixture.
- Run a clean-clone installation and smoke test.
- Inspect tracked files for session data, recordings, absolute private paths,
  and credentials.

### Gate

- Tests, Ruff, package build, clean-clone smoke, and offline smoke pass.
- README clearly labels limitations and tested hardware.
- Repository contains no private audio, transcripts, secrets, or model weights.

## Phase 8: GitHub publication

### Work

- Review the exact staged file list and diff.
- Create the initial commit only after commit authorization is confirmed.
- Create the GitHub repository with the agreed visibility.
- Push `main` only after push authorization is confirmed.
- Verify the remote URL, default branch, README rendering, license, and absence
  of sensitive files.
- Optionally create a versioned POC release after the remote smoke check.

### Gate

- Local HEAD and remote `main` match.
- GitHub repository visibility matches the user's decision.
- GitHub's file list contains only the reviewed publication set.

## Suggested implementation order

The shortest path to evidence is:

1. prove Nemotron stateful replay;
2. build the event and metric contracts;
3. add microphone capture;
4. make session recovery reliable;
5. add local incremental notes;
6. benchmark the actual MacBook;
7. publish only the verified POC.

This ordering deliberately postpones GUI work and optional diarization until the
core latency and transcription-quality assumptions are validated.
