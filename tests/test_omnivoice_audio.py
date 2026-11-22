import io
import wave

import numpy as np
import pytest

from app import _omnivoice_audio_to_wav


def test_omnivoice_numpy_audio_is_encoded_as_playable_wav():
    samples = np.array([0.0, 0.5, -0.5, 1.0], dtype=np.float32)

    output = _omnivoice_audio_to_wav((24000, samples))

    with wave.open(io.BytesIO(output), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getframerate() == 24000
        assert audio.getnframes() == 4
        assert audio.readframes(4)


def test_omnivoice_stereo_audio_is_downmixed_to_mono():
    samples = np.array(
        [[0.1, 0.2], [0.3, 0.4], [-0.2, -0.1]],
        dtype=np.float32,
    )

    output = _omnivoice_audio_to_wav((22050, samples))

    with wave.open(io.BytesIO(output), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getframerate() == 22050
        assert audio.getnframes() == 3


def test_omnivoice_rejects_empty_audio():
    with pytest.raises(RuntimeError, match="empty audio"):
        _omnivoice_audio_to_wav((24000, np.array([], dtype=np.float32)))
