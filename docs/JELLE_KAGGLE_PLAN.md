# Jelle Kaggle first-pass experiment

**Status:** prepared, not yet executed. Branch: `experiment/jelle-kaggle-first-pass`.

## Responsibility split

- **Kaggle:** primary compute environment for loading Jelle, its SpeechT5 vocoder, generating test WAVs, measuring runtime, and saving a report. Use a temporary GPU session; do not treat it as an always-on production worker.
- **GitHub:** versioned source of the reproducible notebook, pinned model revision, test procedure, and later inference adapter code.
- **Render:** retain the current lightweight FastAPI service and existing `/tts` contract. Do not install PyTorch/Jelle on the current Free instance (documented at 512 MB RAM / 0.1 CPU).
- **Supabase:** later handle authenticated job metadata, private voice samples/results, ownership/RLS, and signed storage access. No schema or function changes are required for the first model-quality test.

## Current test design

The notebook loads `Somali-tts/Jelle_tts` at revision `ee0109720255e9b979bec7d9787de456747f4fa7`, plus `microsoft/speecht5_hifigan`. It uses one public CMU Arctic x-vector solely as a technical speaker-conditioning input. It does not upload or use the user's personal recording and does not perform voice cloning.

## Kaggle run requirements

1. Import `notebooks/jelle_kaggle_first_pass.ipynb` into Kaggle.
2. In Notebook → Session options, enable Internet and select a GPU.
3. Run cells from top to bottom.
4. Listen to all three generated Somali WAV samples and inspect `jelle_test_report.json`.
5. Save a notebook version and retain the output files.

The Kaggle session is temporary. A successful run proves the checkpoint can be executed in that session; it does not provide a persistent production inference endpoint.

## Gate before integration

Do not switch the deployed provider or alter the frontend until a Somali-speaking listener confirms intelligibility and acceptable pronunciation. Then test longer text, chunk boundaries, output quality, and a sustainable worker design. The current Edge TTS provider remains intact as fallback.
