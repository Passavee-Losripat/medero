"""Medero API (FastAPI + WebSockets) on Modal, CPU only.

Exactly one container, always on: visit sessions live in memory (guardrail 10), so a second container would
not know a session. Secrets come from the Modal secret "medero-api" (created by scripts/modal_api_setup.sh
from .env; never committed). Deploy: bash scripts/modal_api_setup.sh
"""

import modal

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements("api/requirements.txt")
    .env({"DEMO_MODE": "1", "ROUTER_PROVIDER": "rules", "DOC_PROVIDER": "modal", "FIND_PROVIDER": "modal",
          "REASONING_EFFORT": "minimal", "MODEL_TIMEOUT_S": "15", "VERIFIER_MODEL_CHECK": "0"})
    # same layout as the repo, so the app finds data/mock and eval/results (ROOT = /srv)
    .add_local_dir("api", "/srv/api", ignore=["**/__pycache__", "**/.pytest_cache", "tests"])
    .add_local_dir("data/mock", "/srv/data/mock", ignore=[".fonts"])
    .add_local_file("eval/results/latest.md", "/srv/eval/results/latest.md")
)
app = modal.App("medero-api")


@app.function(image=image, secrets=[modal.Secret.from_name("medero-api")], cpu=0.5, memory=1024,
              min_containers=1, max_containers=1, timeout=3600)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def api():
    import sys

    sys.path.insert(0, "/srv/api")
    from app.main import app as fastapi_app

    return fastapi_app
