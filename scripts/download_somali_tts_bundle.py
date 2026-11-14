#!/usr/bin/env python3
"""One-pass downloader for SomaliTTS research assets.

Downloads candidate repositories from Hugging Face into one directory.
This does NOT certify model or recording rights. See assets/somali_bundle/README.md.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone

from huggingface_hub import snapshot_download

ASSETS = [
    {
        "repo_id": "ayeeyokoris/hubi-tts",
        "repo_type": "model",
        "folder": "models/hubi-tts",
        "license_status": "UNKNOWN - experimental only; do not use commercially until verified",
        "commercial_ok": False,
    },
    {
        "repo_id": "zakihassan/som_tts",
        "repo_type": "dataset",
        "folder": "datasets/som_tts",
        "license_status": "Apache-2.0 declared by dataset card; independently verify underlying recording permissions",
        "commercial_ok": True,
    },
    {
        "repo_id": "maanka2/ayaan-somali-tts-corpus",
        "repo_type": "dataset",
        "folder": "datasets/ayaan-somali-tts-corpus",
        "license_status": "Apache-2.0 declared by dataset card; independently verify underlying recording permissions",
        "commercial_ok": True,
    },
    {
        "repo_id": "facebook/mms-tts-som",
        "repo_type": "model",
        "folder": "restricted/mms-tts-som",
        "license_status": "CC-BY-NC-4.0 - NON-COMMERCIAL ONLY",
        "commercial_ok": False,
    },
]

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/kaggle/working/SomaliTTS-assets")
    parser.add_argument("--include-restricted", action="store_true",
                        help="Also download non-commercial MMS for research; never use commercially.")
    args = parser.parse_args()

    root = Path(args.output).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("HF_TOKEN")
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output_directory": str(root),
        "notice": "Downloaded files retain their upstream licenses. This manifest is not legal advice.",
        "assets": [],
    }

    for item in ASSETS:
        if item["repo_id"] == "facebook/mms-tts-som" and not args.include_restricted:
            manifest["assets"].append({**item, "status": "skipped_by_default"})
            print(f"SKIP restricted: {item['repo_id']}")
            continue
        target = root / item["folder"]
        try:
            path = snapshot_download(
                repo_id=item["repo_id"],
                repo_type=item["repo_type"],
                local_dir=str(target),
                token=token,
                resume_download=True,
            )
            manifest["assets"].append({**item, "status": "downloaded", "path": str(path)})
            print(f"DOWNLOADED: {item['repo_id']} -> {path}")
        except Exception as exc:
            manifest["assets"].append({**item, "status": "failed", "error": str(exc)})
            print(f"FAILED: {item['repo_id']}: {exc}")

    manifest_path = root / "download-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest: {manifest_path}")
    return 0 if any(x["status"] == "downloaded" for x in manifest["assets"]) else 1

if __name__ == "__main__":
    raise SystemExit(main())
