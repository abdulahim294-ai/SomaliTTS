import asyncio
import logging
from typing import Optional

from config import SETTINGS


logger = logging.getLogger("somalitts.audio")

DEFAULT_FFMPEG_PATH = "ffmpeg"
DEFAULT_TIMEOUT_SECONDS = 90
DEFAULT_MAX_INPUT_BYTES = 25 * 1024 * 1024
DEFAULT_MAX_OUTPUT_BYTES = 50 * 1024 * 1024
MAX_STDERR_BYTES = 64 * 1024


class AudioProcessingError(Exception):
    """Raised when audio processing fails safely."""


class AudioInputTooLarge(AudioProcessingError):
    """Raised when input audio exceeds the configured limit."""


class AudioOutputTooLarge(AudioProcessingError):
    """Raised when FFmpeg output exceeds the configured limit."""


class AudioProcessingTimeout(AudioProcessingError):
    """Raised when FFmpeg exceeds its execution deadline."""


class AudioPipeline:
    """
    Converts synthesized audio into normalized MP3.

    Processing:
    - Decode the input audio.
    - Remove embedded metadata.
    - Convert to mono.
    - Resample to 48 kHz.
    - Normalize loudness.
    - Encode MP3 at 128 kbps.

    Uses FFmpeg through asyncio subprocess pipes.
    No temporary files or shell execution are used.
    """

    def __init__(
        self,
        ffmpeg_path: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_input_bytes: Optional[int] = None,
        max_output_bytes: Optional[int] = None,
    ):
        self.ffmpeg_path = (
            ffmpeg_path
            or getattr(SETTINGS, "ffmpeg_path", DEFAULT_FFMPEG_PATH)
        )

        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else getattr(
                SETTINGS,
                "ffmpeg_timeout_seconds",
                DEFAULT_TIMEOUT_SECONDS,
            )
        )

        self.max_input_bytes = (
            max_input_bytes
            if max_input_bytes is not None
            else getattr(
                SETTINGS,
                "max_audio_input_bytes",
                DEFAULT_MAX_INPUT_BYTES,
            )
        )

        self.max_output_bytes = (
            max_output_bytes
            if max_output_bytes is not None
            else getattr(
                SETTINGS,
                "max_audio_output_bytes",
                DEFAULT_MAX_OUTPUT_BYTES,
            )
        )

    def _build_command(self) -> list[str]:
        return [
            self.ffmpeg_path,
            "-hide_banner",
            "-loglevel", "error",
            "-nostdin",
            "-i", "pipe:0",
            "-map", "0:a:0",
            "-map_metadata", "-1",
            "-vn",
            "-sn",
            "-dn",
            "-ac", "1",
            "-ar", "48000",
            "-af", "loudnorm=I=-19:TP=-2:LRA=7",
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            "-f", "mp3",
            "pipe:1",
        ]

    async def _terminate(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return

        process.kill()

        try:
            await asyncio.wait_for(process.wait(), timeout=3)
        except asyncio.TimeoutError:
            logger.error("FFmpeg process did not exit after termination")

    async def _write_input(
        self,
        process: asyncio.subprocess.Process,
        audio: bytes,
    ) -> None:
        if process.stdin is None:
            raise AudioProcessingError("FFmpeg input pipe is unavailable")

        try:
            process.stdin.write(audio)
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            # FFmpeg may close stdin early when it rejects the input.
            pass
        finally:
            process.stdin.close()

            try:
                await process.stdin.wait_closed()
            except (BrokenPipeError, ConnectionResetError):
                pass

    async def _read_output(
        self,
        process: asyncio.subprocess.Process,
    ) -> bytes:
        if process.stdout is None:
            raise AudioProcessingError("FFmpeg output pipe is unavailable")

        output = bytearray()

        while True:
            chunk = await process.stdout.read(64 * 1024)

            if not chunk:
                break

            if len(output) + len(chunk) > self.max_output_bytes:
                raise AudioOutputTooLarge(
                    "Processed audio exceeds the configured output limit"
                )

            output.extend(chunk)

        return bytes(output)

    async def _read_stderr(
        self,
        process: asyncio.subprocess.Process,
    ) -> str:
        if process.stderr is None:
            return ""

        captured = bytearray()

        while True:
            chunk = await process.stderr.read(8192)

            if not chunk:
                break

            remaining = MAX_STDERR_BYTES - len(captured)

            if remaining > 0:
                captured.extend(chunk[:remaining])

        return captured.decode("utf-8", errors="replace")

    async def process(self, audio: bytes) -> bytes:
        """
        Process synthesized audio and return a normalized MP3 file.
        """

        if not isinstance(audio, bytes) or not audio:
            raise AudioProcessingError("Input audio is empty or invalid")

        if len(audio) > self.max_input_bytes:
            raise AudioInputTooLarge(
                "Input audio exceeds the configured input limit"
            )

        process = None
        tasks = []

        try:
            process = await asyncio.create_subprocess_exec(
                *self._build_command(),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            writer_task = asyncio.create_task(
                self._write_input(process, audio)
            )

            output_task = asyncio.create_task(
                self._read_output(process)
            )

            stderr_task = asyncio.create_task(
                self._read_stderr(process)
            )

            wait_task = asyncio.create_task(process.wait())

            tasks = [
                writer_task,
                output_task,
                stderr_task,
                wait_task,
            ]

            output, stderr, return_code = await asyncio.wait_for(
                asyncio.gather(
                    writer_task,
                    output_task,
                    stderr_task,
                    wait_task,
                ),
                timeout=self.timeout_seconds,
            )

            if return_code != 0:
                logger.warning(
                    "FFmpeg failed with exit code %s: %s",
                    return_code,
                    stderr[:1000],
                )

                raise AudioProcessingError(
                    "FFmpeg could not process the generated audio"
                )

            if not output:
                raise AudioProcessingError(
                    "FFmpeg returned empty audio"
                )

            return output

        except asyncio.TimeoutError as exc:
            if process is not None:
                await self._terminate(process)

            raise AudioProcessingTimeout(
                "Audio processing exceeded its time limit"
            ) from exc

        except FileNotFoundError as exc:
            raise AudioProcessingError(
                "FFmpeg executable was not found"
            ) from exc

        except asyncio.CancelledError:
            if process is not None:
                await self._terminate(process)

            raise

        except AudioProcessingError:
            if process is not None:
                await self._terminate(process)

            raise

        except Exception as exc:
            if process is not None:
                await self._terminate(process)

            logger.exception("Unexpected audio processing failure")

            raise AudioProcessingError(
                "Unexpected audio processing failure"
            ) from exc

        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
