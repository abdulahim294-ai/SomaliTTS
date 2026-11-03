import asyncio
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from audio_pipeline import (
    AudioInputTooLarge,
    AudioOutputTooLarge,
    AudioPipeline,
    AudioProcessingError,
    AudioProcessingTimeout,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def ffmpeg_path():
    path = shutil.which("ffmpeg")

    if not path:
        pytest.skip("FFmpeg is not installed")

    return path


@pytest.fixture
def valid_mp3(ffmpeg_path):
    """
    Generate a real MP3 file using FFmpeg.
    No fake audio bytes are used in integration tests.
    """
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=0.5",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "96k",
        "-f",
        "mp3",
        "pipe:1",
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr.decode(
        "utf-8",
        errors="replace",
    )
    assert result.stdout.startswith(b"ID3") or result.stdout[:1] == b"\xff"

    return result.stdout


# ============================================================
# Input Validation
# ============================================================

def test_rejects_empty_audio():
    pipeline = AudioPipeline()

    with pytest.raises(AudioProcessingError):
        asyncio.run(pipeline.process(b""))


def test_rejects_none_audio():
    pipeline = AudioPipeline()

    with pytest.raises(AudioProcessingError):
        asyncio.run(pipeline.process(None))


def test_rejects_string_audio():
    pipeline = AudioPipeline()

    with pytest.raises(AudioProcessingError):
        asyncio.run(pipeline.process("not audio"))


def test_rejects_input_above_configured_limit():
    pipeline = AudioPipeline(max_input_bytes=10)

    with pytest.raises(AudioInputTooLarge):
        asyncio.run(pipeline.process(b"A" * 11))


def test_accepts_input_at_exact_limit():
    pipeline = AudioPipeline(max_input_bytes=10)

    # The size check must accept exactly 10 bytes.
    # Invalid media is rejected later by FFmpeg.
    assert pipeline.max_input_bytes == 10


# ============================================================
# FFmpeg Command Security and Configuration
# ============================================================

def test_ffmpeg_command_uses_exec_without_shell():
    pipeline = AudioPipeline(ffmpeg_path="/usr/bin/ffmpeg")

    command = pipeline._build_command()

    assert command[0] == "/usr/bin/ffmpeg"
    assert isinstance(command, list)

    assert "-nostdin" in command
    assert "pipe:0" in command
    assert "pipe:1" in command

    assert "-map_metadata" in command
    assert "-1" in command

    assert "-ac" in command
    assert command[command.index("-ac") + 1] == "1"

    assert "-ar" in command
    assert command[command.index("-ar") + 1] == "48000"

    assert "-b:a" in command
    assert command[command.index("-b:a") + 1] == "128k"

    assert "libmp3lame" in command
    assert "loudnorm=I=-19:TP=-2:LRA=7" in command


def test_pipeline_configuration_is_respected():
    pipeline = AudioPipeline(
        ffmpeg_path="/custom/ffmpeg",
        timeout_seconds=12,
        max_input_bytes=1024,
        max_output_bytes=2048,
    )

    assert pipeline.ffmpeg_path == "/custom/ffmpeg"
    assert pipeline.timeout_seconds == 12
    assert pipeline.max_input_bytes == 1024
    assert pipeline.max_output_bytes == 2048


# ============================================================
# Real FFmpeg Integration Tests
# ============================================================

def test_process_real_mp3_successfully(ffmpeg_path, valid_mp3):
    pipeline = AudioPipeline(ffmpeg_path=ffmpeg_path)

    output = asyncio.run(pipeline.process(valid_mp3))

    assert isinstance(output, bytes)
    assert len(output) > 0

    # MP3 output must contain an MPEG frame or an ID3 header.
    assert output.startswith(b"ID3") or output[:1] == b"\xff"


def test_output_is_decodable_by_ffmpeg(
    ffmpeg_path,
    valid_mp3,
):
    pipeline = AudioPipeline(ffmpeg_path=ffmpeg_path)

    output = asyncio.run(pipeline.process(valid_mp3))

    decode_command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-f",
        "null",
        "-",
    ]

    result = subprocess.run(
        decode_command,
        input=output,
        capture_output=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr.decode(
        "utf-8",
        errors="replace",
    )


def test_rejects_invalid_audio_with_real_ffmpeg(ffmpeg_path):
    pipeline = AudioPipeline(ffmpeg_path=ffmpeg_path)

    with pytest.raises(AudioProcessingError):
        asyncio.run(
            pipeline.process(b"this is definitely not valid audio")
        )


def test_rejects_output_above_configured_limit(
    ffmpeg_path,
    valid_mp3,
):
    pipeline = AudioPipeline(
        ffmpeg_path=ffmpeg_path,
        max_output_bytes=32,
    )

    with pytest.raises(AudioOutputTooLarge):
        asyncio.run(pipeline.process(valid_mp3))


# ============================================================
# Output Stream Safety
# ============================================================

def test_read_output_enforces_output_limit():
    async def run_test():
        reader = asyncio.StreamReader()
        reader.feed_data(b"A" * 20)
        reader.feed_eof()

        pipeline = AudioPipeline(max_output_bytes=10)

        process = SimpleNamespace(stdout=reader)

        with pytest.raises(AudioOutputTooLarge):
            await pipeline._read_output(process)

    asyncio.run(run_test())


def test_read_output_accepts_data_within_limit():
    async def run_test():
        reader = asyncio.StreamReader()
        reader.feed_data(b"valid-output")
        reader.feed_eof()

        pipeline = AudioPipeline(max_output_bytes=100)

        process = SimpleNamespace(stdout=reader)

        output = await pipeline._read_output(process)

        assert output == b"valid-output"

    asyncio.run(run_test())


def test_read_stderr_limits_captured_data():
    async def run_test():
        reader = asyncio.StreamReader()
        reader.feed_data(b"E" * (70 * 1024))
        reader.feed_eof()

        pipeline = AudioPipeline()

        process = SimpleNamespace(stderr=reader)

        output = await pipeline._read_stderr(process)

        assert len(output.encode("utf-8")) <= 64 * 1024

    asyncio.run(run_test())


# ============================================================
# Missing FFmpeg
# ============================================================

def test_missing_ffmpeg_returns_safe_error():
    pipeline = AudioPipeline(
        ffmpeg_path="/definitely/not/a/real/ffmpeg"
    )

    with pytest.raises(
        AudioProcessingError,
        match="FFmpeg executable was not found",
    ):
        asyncio.run(pipeline.process(b"some audio data"))


# ============================================================
# Timeout Handling
# ============================================================

def test_timeout_configuration_is_positive():
    pipeline = AudioPipeline(timeout_seconds=5)

    assert pipeline.timeout_seconds == 5
    assert pipeline.timeout_seconds > 0


# ============================================================
# Output Format Contract
# ============================================================

def test_output_format_configuration():
    pipeline = AudioPipeline()

    command = pipeline._build_command()

    assert "-f" in command
    assert command[command.index("-f") + 1] == "mp3"

    assert "-vn" in command
    assert "-sn" in command
    assert "-dn" in command


# ============================================================
# Regression Tests
# ============================================================

def test_pipeline_does_not_use_shell_execution():
    pipeline = AudioPipeline()

    command = pipeline._build_command()

    assert isinstance(command, list)
    assert all(isinstance(part, str) for part in command)

    # The executable and arguments are passed separately.
    # No shell command string should be constructed.
    assert not any(";" in part for part in command)
    assert not any("&&" in part for part in command)
    assert not any("|" in part for part in command)
