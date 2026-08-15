from meeting_notes.ui import UI_HTML


def test_ui_has_accessible_live_regions_and_microphone_label() -> None:
    assert '<label class="sr-only" for="device">Microphone</label>' in UI_HTML
    assert 'id="status" class="status" role="status" aria-live="polite"' in UI_HTML
    assert 'id="transcript" aria-live="polite" aria-atomic="false"' in UI_HTML
    assert 'id="error" class="error-text" role="alert"' in UI_HTML


def test_ui_microphone_select_can_shrink_on_narrow_screens() -> None:
    assert "select { min-width: 0; max-width: 100%" in UI_HTML
    assert "select { flex-basis: 100%; width: 100%; }" in UI_HTML
