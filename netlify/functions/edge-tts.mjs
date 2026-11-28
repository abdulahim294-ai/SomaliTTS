import { EdgeTTS } from "node-edge-tts";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const SUPABASE_URL = "https://eczhhuhwrxfuzfczycug.supabase.co";
const SUPABASE_KEY = "sb_publishable_NduGBJGnHbxZPOJz1eYQgg_IWDy0wRa";
const VOICES = new Set(["so-SO-MuuseNeural", "so-SO-UbaxNeural"]);

export default async (request) => {
  if (request.method !== "POST") return Response.json({ error: "Method not allowed." }, { status: 405 });
  const authorization = request.headers.get("authorization") || "";
  if (!authorization.startsWith("Bearer ")) return Response.json({ error: "يلزم الاتصال بمكتبتك الخاصة." }, { status: 401 });
  try {
    const authCheck = await fetch(SUPABASE_URL + "/auth/v1/user", {
      headers: { apikey: SUPABASE_KEY, Authorization: authorization }
    });
    if (!authCheck.ok) return Response.json({ error: "انتهت جلسة المكتبة. أعد تحميل الصفحة." }, { status: 401 });
    const body = await request.json();
    const text = typeof body.text === "string" ? body.text.trim() : "";
    const voice = typeof body.voice === "string" ? body.voice : "";
    if (!text || text.length > 900) return Response.json({ error: "يجب أن يكون النص بين حرف واحد و900 حرف لكل طلب." }, { status: 400 });
    if (!VOICES.has(voice)) return Response.json({ error: "الصوت المطلوب غير مدعوم." }, { status: 400 });

    const directory = await mkdtemp(join(tmpdir(), "somalitts-edge-"));
    const outputPath = join(directory, "speech.mp3");
    try {
      const tts = new EdgeTTS({ voice, lang: "so-SO", outputFormat: "audio-24khz-96kbitrate-mono-mp3", timeout: 45000 });
      await tts.ttsPromise(text, outputPath);
      const audio = await readFile(outputPath);
      if (!audio.length) throw new Error("لم يُرجع محرك الصوت بيانات صوتية.");
      return new Response(audio, { status: 200, headers: { "Content-Type": "audio/mpeg", "Cache-Control": "no-store" } });
    } finally {
      await rm(directory, { recursive: true, force: true });
    }
  } catch (error) {
    return Response.json({ error: error?.message || "فشل توليد الصوت." }, { status: 502 });
  }
};

export const config = {
  rateLimit: { action: "rate_limit", aggregateBy: "ip", windowSize: 60, windowLimit: 30 }
};
