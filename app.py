from fastapi import FastAPI, Form
from fastapi.responses import FileResponse
import edge_tts
import asyncio
import uuid
import os
from pydub import AudioSegment

app = FastAPI()

VOICE = "so-SO-UbaxNeural"
MAX_CHARS = 1000


@app.get("/")
def home():
    return {
        "status": "SomaliTTS running",
        "service": "online"
    }


def split_text(text, max_chars=MAX_CHARS):
    words = text.split()
    parts = []
    current = ""

    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current += (" " if current else "") + word
        else:
            parts.append(current)
            current = word

    if current:
        parts.append(current)

    return parts


async def generate_part(text, filename):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(filename)


@app.post("/tts")
def generate(text: str = Form(...)):
    parts = split_text(text)

    merged = AudioSegment.empty()

    for i, part in enumerate(parts):
        temp_file = f"/tmp/{uuid.uuid4()}_{i}.mp3"

        asyncio.run(generate_part(part, temp_file))

        merged += AudioSegment.from_mp3(temp_file)

        if os.path.exists(temp_file):
            os.remove(temp_file)

    output = f"/tmp/{uuid.uuid4()}.mp3"
    merged.export(output, format="mp3")

    return FileResponse(
        output,
        media_type="audio/mpeg",
        filename="output.mp3"
    )
