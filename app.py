from fastapi import FastAPI, Form
from fastapi.responses import FileResponse
from TTS.api import TTS
import uuid

app = FastAPI()

tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

@app.get("/")
def home():
    return {"status": "SomaliTTS running"}

@app.post("/tts")
def generate(text: str = Form(...)):

    filename = f"{uuid.uuid4()}.wav"

    tts.tts_to_file(
        text=text,
        file_path=filename
    )

    return FileResponse(
        filename,
        media_type="audio/wav",
        filename="somali_voice.wav"
    )
