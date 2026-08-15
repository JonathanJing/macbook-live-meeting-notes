import numpy as np

from meeting_notes.endpoint import EndpointConfig, SilenceEndpoint


def test_endpoint_fires_after_speech_and_configured_silence() -> None:
    endpoint = SilenceEndpoint(
        EndpointConfig(
            sample_rate=1000,
            threshold_dbfs=-30,
            minimum_speech_ms=100,
            silence_ms=200,
        )
    )
    assert not endpoint.feed(np.full(100, 0.1, dtype=np.float32))
    assert not endpoint.feed(np.zeros(100, dtype=np.float32))
    assert endpoint.feed(np.zeros(100, dtype=np.float32))
    assert not endpoint.feed(np.zeros(300, dtype=np.float32))


def test_endpoint_ignores_short_noise() -> None:
    endpoint = SilenceEndpoint(
        EndpointConfig(sample_rate=1000, minimum_speech_ms=200, silence_ms=100)
    )
    assert not endpoint.feed(np.full(50, 0.2, dtype=np.float32))
    assert not endpoint.feed(np.zeros(200, dtype=np.float32))
