import os
import secrets
import subprocess
import tempfile
import threading
from pathlib import Path

import torch
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from transformers import AutoModel

MODEL_ID = os.getenv("HUBI_MODEL_ID", "ayeeyokoris/hubi-tts")
MODEL_REVISION = os.getenv("HUBI_MODEL_REVISION", "main")
API_TOKEN = os.getenv("HUBI_API_TOKEN", "")
MAX_UPLOAD_BYTES = int(os.getenv("HUBI_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

if not API_TOKEN:
    raise RuntimeError("HUBI_API_TOKEN must be set to a long random secret")

app = FastAPI(title="SomaliTTS Hubi inference", version="0.1.0")
model = None
model_lock = threading.Lock()
workdir = Path(os.getenv("HUBI_WORKDIR", "/tmp/hubi"))
workdir.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
def load_model():
    global model
    # Hubi currently publishes custom Transformers code. Pin HUBI_MODEL_REVISION
    # before production use and review that code before enabling trust_remote_code.
    model = AutoModel.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
        trust_remote_code=True,
    ).to(DEVICE)
    model.eval()


def require_token(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="unauthorized")
    supplied = authorization[7:]
    if not secrets.compare_digest(supplied, API_TOKEN):
        raise HTTPException(status_code=401, detail="unauthorized")


def convert_reference(source: Path, target: Path):
    # ffmpeg normalizes common browser uploads (webm/mp3/m4a/ogg/wav) to mono WAV.
    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(source),
         "-ac", "1", "-ar", "16000", str(target)],
        capture_output=True, timeout=60,
    )
    if result.returncode != 0 or not target.exists() or target.stat().st_size < 1024:
        raise HTTPException(status_code=422, detail="invalid_reference_audio")


async def save_upload(upload: UploadFile, folder: Path) -> Path:
    suffix = Path(upload.filename or "reference.bin").suffix[:10] or ".bin"
    source = folder / f"reference{suffix}"
    total = 0
    with source.open("wb") as out:
        while chunk := await upload.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                source.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="reference_too_large")
            out.write(chunk)
    if total < 1024:
        source.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="reference_audio_empty")
    normalized = folder / "reference.wav"
    convert_reference(source, normalized)
    return normalized


@app.get("/health")
def health():
    return {"ready": model is not None, "model": MODEL_ID, "device": DEVICE}


@app.post("/prepare")
async def prepare(
    authorization: str | None = Header(default=None),
    voice_id: str = Form(...),
    language: str = Form("so"),
    reference_audio: UploadFile = File(...),
):
    require_token(authorization)
    if language != "so":
        raise HTTPException(status_code=422, detail="unsupported_language")
    folder = Path(tempfile.mkdtemp(prefix="prepare-", dir=workdir))
    try:
        reference = await save_upload(reference_audio, folder)
        probe = folder / "probe.wav"
        # This is a real short inference, not a placeholder status.
        with model_lock:
            model.tts("Salaam.", prompt_audio=str(reference), save_path=str(probe))
        if not probe.exists() or probe.stat().st_size < 1024:
            raise HTTPException(status_code=503, detail="voice_probe_failed")
        return {"voice_id": voice_id, "ready": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"inference_failed: {type(exc).__name__}")
    finally:
        for item in folder.glob("*"):
            item.unlink(missing_ok=True)
        folder.rmdir()


@app.post("/tts")
async def synthesize(
    authorization: str | None = Header(default=None),
    text: str = Form(...),
    voice_id: str = Form(...),
    language: str = Form("so"),
    reference_audio: UploadFile = File(...),
):
    require_token(authorization)
    if language != "so":
        raise HTTPException(status_code=422, detail="unsupported_language")
    text = text.strip()
    if not text or len(text) > 100_000:
        raise HTTPException(status_code=422, detail="invalid_text")
    folder = Path(tempfile.mkdtemp(prefix="tts-", dir=workdir))
    try:
        reference = await save_upload(reference_audio, folder)
        output = folder / "generated.wav"
        with model_lock:
            model.tts(text, prompt_audio=str(reference), save_path=str(output))
        if not output.exists() or output.stat().st_size < 1024:
            raise HTTPException(status_code=503, detail="empty_generation")
        return FileResponse(
            output,
            media_type="audio/wav",
            filename="somali_voice.wav",
            background=BackgroundTask(lambda: __import__("shutil").rmtree(folder, ignore_errors=True)),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"inference_failed: {type(exc).__name__}")
