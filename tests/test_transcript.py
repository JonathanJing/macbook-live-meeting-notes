from meeting_notes.transcript import TranscriptStabilizer


def test_stabilizer_commits_only_new_cumulative_text() -> None:
    stabilizer = TranscriptStabilizer()
    assert stabilizer.update("Hello everyone") == "Hello everyone"
    assert stabilizer.commit() == "Hello everyone"
    assert stabilizer.update("Hello everyone We decided to ship Friday.") == (
        "We decided to ship Friday."
    )
    assert stabilizer.commit() == "We decided to ship Friday."
    assert stabilizer.committed == "Hello everyone We decided to ship Friday."


def test_stabilizer_tolerates_rewritten_hypothesis() -> None:
    stabilizer = TranscriptStabilizer()
    stabilizer.update("Hello world")
    stabilizer.commit()
    assert stabilizer.update("Hello Word") == "Hello Word"
