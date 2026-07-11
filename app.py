@app.post("/tts")
def generate(text: str = Form(...)):
    import uuid
    from pydub import AudioSegment
    import edge_tts
    import asyncio
    import os

    parts = [text[i:i+2500] for i in range(0, len(text), 2500)]

    output_files = []

    async def create_audio():
        for i, part in enumerate(parts):
            filename = f"/tmp/part_{i}.mp3"

            communicate = edge_tts.Communicate(
                part,
                "so-SO-UbaxNeural"
            )

            await communicate.save(filename)
            output_files.append(filename)

    asyncio.run(create_audio())

    final = AudioSegment.empty()

    for f in output_files:
        final += AudioSegment.from_mp3(f)

    result = f"/tmp/{uuid.uuid4()}.mp3"
    final.export(result, format="mp3")

    return FileResponse(
        result,
        media_type="audio/mpeg",
        filename="somali_voice.mp3"
    )
