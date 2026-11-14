# SomaliTTS one-pass asset bundle

This bundle script downloads the current Somali speech candidates into one folder.
It is intended for a Kaggle GPU/Internet notebook or another machine with sufficient
disk space. It does not train models, start an inference server, or change Laravel.

## Contents

| Repository | Type | Declared license/status | Intended use |
|---|---|---|---|
| `ayeeyokoris/hubi-tts` | Model | License not clearly declared | Experimental Somali voice-cloning candidate only |
| `zakihassan/som_tts` | Dataset | Apache-2.0 in the HF dataset card | Somali TTS training data; confirm recording rights |
| `maanka2/ayaan-somali-tts-corpus` | Dataset | Apache-2.0 in the HF dataset card | Somali TTS training data; confirm recording rights |
| `facebook/mms-tts-som` | Model | CC-BY-NC-4.0 | Excluded by default; research/non-commercial only |

The dataset repositories declare Apache-2.0, but that metadata alone does not prove
that every underlying speaker recording was collected with commercial redistribution
and model-training consent. Preserve the original dataset cards and attribution.

Hubi is downloaded as a candidate, not as a commercially cleared model. Review its
model code before loading it: the current inference adapter uses
`trust_remote_code=True`. Pin a reviewed commit before any production deployment.

## Run once

```bash
python -m pip install -U huggingface_hub
python scripts/download_somali_tts_bundle.py
```

Default output: `/kaggle/working/SomaliTTS-assets`.

To additionally fetch the non-commercial MMS checkpoint for research only:

```bash
python scripts/download_somali_tts_bundle.py --include-restricted
```

Set `HF_TOKEN` only if Hugging Face requires authentication for a repository.
The script writes `download-manifest.json` with each download result and continues
if one repository fails. The full Ayaan corpus is approximately 3.95 GB, in addition
to other model/data downloads, so ensure sufficient disk space and Kaggle Internet.
