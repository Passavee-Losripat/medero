#!/usr/bin/env bash
# One-time Modal setup for Muse Glimmer (run by the developer, not by an agent):
#   1. creates a random access key, stores it as the Modal secret "medero-modal" and in .env (git-ignored)
#   2. downloads the Glimmer GGUF weights into a Modal volume (inside Modal's network)
#   3. deploys the llama.cpp server (1 GPU max, scales to zero after 5 idle minutes)
#   4. writes MODAL_LLM_BASE / MODAL_LLM_MODEL to .env
# The key is never printed.
set -euo pipefail
cd "$(dirname "$0")/.."
MODAL=.venv/bin/modal

KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
$MODAL secret create medero-modal MEDERO_MODAL_TOKEN="$KEY" --force >/dev/null
touch .env
grep -v -E '^(MODAL_LLM_KEY|MODAL_LLM_BASE|MODAL_LLM_MODEL)=' .env > .env.tmp || true
echo "MODAL_LLM_KEY=$KEY" >> .env.tmp
echo "secret created"

$MODAL run infra/modal_glimmer.py::download
OUT=$($MODAL deploy infra/modal_glimmer.py 2>&1 | tee /dev/stderr)
URL=$(echo "$OUT" | grep -oE 'https://[a-zA-Z0-9.-]+\.modal\.run' | head -1)
if [ -z "$URL" ]; then echo "could not find the endpoint URL in the deploy output"; mv .env.tmp .env; exit 1; fi
echo "MODAL_LLM_BASE=$URL/v1" >> .env.tmp
echo "MODAL_LLM_MODEL=muse-glimmer-30B" >> .env.tmp
mv .env.tmp .env
echo "deployed: $URL  (written to .env)"
