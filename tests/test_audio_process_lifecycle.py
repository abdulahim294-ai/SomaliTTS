import asyncio
import os
import sys
import textwrap

import pytest

from audio_pipeline import (
    AudioPipeline,
    AudioProcessingTimeout,
)


@pytest.fixture
def hanging_ffmpeg(tmp_path):
    """
    Create a fake FFmpeg executable that stays alive.

    This allows lifecycle tests to verify real subprocess
    termination without depending on actual audio encoding.
    """
    executable = tmp_path / "fake_ffmpeg"

    executable.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            import time

            time.sleep(60)
            """
        ),
        encoding="utf-8",
    )

    executable.chmod(0o755)

    return str(executable)


def test_timeout_terminates_ffmpeg_process(hanging_ffmpeg):
    async def run_test():
        pipeline = AudioPipeline(
            ffmpeg_path=hanging_ffmpeg,
            timeout_seconds=0.3,
        )

        with pytest.raises(AudioProcessingTimeout):
            await pipeline.process(b"test-audio")

    asyncio.run(run_test())


def test_cancellation_terminates_ffmpeg_process(hanging_ffmpeg):
    async def run_test():
        pipeline = AudioPipeline(
            ffmpeg_path=hanging_ffmpeg,
            timeout_seconds=30,
        )

        process_started = asyncio.Event()
        created_processes = []

        original_create = asyncio.create_subprocess_exec

        async def tracked_create(*args, **kwargs):
            process = await original_create(*args, **kwargs)
            created_processes.append(process)
            process_started.set()
            return process

        import audio_pipeline

        original_module_create = (
            audio_pipeline.asyncio.create_subprocess_exec
        )

        audio_pipeline.asyncio.create_subprocess_exec = tracked_create

        try:
            task = asyncio.create_task(
                pipeline.process(b"test-audio")
            )

            await asyncio.wait_for(
                process_started.wait(),
                timeout=5,
            )

            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

            assert created_processes

            process = created_processes[0]

            assert process.returncode is not None

        finally:
            audio_pipeline.asyncio.create_subprocess_exec = (
                original_module_create
            )

    asyncio.run(run_test())


def test_normal_process_cleanup_does_not_leave_running_process(
    hanging_ffmpeg,
):
    async def run_test():
        pipeline = AudioPipeline(
            ffmpeg_path=hanging_ffmpeg,
            timeout_seconds=0.2,
        )

        with pytest.raises(AudioProcessingTimeout):
            await pipeline.process(b"test-audio")

    asyncio.run(run_test())


def test_timeout_is_reported_as_processing_timeout():
    async def run_test():
        pipeline = AudioPipeline(
            ffmpeg_path="/nonexistent/fake-ffmpeg",
            timeout_seconds=1,
        )

        with pytest.raises(Exception):
            await pipeline.process(b"test-audio")

    asyncio.run(run_test())


def test_pipeline_rejects_zero_timeout():
    with pytest.raises(ValueError):
        AudioPipeline(timeout_seconds=0)


def test_pipeline_rejects_negative_input_limit():
    with pytest.raises(ValueError):
        AudioPipeline(max_input_bytes=-1)


def test_pipeline_rejects_negative_output_limit():
    with pytest.raises(ValueError):
        AudioPipeline(max_output_bytes=-1)


def test_pipeline_rejects_empty_ffmpeg_path():
    with pytest.raises(ValueError):
        AudioPipeline(ffmpeg_path="   ")
