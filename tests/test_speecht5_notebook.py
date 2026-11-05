import ast
import json
from pathlib import Path


NOTEBOOK_PATH = (
    Path(__file__).resolve().parents[1]
    / "notebooks"
    / "somali_speecht5_baseline.ipynb"
)


def test_somali_speecht5_notebook_is_valid_and_executable_python():
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))

    assert notebook["nbformat"] == 4
    assert notebook["metadata"]["kernelspec"]["name"] == "python3"

    code_cells = [
        cell for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    ]
    assert code_cells

    for index, cell in enumerate(code_cells):
        source = cell.get("source", [])
        code = "".join(source) if isinstance(source, list) else source

        # Ignore IPython line magics such as the notebook's %pip install cell.
        python_lines = [
            line for line in code.splitlines()
            if not line.lstrip().startswith("%")
        ]
        python_code = "\n".join(python_lines)

        if python_code.strip():
            ast.parse(python_code, filename=f"notebook-cell-{index}")


def test_somali_speecht5_notebook_keeps_experiment_scope_explicit():
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    all_source = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
    )

    assert "Somali-tts/Jelle_tts" in all_source
    assert "Somali-tts/diirow_tts" in all_source
    assert "microsoft/speecht5_hifigan" in all_source
    assert "use_safetensors=True" in all_source
    assert "does not perform voice cloning or RVC" in all_source
    assert "Do not move to RVC unless at least one baseline is intelligible." in all_source


def test_speecht5_notebook_validates_audio_and_continues_after_model_failure():
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    all_source = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
    )

    assert "np.isfinite(audio).all()" in all_source
    assert "Unexpected generated waveform shape" in all_source
    assert "effectively silent" in all_source
    assert "status': 'failed'" in all_source
    assert "run_info['outputs'] = results" in all_source
    assert "gc.collect()" in all_source


def test_speecht5_notebook_pins_dataset_and_packages_results():
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    all_source = "\\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
    )

    assert "DATASET_ID = 'Matthijs/cmu-arctic-xvectors'" in all_source
    assert "api.dataset_info(DATASET_ID).sha" in all_source
    assert "revision=resolved[DATASET_ID]" in all_source
    assert "somali_baseline_results.zip" in all_source
    assert "zipfile.ZIP_DEFLATED" in all_source
