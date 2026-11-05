# Somali voice pipeline: feasibility and architecture decision

**Status:** research / prototype gate — not production-ready  
**Updated:** 2026-11-05  
**Decision owner:** SomaliTTS maintainers

## Executive decision

Do not run PyTorch, model training, or voice-conversion inference on the current Render Free web service. Its 512 MB RAM / 0.1 CPU allocation is suitable only for lightweight API orchestration and the existing Edge TTS adapter.

The most defensible zero-cash experiment is a two-stage pipeline:

1. Generate Somali source speech with a Somali-capable TTS checkpoint (initial candidates: `Somali-tts/Jelle_tts` and `Somali-tts/diirow_tts`).
2. Convert the generated speech to a consenting speaker's timbre with a separately trained voice-conversion model (RVC is the first experiment, not yet an approved production dependency).

This separation means the conversion model does not need to tokenize or understand Somali text. It still does **not** prove good Somali pronunciation, preservation of consonants/prosody, or speaker similarity. Those must be measured with Somali-speaking listeners.

No end-to-end Somali voice-cloning prototype has been executed by this repository as of this document. The current deployed product remains Edge TTS with the configured Muuse and Ubax voices. Do not advertise cloning as available.

## Current system facts

- FastAPI application: `app.py`; existing synthesis endpoint: `POST /tts`.
- Existing provider registry contains only `EdgeTTSProvider`.
- FFmpeg handles audio normalization/encoding; it is not a TTS or cloning engine.
- Render hosts the lightweight API only.
- Supabase has RLS-protected `profiles`, `voice_models`, `voice_samples`, `clone_jobs`, and `usage_events` tables, plus private `voice-samples` and `generated-audio` buckets.
- Supabase Edge Functions currently include `voice-library` and `omnivoice-status`. The latter is a model/Space status probe, not an inference API.
- Voice sample rows and clone jobs are currently empty. A schema row or upload is not evidence that a trained model exists.
- The production health deploy `ded0a9e4d876823b4e12b23646fa7344192fafe7` is Live on Render. GitHub CI previously passed Python tests and Docker build for that commit.

## Candidate assessment

| Candidate | Somali speech | Voice conversion / cloning | License / evidence | Decision |
|---|---|---|---|---|
| `Somali-tts/Jelle_tts` | Somali TTS checkpoint | No | Model card declares MIT; its training data description is incomplete and the upstream SpeechT5/vocoder chain must also be reviewed | First baseline candidate; validate pronunciation and full dependency/data rights |
| `Somali-tts/diirow_tts` | Somali TTS checkpoint | No | Model card declares MIT; training data description is incomplete and the upstream SpeechT5/vocoder chain must also be reviewed | Second baseline candidate |
| RVC WebUI | Converts audio timbre; does not generate Somali text | Yes, after speaker-specific training | Main RVC repository LICENSE declares MIT for the repository code. This does not automatically license every checkpoint, pretrained asset, feature extractor, vocoder, dataset, or downloaded model | Best first conversion experiment; audit each artifact before distribution or paid use |
| OmniVoice | Broad multilingual TTS, including Somali according to its model card | Yes, reference-based | Model card states CC-BY-NC for pretrained weights | Exclude from commercial product; do not build production around it |
| Meta MMS Somali TTS | Somali TTS | No | Relevant checkpoint card states CC-BY-NC | Exclude from commercial product |
| VoxCPM2 | Its documented language list does not include Somali | Yes | Project advertises Apache-2.0 code/model; Somali capability is not established | Not a Somali base generator |
| MOSS-TTS-Nano | Documented supported languages do not include Somali | Reference-audio voice cloning | Apache-2.0 model card, but no Somali support established | Not a solution to Somali synthesis |
| `lakiLabs/omi-tts` | Experimental Somali-tagged work | Not currently a usable cloning path | Apache-2.0 reported; model requires an external vocoder and voice cloning is future work | Revisit only after a complete waveform-generation pipeline is demonstrated |

**Important licensing rule:** a permissive repository license is not a blanket license for all downloaded weights or training data. Before a public or paid release, record the exact revision, license, attribution obligations, source dataset rights, vocoder license, and any third-party component license for every artifact used.

## RVC feasibility and limitations

The upstream RVC documentation recommends at least around 10 minutes of clean, low-noise speech for training. It supports CPU dependency installations, but that does not mean CPU training or conversion will be practical on the user's low-resource laptop or Render Free. RVC's published setup includes multiple large pretrained assets and PyTorch/CUDA variants.

A realistic first experiment requires a temporary GPU notebook or GPU-backed demo environment. Hugging Face ZeroGPU currently advertises a free-account daily quota of 5 minutes, shared queues, and Gradio-only hosting constraints. That is useful for a short feasibility test, not a dependable multi-user inference service. Kaggle's current documentation describes a weekly GPU quota (up to 30 hours, sometimes higher depending on demand), a free P100 option, and queues when demand is high; notebook sessions are time-bounded and the GPU is not guaranteed. Never treat a free notebook as an always-on production worker. The RVC model-assets repository lists MIT metadata but is very large (about 103 GB) and includes legacy pickle-based checkpoints; do not download the whole repository or load arbitrary checkpoints. Pin only the exact required files, verify provenance and hashes, and use safe weight-loading practices.

