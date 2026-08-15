import wave

import numpy as np

from meeting_notes.audio import iter_chunks, read_wav, save_wav_chunks


def test_iter_chunks_preserves_samples() -> None:
    audio = np.arange(10, dtype=np.float32)
    chunks = list(iter_chunks(audio, 4))
    assert [len(chunk) for chunk in chunks] == [4, 4, 2]
    np.testing.assert_array_equal(np.concatenate(chunks), audio)


def test_read_wav_downmixes_stereo(tmp_path) -> None:
    path = tmp_path / "input.wav"
    samples = np.array([[1000, -1000], [2000, 0]], dtype="<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(16_000)
        handle.writeframes(samples.tobytes())
    result = read_wav(path)
    np.testing.assert_allclose(result, [0.0, 1000 / 32768], atol=1e-6)


def test_save_wav_chunks_round_trips_audio(tmp_path) -> None:
    path = tmp_path / "recording.wav"
    chunks = [
        np.array([-1.0, -0.5, 0.0], dtype=np.float32),
        np.array([0.5, 1.0], dtype=np.float32),
    ]
    yielded = list(save_wav_chunks(iter(chunks), path, sample_rate=16_000))
    assert yielded == chunks
    np.testing.assert_allclose(read_wav(path), np.concatenate(chunks), atol=1 / 32768)
