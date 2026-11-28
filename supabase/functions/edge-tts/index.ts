import { createSupabaseContext } from "npm:@supabase/server";
import { EdgeTTS } from "npm:node-edge-tts@1.2.12";

const allowedVoices = new Set(["so-SO-MuuseNeural", "so-SO-UbaxNeural"]);
const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Vary": "Origin",
};

function splitText(text: string, limit = 3000): string[] {
  const out: string[] = [];
  let rest = text.trim();
  while (rest.length > limit) {
    let cut = rest.lastIndexOf(" ", limit);
    if (cut < Math.floor(limit * 0.55)) cut = limit;
    out.push(rest.slice(0, cut).trim());
    rest = rest.slice(cut).trim();
  }
  if (rest) out.push(rest);
  return out;
}

async function synthesizeChunk(text: string, voice: string): Promise<Uint8Array> {
  const tts = new EdgeTTS({
    voice,
    lang: "so-SO",
    outputFormat: "audio-24khz-96kbitrate-mono-mp3",
    timeout: 60000,
  });
  const audio: Uint8Array[] = [];
  for await (const part of tts.streamAudio(text)) {
    if (part instanceof Uint8Array) audio.push(new Uint8Array(part));
  }
  if (!audio.length) throw new Error("Microsoft Edge TTS لم يُرجع بيانات صوتية.");
  const size = audio.reduce((n, item) => n + item.length, 0);
  const merged = new Uint8Array(size);
  let offset = 0;
  for (const item of audio) { merged.set(item, offset); offset += item.length; }
  return merged;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
  if (req.method !== "POST") return Response.json({ error: { message: "Use POST." } }, { status: 405, headers: cors });

  const { data: ctx, error: authError } = await createSupabaseContext(req, { auth: "user" });
  if (authError || !ctx?.userClaims?.id) {
    return Response.json({ error: { message: "يلزم تسجيل الدخول إلى مكتبتك الخاصة." } }, { status: 401, headers: cors });
  }

  try {
    const body = await req.json();
    const text = typeof body.text === "string" ? body.text.trim() : "";
    const voice = typeof body.voice === "string" ? body.voice : "";
    if (!text || text.length > 12000) throw new Error("النص يجب ألا يتجاوز 12,000 حرف.");
    if (!allowedVoices.has(voice)) throw new Error("معرّف الصوت غير مسموح.");

    const parts: Uint8Array[] = [];
    for (const chunk of splitText(text)) {
      parts.push(await synthesizeChunk(chunk, voice));
    }
    const total = parts.reduce((n, part) => n + part.length, 0);
    const output = new Uint8Array(total);
    let offset = 0;
    for (const part of parts) { output.set(part, offset); offset += part.length; }

    return new Response(output, {
      status: 200,
      headers: { ...cors, "Content-Type": "audio/mpeg", "Cache-Control": "no-store" },
    });
  } catch (error) {
    console.error("edge-tts synthesis failed", error);
    return Response.json({
      error: { message: error instanceof Error ? error.message : "تعذر توليد الصوت." },
    }, { status: 502, headers: cors });
  }
});
