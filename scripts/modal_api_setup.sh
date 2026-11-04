#!/usr/bin/env bash
# Deploy the Medero API on Modal (run by the developer). Copies the 4 keys from .env into the Modal secret
# "medero-api" without printing them, deploys infra/modal_api.py, and prints the public URL.
set -euo pipefail
cd "$(dirname "$0")/.."
MODAL=.venv/bin/modal
args=()
while IFS= read -r line; do args+=("$line"); done < <(grep -E '^(MODEL_API_KEY|MODAL_LLM_BASE|MODAL_LLM_KEY|MODAL_LLM_MODEL)=' .env)
[ ${#args[@]} -eq 4 ] || { echo "expected 4 keys in .env, found ${#args[@]}"; exit 1; }
$MODAL secret create medero-api "${args[@]}" --force >/dev/null
echo "secret medero-api updated (4 keys)"
$MODAL deploy infra/modal_api.py
