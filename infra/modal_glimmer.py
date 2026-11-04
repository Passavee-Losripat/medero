"""Muse Glimmer on Modal (fallback router + full-precision baseline for the benchmark).

NOT DEPLOYED. Deploy only when the user says so:  modal deploy infra/modal_glimmer.py
VERIFY before deploying: the exact Hugging Face repo id of Muse Glimmer, its license
terms, GPU memory needs (~60 GB at full precision per third-party articles), and
whether vLLM supports it. Record findings in docs/api-notes.md.

Serves an OpenAI-compatible API, so set in .env:
  ROUTER_PROVIDER=modal
  MODAL_LLM_BASE=https://<your-modal-url>/v1
  MODAL_LLM_KEY=<value of the MEDERO_MODAL_TOKEN secret>
  MODAL_LLM_MODEL=<same as GLIMMER_MODEL_ID>
"""

import os
import subprocess

import modal

GLIMMER_MODEL_ID = os.environ.get("GLIMMER_MODEL_ID", "VERIFY/muse-glimmer")  # placeholder until verified
GPU = os.environ.get("GLIMMER_GPU", "H100")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("vllm", "huggingface_hub[hf_transfer]")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)
weights = modal.Volume.from_name("medero-glimmer-weights", create_if_missing=True)
app = modal.App("medero-glimmer")


@app.function(
    image=image, gpu=GPU, volumes={"/root/.cache/huggingface": weights},
    secrets=[modal.Secret.from_name("medero-modal")],  # holds MEDERO_MODAL_TOKEN (and HF_TOKEN if needed)
    scaledown_window=300, timeout=3600,
)
@modal.concurrent(max_inputs=16)
@modal.web_server(port=8000, startup_timeout=1200)
def serve():
    subprocess.Popen([
        "vllm", "serve", GLIMMER_MODEL_ID, "--port", "8000", "--host", "0.0.0.0",
        "--served-model-name", GLIMMER_MODEL_ID, "--max-model-len", "8192",
        "--api-key", os.environ["MEDERO_MODAL_TOKEN"],
    ])
