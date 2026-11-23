import asyncio
import io
import re
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path

import edge_tts
import gradio as gr
import numpy as np
from gradio_client import Client, handle_file

TMP = Path(tempfile.gettempdir()) / "somalitts-studio"
TMP.mkdir(parents=True, exist_ok=True)
MAX_AUDIO = 8 * 1024 * 1024
MAX_CLONE_TEXT = 12000
MAX_TTS_TEXT = 100000
ALLOWED = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}

CSS = r"""
:root{--bg:#07111f;--panel:rgba(15,32,53,.84);--line:rgba(132,177,220,.18);--ink:#eaf4ff}
.gradio-container{max-width:1180px!important;margin:auto!important;background:radial-gradient(ellipse at 12% 0%,#12345a 0,transparent 38%),radial-gradient(ellipse at 90% 15%,#0b4650 0,transparent 30%),var(--bg)!important;color:var(--ink)!important;font-family:system-ui,"Segoe UI",sans-serif!important}
footer{display:none!important}#hero{border:1px solid var(--line);border-radius:25px;padding:26px 30px;background:linear-gradient(125deg,rgba(21,52,84,.9),rgba(10,37,52,.75));box-shadow:0 18px 60px #0003;margin-bottom:18px}
#hero h1{font-size:clamp(30px,5vw,48px);line-height:1.25;margin:5px 0 9px;color:#f3f8ff}
#hero p{color:#b5c8dc;font-size:14px;line-height:1.9;margin:0}.kicker{color:#79d9e9;font-size:12px;font-weight:800;letter-spacing:1.2px}
.gradio-container .tab-nav{border:1px solid var(--line)!important;background:#0c1b2c!important;border-radius:16px!important;padding:5px!important}
.gradio-container .tab-nav button{border-radius:11px!important;color:#b9cce0!important}.gradio-container .tab-nav button.selected{background:linear-gradient(110deg,#1766ad,#087f91)!important;color:white!important}
.gradio-container .block,.gradio-container .form{background:var(--panel)!important;border:1px solid var(--line)!important;border-radius:18px!important}
.gradio-container input,.gradio-container textarea,.gradio-container select{background:#091827!important;color:#edf6ff!important;border-color:#29435e!important}
.gradio-container textarea{line-height:1.9!important}.gradio-container button.primary{background:linear-gradient(105deg,#287be0,#087f91)!important;border:0!important;color:white!important;font-weight:800!important;border-radius:13px!important;min-height:48px}
.gradio-container button.secondary{border:1px solid #355775!important;background:#132a41!important;color:#dcecff!important;border-radius:12px!important}
#notice{border:1px solid #2b536e;background:#0b2031;border-radius:15px;padding:12px 16px;color:#b9d4eb;font-size:12px;line-height:1.9}
#foot{color:#7892ac;text-align:center;font-size:11px;padding:12px}
@media(max-width:650px){#hero{padding:20px 17px;border-radius:18px}.gradio-container{padding-left:8px!important;padding-right:8px!important}}
"""

def split_text(text, limit=2600):
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return [text]
    sentences = re.split(r"(?<=[.!?؟۔])\s+", text)
    chunks, current = [], ""
    for sentence in sentences:
        while len(sentence) > limit:
            if current:
                chunks.append(current)
                current = ""
            cut = sentence.rfind(" ", 0, limit)
            if cut < limit // 2:
                cut = limit
            chunks.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        candidate = (current + " " + sentence).strip()
        if len(candidate) > limit and current:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return [c for c in chunks if c]

