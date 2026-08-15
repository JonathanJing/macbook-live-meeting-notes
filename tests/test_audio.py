import wave

import numpy as np

from meeting_notes.audio import iter_chunks, read_wav


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
