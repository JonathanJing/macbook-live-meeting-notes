from meeting_notes.notes import ExtractiveNoteGenerator


def test_extractive_notes_keep_decisions_actions_and_questions() -> None:
    transcript = (
        "Welcome to the meeting. We decided to ship on Friday. "
        "Alice will prepare the release. What remains blocked?"
    )
    notes = ExtractiveNoteGenerator().generate(transcript)
    assert "We decided to ship on Friday." in notes
    assert "Alice will prepare the release." in notes
    assert "What remains blocked?" in notes
    assert "Review against the transcript" in notes


def test_extractive_notes_do_not_invent_missing_items() -> None:
    notes = ExtractiveNoteGenerator().generate("A short status update.")
    assert "None detected." in notes
    assert "Owners and dates require review." in notes