### Critical signal-processing risk

RVC conversion is not guaranteed to preserve Somali phonemes. The source TTS must already pronounce the words correctly. Test:
- Somali consonants and vowel length;
- words with similar phonetic structure;
- sentence-final intonation;
- code-switching and names;
- male and female source voices;
- 5–15 second and 30–60 second clips;
- output intelligibility and speaker similarity, judged by native Somali listeners.

Do not optimize only for a voice similarity score. A convincing clone that corrupts the words is not useful for narration.

## Target architecture

```text
Browser / mobile UI
    |
    | Supabase Auth JWT
    v
Render FastAPI (lightweight control plane only)
    |-- validates user and request
    |-- creates/updates job metadata
    |-- issues short-lived signed storage URLs
    |-- never loads PyTorch or model weights
    |
    +---- Supabase Postgres (RLS)
    |       profiles / voice_models / voice_samples
    |       clone_jobs / usage_events
    |
    +---- Supabase Storage (private)
    |       voice-samples / generated-audio
    |
    +---- GPU worker (separate, ephemeral during prototype)
            1. fetch authorized input via signed URL
            2. Somali TTS -> source audio
            3. speaker-specific RVC -> converted audio
            4. validate duration, codec, silence, and size
            5. upload result to private generated-audio bucket
            6. report job state to authenticated backend
```

The GPU worker is **not yet deployed**. Do not place its credentials in browser code. A production worker must authenticate jobs, verify ownership server-side, limit file sizes/durations, reject arbitrary URLs, isolate per-user models, clean temporary files, and prevent one user from reading another user's voice assets.

## Consent, abuse prevention, and privacy requirements

Before accepting any voice model:
- Require the speaker to affirm that the recording is their own voice or that they have documented authorization from the speaker.
- Explicitly prohibit impersonation, fraud, harassment, and cloning public figures or other people without permission.
- Record consent version, timestamp, user ID, and source sample ID.
- Provide revoke/delete controls for source audio, trained weights, generated outputs, and associated metadata.
- Keep buckets private; use short-lived signed URLs.
- Never expose raw storage paths as public links.
- Do not upload a user's voice sample to an external GPU notebook or model provider without a clear, separate disclosure and explicit consent.
- Do not place user audio in public datasets or model repositories.
- Apply per-user quotas and job duration limits before any public beta.

## Prototype acceptance gates

The RVC prototype is accepted only when all are true:

1. A known-consenting speaker's clean Somali recording is used.
2. The selected RVC code revision and every required pretrained artifact have recorded licenses.
3. Jelle and Diirow baseline outputs are generated and listened to by native Somali speakers.
4. Converted output remains intelligible and recognizably matches the consenting speaker.
5. Test inputs and outputs are stored privately and can be deleted.
6. The pipeline can be repeated from a clean notebook using documented, pinned dependencies.
7. No user audio is exposed publicly or retained in a third-party runtime after the experiment.

A passing technical demo is not sufficient to launch a paid service. Commercial launch additionally requires a sustainable GPU worker, abuse controls, privacy terms, data/weight rights review, and cost-per-minute measurements.

## Work that can be done at zero cash

- Keep Render as the lightweight API and Supabase as auth/database/private storage.
- Build provider/job interfaces, request validation, signed-URL orchestration, tests, and operational documentation.
- Run small, temporary experiments when a free GPU quota is available.
- Compare Jelle and Diirow audio samples and collect consented, local listener feedback.
- Prototype RVC training/inference in a notebook without promising uptime.

## Work that cannot honestly be promised for free

- Always-on GPU inference for many users.
- Guaranteed GPU notebook availability or persistent sessions.
- Commercial rights to non-commercial weights or unclear datasets.
- Production-grade voice cloning from a single short sample without quality trade-offs.
- Reliable emotion transfer, video scene analysis, lip-sync, or sound-effect generation before the voice pipeline is validated.

## Next engineering sequence

1. Validate baseline Jelle/Diirow inference in a disposable GPU notebook and document exact output quality.
2. Validate the full RVC conversion path using a speaker-owned sample and licensed assets.
3. If quality passes, define a narrow GPU-worker contract and job lifecycle; keep model execution out of Render.
4. Add authenticated orchestration and private storage transfers only after the worker has a real, repeatable implementation.
5. Run security, privacy, deletion, and cost tests before inviting external users.

## References

- RVC project and training/runtime guidance: https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI
- RVC repository MIT license: https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/LICENSE
- RVC model assets repository (audit artifact-specific terms): https://huggingface.co/lj1995/VoiceConversionWebUI
- Somali Jelle TTS model card: https://huggingface.co/Somali-tts/Jelle_tts
- Somali Diirow TTS model card: https://huggingface.co/Somali-tts/diirow_tts
- OmniVoice model card and license: https://huggingface.co/k2-fsa/OmniVoice
- Hugging Face ZeroGPU official documentation: https://huggingface.co/docs/hub/spaces-zerogpu
- Kaggle free GPU and session documentation: https://www.kaggle.com/docs/notebooks and https://www.kaggle.com/docs/efficient-gpu-usage
