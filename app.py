from fastapi import FastAPI, Form
from fastapi.responses import FileResponse
from pydub import AudioSegment
import edge_tts
import asyncio
import uuid
import os

app = FastAPI()


@app.get("/")
def home():
    return {
        "status": "SomaliTTS running"
    }


@app.post("/tts")
def generate(text: str = Form(...)):

    parts = [
        text[i:i+2500]
        for i in range(0, len(text), 2500)
    ]

    files = []

    async def create():
        for i, part in enumerate(parts):
            filename = f"/tmp/part_{i}.mp3"

            voice = edge_tts.Communicate(
                part,
                "so-SO-UbaxNeural"
            )

            await voice.save(filename)
            files.append(filename)

    asyncio.run(create())

    final_audio = AudioSegment.empty()

    for file in files:
        final_audio += AudioSegment.from_mp3(file)

    output = f"/tmp/{uuid.uuid4()}.mp3"

    final_audio.export(
        output,
        format="mp3"
    )

    return FileResponse(
        output,
        media_type="audio/mpeg",
        filename="somali_voice.mp3"
    )
