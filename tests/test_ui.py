from meeting_notes.ui import UI_HTML, MeetingUIController


def test_ui_has_accessible_live_regions_and_microphone_label() -> None:
    assert '<label class="sr-only" for="device">Microphone</label>' in UI_HTML
    assert 'id="status" class="status" role="status" aria-live="polite"' in UI_HTML
    assert 'id="transcript" aria-live="polite" aria-atomic="false"' in UI_HTML
    assert 'id="error" class="error-text" role="alert"' in UI_HTML


def test_ui_microphone_select_can_shrink_on_narrow_screens() -> None:
    assert "select { min-width: 0; max-width: 100%" in UI_HTML
    assert "select { flex-basis: 100%; width: 100%; }" in UI_HTML


def test_ui_javascript_keeps_newline_escape_inside_string_literal() -> None:
    assert "(s.transcript?'\\n':'')" in UI_HTML


def test_ui_has_open_recordings_folder_button() -> None:
    assert (
        '<button id="reveal" class="secondary">Open recordings folder</button>'
        in UI_HTML
    )
    assert "post('/api/reveal')" in UI_HTML


def test_reveal_sessions_opens_resolved_folder(tmp_path, monkeypatch) -> None:
    calls: list[tuple[list[str], bool]] = []

    def fake_run(command: list[str], *, check: bool) -> None:
        calls.append((command, check))

    monkeypatch.setattr("meeting_notes.ui.subprocess.run", fake_run)
    sessions_dir = tmp_path / "recordings"
    controller = MeetingUIController(sessions_dir)

    assert controller.reveal_sessions() == sessions_dir.resolve()
    assert sessions_dir.is_dir()
    assert calls == [(["open", str(sessions_dir.resolve())], True)]
