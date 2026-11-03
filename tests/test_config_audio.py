import pytest

from config import load_settings


# ============================================================
# FFmpeg Default Configuration
# ============================================================

def test_ffmpeg_default_settings():
    settings = load_settings({})

    assert settings.ffmpeg_path == "ffmpeg"
    assert settings.ffmpeg_timeout_seconds == 90

    assert settings.max_audio_input_bytes == (
        25 * 1024 * 1024
    )

    assert settings.max_audio_output_bytes == (
        50 * 1024 * 1024
    )


# ============================================================
# Custom Configuration
# ============================================================

def test_ffmpeg_custom_settings():
    settings = load_settings({
        "FFMPEG_PATH": "/usr/local/bin/ffmpeg",
        "FFMPEG_TIMEOUT_SECONDS": "120",
        "MAX_AUDIO_INPUT_BYTES": "10485760",
        "MAX_AUDIO_OUTPUT_BYTES": "20971520",
    })

    assert settings.ffmpeg_path == "/usr/local/bin/ffmpeg"
    assert settings.ffmpeg_timeout_seconds == 120

    assert settings.max_audio_input_bytes == 10 * 1024 * 1024
    assert settings.max_audio_output_bytes == 20 * 1024 * 1024


# ============================================================
# Invalid Configuration
# ============================================================

def test_ffmpeg_invalid_numeric_settings_use_defaults():
    settings = load_settings({
        "FFMPEG_TIMEOUT_SECONDS": "invalid",
        "MAX_AUDIO_INPUT_BYTES": "invalid",
        "MAX_AUDIO_OUTPUT_BYTES": "invalid",
    })

    assert settings.ffmpeg_timeout_seconds == 90

    assert settings.max_audio_input_bytes == (
        25 * 1024 * 1024
    )

    assert settings.max_audio_output_bytes == (
        50 * 1024 * 1024
    )


def test_ffmpeg_nan_and_infinite_timeout_use_default():
    for value in ("nan", "inf", "-inf"):
        settings = load_settings({
            "FFMPEG_TIMEOUT_SECONDS": value,
        })

        assert settings.ffmpeg_timeout_seconds == 90


# ============================================================
# Timeout Boundaries
# ============================================================

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", 5),
        ("4", 5),
        ("5", 5),
        ("90", 90),
        ("300", 300),
        ("301", 300),
        ("9999", 300),
    ],
)
def test_ffmpeg_timeout_is_bounded(value, expected):
    settings = load_settings({
        "FFMPEG_TIMEOUT_SECONDS": value,
    })

    assert settings.ffmpeg_timeout_seconds == expected


# ============================================================
# Input Size Boundaries
# ============================================================

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", 1024),
        ("512", 1024),
        ("1024", 1024),
        ("10485760", 10 * 1024 * 1024),
        ("104857600", 100 * 1024 * 1024),
        ("200000000", 100 * 1024 * 1024),
    ],
)
def test_audio_input_size_is_bounded(value, expected):
    settings = load_settings({
        "MAX_AUDIO_INPUT_BYTES": value,
    })

    assert settings.max_audio_input_bytes == expected


# ============================================================
# Output Size Boundaries
# ============================================================

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", 1024),
        ("512", 1024),
        ("1024", 1024),
        ("20971520", 20 * 1024 * 1024),
        ("157286400", 150 * 1024 * 1024),
        ("200000000", 150 * 1024 * 1024),
    ],
)
def test_audio_output_size_is_bounded(value, expected):
    settings = load_settings({
        "MAX_AUDIO_OUTPUT_BYTES": value,
    })

    assert settings.max_audio_output_bytes == expected


# ============================================================
# FFmpeg Executable Path
# ============================================================

def test_ffmpeg_path_is_trimmed():
    settings = load_settings({
        "FFMPEG_PATH": "  /usr/bin/ffmpeg  ",
    })

    assert settings.ffmpeg_path == "/usr/bin/ffmpeg"


def test_empty_ffmpeg_path_uses_default():
    settings = load_settings({
        "FFMPEG_PATH": "   ",
    })

    assert settings.ffmpeg_path == "ffmpeg"


# ============================================================
# Configuration Immutability
# ============================================================

def test_settings_are_immutable():
    settings = load_settings({})

    with pytest.raises(AttributeError):
        settings.ffmpeg_path = "/tmp/another-ffmpeg"
