# ruff: noqa: E501
from __future__ import annotations

import json
import subprocess
import threading
import webbrowser
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .asr import NemotronStreamingASR
from .audio import MicrophoneSource, input_devices, save_wav_chunks
from .endpoint import EndpointConfig, SilenceEndpoint
from .events import SessionEvent
from .notes import MLXNoteGenerator
from .runner import MeetingRunner
from .session import SessionWriter

DEFAULT_NOTES_MODEL = "mlx-community/Qwen3.5-4B-MLX-4bit"


@dataclass
class UIState:
    status: str = "idle"
    message: str = "Ready"
    session_path: str = ""
    transcript: str = ""
    partial: str = ""
    notes: str = ""
    audio_seconds: float = 0.0
    audio_file: str = ""
    transcript_file: str = ""
    notes_file: str = ""
    error: str = ""


class MeetingUIController:
    def __init__(self, sessions_dir: Path) -> None:
        self.sessions_dir = sessions_dir
        self._state = UIState()
        self._lock = threading.Lock()
        self._source: MicrophoneSource | None = None
        self._writer: SessionWriter | None = None
        self._stop_requested = threading.Event()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            snapshot = asdict(self._state)
            writer = self._writer
        if writer is not None and writer.notes_path.exists():
            snapshot["notes"] = writer.notes_path.read_text(encoding="utf-8")
        return snapshot

    def start(self, device: int | str | None = None) -> bool:
        with self._lock:
            if self._state.status in {"loading", "listening", "finalizing"}:
                return False
            self._state = UIState(status="loading", message="Loading local models…")
            self._writer = None
        self._stop_requested.clear()
        threading.Thread(
            target=self._record,
            args=(device,),
            name="meeting-notes-ui-session",
            daemon=True,
        ).start()
        return True

    def stop(self) -> bool:
        with self._lock:
            if self._state.status not in {"loading", "listening"}:
                return False
            self._state.status = "finalizing"
            self._state.message = "Finalizing transcript and notes…"
            source = self._source
        self._stop_requested.set()
        if source is not None:
            source.request_stop()
        return True

    def reveal_sessions(self) -> Path:
        """Open the local recordings root in Finder."""
        path = self.sessions_dir.resolve()
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(path)], check=True)
        return path

    def _record(self, device: int | str | None) -> None:
        writer: SessionWriter | None = None
        source: MicrophoneSource | None = None
        try:
            asr = NemotronStreamingASR()
            notes = MLXNoteGenerator(DEFAULT_NOTES_MODEL)
            if self._stop_requested.is_set():
                with self._lock:
                    self._state = UIState(message="Stopped before recording started")
                return

            writer = SessionWriter(
                self.sessions_dir,
                model_id=asr.model_id,
                metadata={
                    "source": "microphone-ui",
                    "device": device,
                    "chunk_ms": 320,
                    "notes_model": DEFAULT_NOTES_MODEL,
                    "audio_saved": True,
                },
            )
            with self._lock:
                self._writer = writer

            def on_snapshot(_snapshot, partial: str) -> None:
                with self._lock:
                    self._state.partial = partial
                    self._state.audio_seconds = runner.audio_seconds

            def on_commit(_fragment: str) -> None:
                with self._lock:
                    self._state.transcript = writer.transcript()
                    self._state.partial = ""

            runner = MeetingRunner(
                asr,
                writer,
                notes,
                endpoint=SilenceEndpoint(EndpointConfig()),
                on_snapshot=on_snapshot,
                on_commit=on_commit,
                note_interval_seconds=60.0,
            )
            with self._lock:
                self._state.status = "listening"
                self._state.message = "Listening on this Mac"
                self._state.session_path = str(writer.path.resolve())
                self._state.audio_file = writer.audio_path.name
                self._state.transcript_file = writer.transcript_path.name
                self._state.notes_file = writer.notes_path.name

            source = MicrophoneSource(device=device, chunk_ms=320)
            with self._lock:
                self._source = source
            with source:
                runner.run(
                    save_wav_chunks(
                        source.chunks(),
                        writer.audio_path,
                        sample_rate=source.sample_rate,
                    )
                )

            self._append_microphone_metrics(writer, runner, source)
            with self._lock:
                self._state.status = "finalizing"
                self._state.message = "Generating final notes locally…"
            runner.finish()
            with self._lock:
                self._state.status = "completed"
                self._state.message = "Saved audio, transcript, and notes"
                self._state.transcript = writer.transcript()
                self._state.partial = ""
                self._state.notes = writer.notes_path.read_text(encoding="utf-8")
                self._state.audio_seconds = runner.audio_seconds
        except BaseException as exc:
            with self._lock:
                self._state.status = "error"
                self._state.message = "Session failed"
                self._state.error = f"{type(exc).__name__}: {exc}"
                if writer is not None:
                    self._state.session_path = str(writer.path.resolve())
        finally:
            with self._lock:
                self._source = None

    @staticmethod
    def _append_microphone_metrics(
        writer: SessionWriter, runner: MeetingRunner, source: MicrophoneSource
    ) -> None:
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


