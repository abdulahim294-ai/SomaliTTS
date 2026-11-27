# Mobile Runtime and Capability Gate

This reference prevents overpromising when the user works in Claude mobile.

## What a custom Skill does

A Skill gives Claude reusable instructions and optional reference material. It does not install FFmpeg, Demucs, Whisper, Python packages, system codecs, desktop applications, MCP servers or Android apps. It does not grant access to the phone's Downloads folder unless the user attaches a file or a supported connector exposes it.

## Before editing

1. List files actually attached to the conversation.
2. Check which code/file tools are exposed.
3. Check whether code execution and file creation are enabled.
4. Test whether Python and needed packages are available.
5. Test FFmpeg/FFprobe only if shell execution is genuinely exposed.
6. Confirm writable storage and output-size constraints.
7. Never infer capabilities from the word "Claude" or from this Skill.

## Free-plan expectations

Plan availability, usage caps, upload limits, file limits and runtime limits can change. Verify the current in-app UI/help documentation rather than promising unlimited processing. Skills may be available on Free when code execution and file creation are enabled, but this does not mean every file size or long-running render will fit.

## Honest fallback ladder

- Full render possible: render, inspect, repair, deliver.
- Audio processing possible but video render not: deliver clean audio and a timestamped EDL.
- Analysis possible but processing not: deliver a scene map and exact reproducible commands/scripts.
- Only file reading possible: inspect assets and provide a clear limitation report.
- No access to attached assets: ask the user to attach them; do not pretend to inspect them.

## Never

- Claim the phone's local storage is accessible without evidence.
- Claim an external program ran without tool output.
- Claim an API key or MCP integration exists without a connected tool.
- Claim a download was performed if no file was created.
- Invent output links.