def combine_mp3(files, output):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        with open(output, "wb") as target:
            for item in files:
                target.write(Path(item).read_bytes())
        return output
    listing = TMP / f"concat-{time.time_ns()}.txt"
    listing.write_text("".join(f"file '{Path(p).as_posix()}'\n" for p in files), encoding="utf-8")
    run = subprocess.run([ffmpeg,"-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(listing),"-vn","-af","loudnorm=I=-16:TP=-1.5:LRA=11","-ar","48000","-ac","1","-b:a","128k",output],capture_output=True,timeout=180)
    listing.unlink(missing_ok=True)
    if run.returncode:
        raise RuntimeError("تعذرت معالجة ملف MP3 النهائي. أعد المحاولة بنص أقصر.")
    return output

async def create_tts(text, gender):
    text = (text or "").strip()
    if not text:
        raise gr.Error("اكتب النص الصومالي أولاً.")
    if len(text) > MAX_TTS_TEXT:
        raise gr.Error("الحد الأقصى 100,000 حرف.")
    voice = "so-SO-MuuseNeural" if gender == "male" else "so-SO-UbaxNeural"
    chunks = split_text(text)
    job = TMP / f"tts-{time.time_ns()}"
    job.mkdir(parents=True, exist_ok=True)
    files = []
    try:
        for index, chunk in enumerate(chunks, 1):
            path = job / f"part-{index:03d}.mp3"
            await edge_tts.Communicate(chunk, voice=voice).save(str(path))
            if not path.exists() or path.stat().st_size < 500:
                raise gr.Error("لم يُرجع محرك الصوت ملفاً صالحاً. حاول مرة أخرى.")
            files.append(str(path))
        output = str(job / "somalitts-voice.mp3")
        combine_mp3(files, output)
        return output, f"اكتمل إنشاء الصوت — {len(chunks)} مقطع، بصوت {'Muuse' if gender == 'male' else 'Ubax'}."
    except gr.Error:
        raise
    except Exception as exc:
        raise gr.Error(f"تعذر إنشاء الصوت: {str(exc)[:220]}") from exc

def audio_to_wav(result):
    if isinstance(result, dict):
        path = result.get("path") or result.get("name")
        if path and Path(path).is_file():
            return Path(path).read_bytes()
    if isinstance(result, (tuple, list)) and len(result) == 2 and isinstance(result[0], (int, float)):
        rate, samples = result
        if not isinstance(samples, np.ndarray) or samples.size == 0:
            raise RuntimeError("OmniVoice returned empty audio")
        samples = np.asarray(samples)
        if samples.ndim == 2:
            if samples.shape[0] <= 2 and samples.shape[1] > 2:
                samples = samples.T
            samples = samples.mean(axis=1)
        if samples.ndim != 1:
            raise RuntimeError("Unsupported audio shape")
        if np.issubdtype(samples.dtype, np.integer):
            pcm = np.clip(samples, -32768, 32767).astype(np.int16)
        else:
            pcm = (np.clip(np.nan_to_num(samples.astype(np.float32)), -1, 1) * 32767).astype(np.int16)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(int(rate)); wav.writeframes(pcm.tobytes())
        return buffer.getvalue()
    raise RuntimeError("OmniVoice returned an unsupported audio format")

def clone_voice(text, reference_text, audio_path, style, emotion, extra, request: gr.Request):
    text = (text or "").strip()
    reference_text = (reference_text or "").strip()
    if not text:
        raise gr.Error("اكتب النص الذي تريد توليده.")
    if len(text) > MAX_CLONE_TEXT:
        raise gr.Error("الحد الأقصى للنص 12,000 حرف.")
    if not reference_text:
        raise gr.Error("اكتب الكلام المطابق للتسجيل الصوتي.")
    if not audio_path or not Path(audio_path).is_file():
        raise gr.Error("ارفع تسجيلاً واضحاً أو سجّل صوتك.")
    path = Path(audio_path)
    if path.suffix.lower() not in ALLOWED:
        raise gr.Error("صيغة الملف غير مدعومة. استخدم WAV أو MP3 أو M4A أو FLAC أو OGG أو WEBM.")
    if path.stat().st_size > MAX_AUDIO:
        raise gr.Error("حجم العينة يجب ألا يتجاوز 8 ميجابايت.")
    presets = {
        "طبيعي وواضح": "",
        "حماسي وجذاب": "Speak in an energetic, engaging Somali narration style.",
        "سرد قصصي": "Use expressive storytelling delivery with natural pauses.",
        "وثائقي": "Use a calm, confident documentary narration style.",
        "هادئ": "Speak softly and calmly with a relaxed pace.",
        "سريع وواضح": "Speak at a brisk pace while maintaining clear Somali pronunciation."
    }
    emotions = {
        "بدون تحديد": "",
        "سعيد": "Convey a warm, happy emotion.",
        "حزين": "Use a gentle, sad and reflective tone.",
        "جاد": "Use a serious, composed tone.",
        "درامي": "Use expressive dramatic narration."
    }
    instruction = " ".join(x for x in [presets.get(style,""),emotions.get(emotion,""),(extra or "").strip()] if x)
    headers = {}
    incoming = request.headers.get("x-ip-token", "")
    if incoming:
        headers["x-ip-token"] = incoming
    try:
        client = Client("k2-fsa/OmniVoice", verbose=False, headers=headers)
        result = client.predict(text,"Somali",handle_file(str(path)),reference_text,instruction,32,2.0,True,1.0,0,True,True,api_name="/_clone_fn")
        audio = result[0] if isinstance(result,(tuple,list)) else result
        status = str(result[1]) if isinstance(result,(tuple,list)) and len(result)>1 else "Done"
        if status.lower().startswith("error"):
            raise RuntimeError(status)
        wav_bytes = audio_to_wav(audio)
        output = TMP / f"somalitts-clone-{time.time_ns()}.wav"
        output.write_bytes(wav_bytes)
        return str(output), "تم إنشاء الصوت المستنسخ. استمع إليه ثم نزّله. قد تختلف مدة الانتظار حسب ضغط OmniVoice."
    except gr.Error:
        raise
    except Exception as exc:
        message = str(exc).lower()
        if any(x in message for x in ("zerogpu","quota","queue","rate limit","429")):
            raise gr.Error("محرك OmniVoice مشغول أو انتهت الحصة المجانية مؤقتاً. انتظر تجدد الحصة ثم أعد المحاولة.") from exc
        raise gr.Error(f"تعذر استنساخ الصوت من OmniVoice: {str(exc)[:240]}") from exc

with gr.Blocks(title="SomaliTTS Studio", theme=gr.themes.Soft(primary_hue="blue",secondary_hue="cyan",neutral_hue="slate"), css=CSS) as demo:
    gr.HTML("""
    <div id="hero" dir="rtl">
      <div class="kicker">✦ SOMALITTS · SOMALI VOICE LAB</div>
      <h1>صوتك الصومالي، <span style="background:linear-gradient(90deg,#74baff,#5eead4);-webkit-background-clip:text;background-clip:text;color:transparent">بإمكانيات استوديو متكامل.</span></h1>
      <p>حوّل النصوص الصومالية إلى كلام طبيعي، أو استنسخ صوتك من عينة قصيرة. واجهة واحدة مصممة للهاتف، مع معاينة وتنزيل مباشر.</p>
    </div>
    """)
    with gr.Tabs():
        with gr.Tab("استنساخ صوتي · Voice Clone"):
            gr.Markdown("### استنساخ صوتك\nارفع تسجيلاً واضحاً، اكتب نصه كما نطقته، ثم أدخل النص الجديد. استخدم صوتك أو تسجيلاً لديك إذن باستخدامه.")
            with gr.Row():
                with gr.Column():
                    ref_audio = gr.Audio(label="عينة صوتك — ارفع ملفاً أو سجّل مباشرة",type="filepath",sources=["upload","microphone"])
                    ref_text = gr.Textbox(label="الكلام المطابق للتسجيل",placeholder="اكتب هنا الكلمات التي قلتها في التسجيل...",lines=2,rtl=True)
                    style = gr.Dropdown(["طبيعي وواضح","حماسي وجذاب","سرد قصصي","وثائقي","هادئ","سريع وواضح"],value="طبيعي وواضح",label="أسلوب الإلقاء")
                    emotion = gr.Dropdown(["بدون تحديد","سعيد","حزين","جاد","درامي"],value="بدون تحديد",label="الإحساس")
                    extra = gr.Textbox(label="تعليمات إضافية (اختياري)",placeholder="مثلاً: اقرأ بنبرة راوي أنمي، مع وضوح مخارج الحروف.",lines=2,rtl=True)
                with gr.Column():
                    clone_text = gr.Textbox(label="النص الصومالي المراد توليده",placeholder="Ku qor qoraalka Af-Soomaaliga aad rabto in codkaaga lagu akhriyo...",lines=12,max_lines=20,max_length=MAX_CLONE_TEXT,rtl=True)
                    clone_btn = gr.Button("✦ استنسخ الصوت الآن",variant="primary")
                    clone_status = gr.Markdown("**المحرك:** OmniVoice على Hugging Face · **الحالة:** حسب التوافر والحصة المجانية.")
                    clone_output = gr.Audio(label="الصوت المستنسخ — استمع أو نزّل",type="filepath")
            clone_btn.click(clone_voice,inputs=[clone_text,ref_text,ref_audio,style,emotion,extra],outputs=[clone_output,clone_status],concurrency_limit=1)
        with gr.Tab("تحويل النص إلى كلام · Text to Speech"):
            gr.Markdown("### تحويل النص الصومالي إلى كلام\nأصوات Muuse وUbax. النص الطويل يُقسّم تلقائياً إلى مقاطع ثم يُدمج في ملف MP3 واحد.")
            with gr.Row():
                with gr.Column():
                    tts_text = gr.Textbox(label="النص الصومالي",placeholder="Ku qor qoraalkaaga Af-Soomaaliga halkan...",lines=13,max_lines=24,max_length=MAX_TTS_TEXT,rtl=True)
                    gender = gr.Radio(choices=[("Muuse — صوت رجالي","male"),("Ubax — صوت نسائي","female")],value="male",label="اختر الصوت")
                    tts_btn = gr.Button("♫ أنشئ ملف MP3",variant="primary")
                with gr.Column():
                    tts_output = gr.Audio(label="النتيجة — استمع أو نزّل",type="filepath")
                    tts_status = gr.Markdown("**Muuse:** so-SO-MuuseNeural · **Ubax:** so-SO-UbaxNeural")
            tts_btn.click(create_tts,inputs=[tts_text,gender],outputs=[tts_output,tts_status],concurrency_limit=2)
    gr.HTML("""
    <div id="notice" dir="rtl"><b>ملاحظات تشغيل مهمة:</b> الاستنساخ يعتمد على خدمة OmniVoice الخارجية وحصتها المجانية؛ هذه الواجهة لا تزيد الحصة ولا تضمن التوليد غير المحدود. قد تتأخر الطلبات عند ازدحام الخدمة. عينة الصوت تُرسل إلى OmniVoice للمعالجة. استخدم صوتك أو تسجيلاً لديك إذن باستخدامه. أوزان OmniVoice المنشورة بترخيص CC-BY-NC؛ هذا الربط للاستخدام الشخصي/غير التجاري ما لم تحصل على ترخيص تجاري منفصل.</div>
    <div id="foot">SomaliTTS Studio · Somali-first voice tools · Built for mobile and desktop</div>
    """)

if __name__ == "__main__":
    demo.queue(default_concurrency_limit=2,max_size=12).launch()
