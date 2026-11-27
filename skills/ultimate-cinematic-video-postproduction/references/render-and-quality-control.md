# Render and Quality Control

## Render safety

- Never overwrite source files.
- Keep intermediates separate from final outputs.
- Prefer deterministic command lines and reproducible settings.
- Preserve source resolution and frame rate unless requested.
- Use chunked rendering if memory/storage is constrained.
- Keep a render log when possible.

## Common output profile

MP4, H.264, AAC, yuv420p, 48 kHz audio, fast-start metadata. Choose bitrate/CRF based on source resolution, motion and size constraints. Do not upscale just to advertise 4K.

## QC checklist

### Picture
- Correct aspect ratio and frame rate.
- No accidental black/frozen frames.
- No unintended repeated footage.
- No wrong character or irrelevant image over important narration.
- No broken/cropped graphics or captions.
- No visible render glitches.
- Color continuity between adjacent shots.

### Sound
- No clipped syllables or cut words.
- No clicks at joins.
- No unnatural gaps.
- No clipping or distortion.
- Narration intelligible over music/SFX.
- Original effects retained when requested and technically recoverable.
- No unwanted original dialogue remnants if removal was requested.
- No sync drift.

### Delivery
- Confirm actual file exists.
- Probe metadata if possible.
- Verify duration and stream alignment.
- Inspect opening, middle, joins and ending.
- Report only measured values.