def serve_ui(
    sessions_dir: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    controller = MeetingUIController(sessions_dir)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/":
                self._send(HTTPStatus.OK, UI_HTML, "text/html; charset=utf-8")
            elif self.path == "/api/state":
                self._json(HTTPStatus.OK, controller.snapshot())
            elif self.path == "/api/devices":
                try:
                    self._json(HTTPStatus.OK, {"devices": input_devices()})
                except BaseException as exc:
                    self._json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {"error": f"{type(exc).__name__}: {exc}"},
                    )
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON"})
                return
            if self.path == "/api/start":
                value = payload.get("device")
                device = int(value) if str(value).isdigit() else value or None
                started = controller.start(device)
                self._json(
                    HTTPStatus.ACCEPTED if started else HTTPStatus.CONFLICT,
                    controller.snapshot(),
                )
            elif self.path == "/api/stop":
                stopped = controller.stop()
                self._json(
                    HTTPStatus.ACCEPTED if stopped else HTTPStatus.CONFLICT,
                    controller.snapshot(),
                )
            elif self.path == "/api/reveal":
                try:
                    path = controller.reveal_sessions()
                    self._json(HTTPStatus.OK, {"path": str(path)})
                except (OSError, subprocess.CalledProcessError) as exc:
                    self._json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {"error": f"Could not open Finder: {exc}"},
                    )
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _json(self, status: HTTPStatus, payload: object) -> None:
            self._send(
                status,
                json.dumps(payload, ensure_ascii=False),
                "application/json; charset=utf-8",
            )

        def _send(self, status: HTTPStatus, body: str, content_type: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer((host, port), Handler)
    if open_browser:
        threading.Timer(0.4, webbrowser.open, args=(f"http://{host}:{port}",)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()
        server.server_close()


UI_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Local Meeting Notes</title>
  <style>
    :root { color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif; }
    body { margin: 0; background: #f5f5f7; color: #1d1d1f; }
    main { max-width: 980px; margin: 0 auto; padding: 40px 20px 64px; }
    h1 { margin: 0 0 6px; font-size: 32px; }
    .sub { color: #6e6e73; margin: 0 0 28px; }
    .toolbar, .card { background: white; border: 1px solid #e5e5e7; border-radius: 16px; padding: 18px; }
    .toolbar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
    select, button { border-radius: 10px; border: 1px solid #c7c7cc; padding: 10px 14px; font-size: 15px; }
    select { min-width: 0; max-width: 100%; flex: 1 1 280px; background: white; }
    button { border: 0; background: #0071e3; color: white; font-weight: 600; cursor: pointer; }
    button.stop { background: #d70015; }
    button.secondary { background: #e8e8ed; color: #1d1d1f; }
    button:disabled { opacity: .45; cursor: default; }
    .status { margin-left: auto; color: #6e6e73; }
    .dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: #8e8e93; margin-right: 7px; }
    .listening .dot { background: #34c759; box-shadow: 0 0 0 4px #34c75922; }
    .error .dot { background: #d70015; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }
    .card h2 { margin: 0 0 12px; font-size: 18px; }
    pre { white-space: pre-wrap; word-wrap: break-word; margin: 0; min-height: 250px; font: 14px/1.55 ui-monospace, SFMono-Regular, Menlo, monospace; }
    .partial { color: #8e8e93; }
    .files { margin-top: 16px; color: #6e6e73; font-size: 13px; overflow-wrap: anywhere; }
    .error-text { color: #d70015; margin-top: 10px; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
    @media (max-width: 700px) { .grid { grid-template-columns: 1fr; } .status { width: 100%; margin-left: 0; } select { flex-basis: 100%; width: 100%; } }
  </style>
</head>
<body><main>
  <h1>Local Meeting Notes</h1>
  <p class="sub">Nemotron ASR + Qwen3.5 4B · audio and text stay on this Mac</p>
  <section class="toolbar">
    <label class="sr-only" for="device">Microphone</label>
    <select id="device"><option value="">Default microphone</option></select>
    <button id="start">Start recording</button>
    <button id="stop" class="stop" disabled>Stop & save</button>
    <button id="reveal" class="secondary">Open recordings folder</button>
    <span id="status" class="status" role="status" aria-live="polite"><span class="dot"></span><span>Ready</span></span>
  </section>
  <div id="error" class="error-text" role="alert"></div>
  <div class="grid">
    <section class="card"><h2>Live transcript</h2><pre id="transcript" aria-live="polite" aria-atomic="false">Waiting to start…</pre></section>
    <section class="card"><h2>Meeting notes</h2><pre id="notes" aria-live="polite">Notes are generated locally while recording and finalized when you stop.</pre></section>
  </div>
  <div id="files" class="files"></div>
</main>
<script>
const start = document.querySelector('#start'), stop = document.querySelector('#stop'), reveal = document.querySelector('#reveal');
const device = document.querySelector('#device'), transcript = document.querySelector('#transcript');
const notes = document.querySelector('#notes'), status = document.querySelector('#status');
const files = document.querySelector('#files'), error = document.querySelector('#error');
async function post(path, body={}) { return fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}); }
async function loadDevices() {
  const data = await fetch('/api/devices').then(r => r.json());
  for (const d of data.devices || []) { const o=document.createElement('option'); o.value=d.index; o.textContent=`${d.index}: ${d.name}`; device.appendChild(o); }
}
function render(s) {
  const active = ['loading','listening','finalizing'].includes(s.status);
  start.disabled = active; stop.disabled = !['loading','listening'].includes(s.status); device.disabled = active;
  status.className = `status ${s.status}`; status.innerHTML = `<span class="dot"></span><span>${s.message}${s.audio_seconds ? ` · ${s.audio_seconds.toFixed(1)}s` : ''}</span>`;
  transcript.innerHTML = escapeHtml(s.transcript || '') + (s.partial ? `<span class="partial">${escapeHtml((s.transcript?'\\n':'') + s.partial)}</span>` : '') || 'Waiting to start…';
  if (s.notes) notes.textContent = s.notes;
  error.textContent = s.error || '';
  files.textContent = s.session_path ? `Saved in ${s.session_path} · ${[s.audio_file,s.transcript_file,s.notes_file].filter(Boolean).join(' · ')}` : '';
}
function escapeHtml(value) { const d=document.createElement('div'); d.textContent=value; return d.innerHTML; }
start.onclick = async () => { const r=await post('/api/start',{device:device.value}); render(await r.json()); };
stop.onclick = async () => { const r=await post('/api/stop'); render(await r.json()); };
reveal.onclick = async () => { const r=await post('/api/reveal'); const data=await r.json(); if (!r.ok) error.textContent=data.error || 'Could not open Finder'; };
async function poll() { try { render(await fetch('/api/state').then(r=>r.json())); } catch (_) {} }
loadDevices().catch(e => { error.textContent = `Could not list microphones: ${e}`; }); poll(); setInterval(poll, 700);
</script></body></html>"""
