from fastapi import FastAPI, Form
from fastapi.responses import FileResponse
import uuid
import os

app = FastAPI()

tts = None


@app.get("/")
def home():
    return {
        "status": "SomaliTTS running",
        "service": "online"
    }


@app.post("/tts")
def generate(text: str = Form(...)):
    global tts

    if tts is None:
        from TTS.api import TTS
        tts = TTS(
            "tts_models/multilingual/multi-dataset/xtts_v2",
            gpu=False
        )

    filename = f"/tmp/{uuid.uuid4()}.wav"

    tts.tts_to_file(
        text=text,
        file_path=filename,
        language="en"
    )

    return FileResponse(
        filename,
        media_type="audio/wav",
        filename="output.wav"
    )
