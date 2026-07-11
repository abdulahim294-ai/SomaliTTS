from fastapi import FastAPI, Form
from fastapi.responses import FileResponse
import uuid
import asyncio
import edge_tts

app = FastAPI()

@app.get("/")
def home():
    return {"status":"online"}

@app.post("/tts")
async def generate(text: str = Form(...)):
    filename = f"/tmp/{uuid.uuid4()}.mp3"

    communicate = edge_tts.Communicate(
        text,
        "ar-SA-HamedNeural"
    )

    await communicate.save(filename)

    return FileResponse(
        filename,
        media_type="audio/mpeg",
        filename="output.mp3"
    )
