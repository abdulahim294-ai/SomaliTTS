from fastapi import FastAPI, Form
from fastapi.responses import FileResponse

app = FastAPI()

@app.get("/")
def home():
    return {"status": "SomaliTTS running"}

@app.post("/tts")
def tts(text: str = Form(...)):
    return {
        "message": "Received text",
        "length": len(text)
    }
