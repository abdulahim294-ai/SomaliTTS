---
title: SomaliTTS Studio
emoji: 🎙️
colorFrom: blue
colorTo: cyan
sdk: gradio
sdk_version: 5.49.1
python_version: 3.10
app_file: app.py
suggested_hardware: zero-a10g
models:
  - k2-fsa/OmniVoice
tags:
  - text-to-speech
  - voice-cloning
  - somali
  - tts
pinned: false
---

# SomaliTTS Studio

A mobile-first Somali voice studio with two tools:

- Somali voice cloning through the hosted k2-fsa/OmniVoice Gradio Space. The app forwards the incoming x-ip-token header when available so Hugging Face can attribute ZeroGPU usage to the end user.
- Somali text-to-speech using Microsoft Edge TTS voices so-SO-MuuseNeural and so-SO-UbaxNeural, with long-text chunking and MP3 normalization when FFmpeg is available.

## Deployment

This app is designed for a Hugging Face Gradio Space on ZeroGPU. It does not download or host the OmniVoice model weights itself. Select ZeroGPU hardware when creating the Space; the suggested hardware in this card does not guarantee account access.

## Important limits

- Voice cloning still depends on the upstream OmniVoice Space, its queue, availability, and the user's own free quota. This app does not bypass or multiply that quota.
- OmniVoice model weights are published under CC-BY-NC. This integration is for personal/non-commercial use unless separate commercial permission is obtained.
- Uploaded voice samples are forwarded to OmniVoice for inference. Use only your own voice or audio you have explicit permission to use.
- No account system or persistent user audio storage is implemented in this lightweight free-hosting edition.
