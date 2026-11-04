PY ?= .venv/bin/python
ENV_FILE := $(wildcard .env)

.PHONY: setup dev api web test eval eval-offline mock-docs lint glimmer

setup:
	python3.11 -m venv .venv && .venv/bin/pip install -r api/requirements.txt Pillow
	cd web && npm install

api:
	cd api && ../$(PY) -m uvicorn app.main:app --reload --port 8000 $(if $(ENV_FILE),--env-file ../.env,)

web:
	cd web && npm run dev

dev:
	$(MAKE) -j2 api web

test:
	cd api && ../$(PY) -m pytest -q -p no:warnings
	cd web && npx tsc --noEmit

# Needs MODEL_API_KEY in .env. Add ROUTERS=rules,spark,local to include local Glimmer.
ROUTERS ?= rules,spark
eval:
	set -a; [ -f .env ] && . ./.env; set +a; $(PY) eval/run_eval.py --routers $(ROUTERS)

# Offline: rules baseline + claim matcher only (no model calls).
eval-offline:
	LLM_FAKE=1 $(PY) eval/run_eval.py --routers rules --no-rx

mock-docs:
	$(PY) data/mock/render_mock_docs.py

lint:
	$(PY) -m compileall -q api/app eval
	cd web && npx tsc --noEmit

# Local Glimmer 4-bit via llama.cpp (OpenAI-compatible). Set GLIMMER_GGUF to the model file.
glimmer:
	llama-server -m $(GLIMMER_GGUF) --port 8080 -c 8192 --jinja
