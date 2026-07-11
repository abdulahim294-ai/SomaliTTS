from fastapi import FastAPI, Form
from fastapi.responses import FileResponse
from pydub import AudioSegment
import edge_tts
import asyncio
import uuid

app = FastAPI()


@app.get("/")
def home():
    return {
        "status": "SomaliTTS running"
    }


@app.post("/tts")
def generate(
    text: str = Form(...),
    gender: str = Form("male")
):

    if gender == "female":
        voice = "so-SO-deeroow"
    else:
        voice = "so-SO-maxamed"


    parts = [
        text[i:i+2500]
        for i in range(0, len(text), 2500)
    ]

    files = []


    async def create_audio():

        for i, part in enumerate(parts):

            filename = f"/tmp/part_{i}.mp3"

            communicate = edge_tts.Communicate(
                part,
                voice
            )

            await communicate.save(filename)

            files.append(filename)


    asyncio.run(create_audio())


    final_audio = AudioSegment.empty()

    for f in files:
        final_audio += AudioSegment.from_mp3(f)


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
