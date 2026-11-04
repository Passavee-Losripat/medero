"""Muse Glimmer 4-bit on Modal: the same model and runtime as the local Mac setup, on a GPU we control,
so the public demo can keep identifying documents off third-party APIs and the router benchmark has a
cloud-GPU row.

Model (VERIFIED 2026-11-05 on the Hugging Face model card): meta-models/Muse-Glimmer-30B-GGUF, Apache-2.0,
not gated. Q4_K_M text build (~17 GB) + mmproj perception encoder (~1.4 GB, needed for images).
Runtime: llama.cpp server, build >= b10353 (Glimmer architecture support).

Steps (only when the user says so; this spends Modal credits):
  pip install modal && modal token new
  modal secret create medero-modal MEDERO_MODAL_TOKEN=<random string>
  modal run infra/modal_glimmer.py::download      # once, fills the volume
  modal deploy infra/modal_glimmer.py

Then in .env:
  MODAL_LLM_BASE=https://<workspace>--medero-glimmer-serve.modal.run/v1
  MODAL_LLM_KEY=<the same random string>
  MODAL_LLM_MODEL=muse-glimmer-30B
  DOC_PROVIDER=modal            # and/or ROUTER_PROVIDER=modal
"""

import os
import subprocess

import modal

REPO = "meta-models/Muse-Glimmer-30B-GGUF"
MODEL = "Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf"
MMPROJ = "mmproj-Muse-Glimmer-30B-Q4_K_M.gguf"
LLAMA_IMAGE = "ghcr.io/ggml-org/llama.cpp:server-cuda-b11960"  # pinned; same build as the Mac (brew 0.8.0)
# L40S (48 GB) has room to spare; A10 / L4 (24 GB) fit the 17 GB model + 1.4 GB vision with a smaller context.
GPU = os.environ.get("GLIMMER_GPU", "L40S")
CTX, SLOTS = (os.environ.get("GLIMMER_CTX", "32768" if GPU == "L40S" else "16384"),
              os.environ.get("GLIMMER_SLOTS", "4" if GPU == "L40S" else "2"))
WEIGHTS = "/weights"

weights = modal.Volume.from_name("medero-glimmer-weights", create_if_missing=True)
app = modal.App("medero-glimmer")

dl_image = modal.Image.debian_slim(python_version="3.11").pip_install("huggingface_hub[hf_transfer]==0.27.1") \
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
serve_image = modal.Image.from_registry(LLAMA_IMAGE, add_python="3.11").entrypoint([])


@app.function(image=dl_image, volumes={WEIGHTS: weights}, timeout=3600)
def download():
    from huggingface_hub import hf_hub_download

    for f in (MODEL, MMPROJ, "LICENSE"):
        hf_hub_download(REPO, f, local_dir=WEIGHTS)
    weights.commit()
    print("downloaded to volume:", os.listdir(WEIGHTS))


@app.function(
    image=serve_image, gpu=GPU, volumes={WEIGHTS: weights},
    secrets=[modal.Secret.from_name("medero-modal")],
    scaledown_window=300, timeout=3600, max_containers=1,  # one GPU at most: caps spend
)
@modal.concurrent(max_inputs=4)
@modal.web_server(port=8080, startup_timeout=900)
def serve():
    subprocess.Popen([
        "/app/llama-server", "-m", f"{WEIGHTS}/{MODEL}", "--mmproj", f"{WEIGHTS}/{MMPROJ}",
        "-a", "muse-glimmer-30B", "-ngl", "99", "-c", CTX, "-np", SLOTS, "--jinja",
        "--host", "0.0.0.0", "--port", "8080", "--api-key", os.environ["MEDERO_MODAL_TOKEN"],
        "--temp", "1.0", "--top-p", "0.95", "--top-k", "64",
    ])
