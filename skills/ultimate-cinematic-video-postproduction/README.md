# Ultimate Cinematic Video Post-Production

An all-in-one Agent Skill for Claude.ai mobile and web workflows, focused on editing existing footage to a narration-led master timeline.

## Contents

- `SKILL.md` — master workflow and execution rules.
- `references/mobile-runtime-and-capabilities.md` — realistic mobile/cloud capability checks.
- `references/audio-dialogue-and-sfx.md` — dialogue cleanup, sound separation and mix.
- `references/story-edit-and-visual-sync.md` — semantic scene matching and continuity.
- `references/render-and-quality-control.md` — export and QC.

## Upload to Claude

1. Download this folder as a ZIP with the folder itself at the ZIP root.
2. In Claude, enable **Code execution and file creation** in Settings > Capabilities.
3. Open Customize > Skills > + > Create skill > Upload a skill.
4. Upload this ZIP and enable the Skill.

Claude's mobile app can expose the Skills settings, but actual video processing depends on the tools and runtime available to the conversation. This Skill does not install FFmpeg or provide unlimited compute.

## Compatibility

Written as an Agent Skills-style package for Claude.ai custom Skill upload. It is guidance and reference content, not a bundled video editor or media-processing runtime.
