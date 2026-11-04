PY ?= .venv/bin/python
ENV_FILE := $(wildcard .env)

.PHONY: setup dev api web test eval eval-offline mock-docs lint glimmer phone phone-api phone-web

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
	LLM_FAKE=1 $(PY) eval/run_eval.py --routers rules --no-rx --out eval/results/offline

mock-docs:
	$(PY) data/mock/render_mock_docs.py

lint:
	$(PY) -m compileall -q api/app eval
	cd web && npx tsc --noEmit

# Local Glimmer 4-bit via llama.cpp (OpenAI-compatible). Set GLIMMER_GGUF to the model file.
# Muse Glimmer 4-bit + vision on this Mac (llama.cpp >= b10353; `brew install llama.cpp`).
# Weights: meta-models/Muse-Glimmer-30B-GGUF (Apache-2.0), kept outside the repo.
GLIMMER_DIR ?= $(HOME)/models/glimmer
# Homebrew's bottle failed to compile Metal shaders on macOS 15.6 (bfloat constexpr error). If so, use the
# official release binary of the same build: make glimmer LLAMA_SERVER=~/models/llama-b11960/llama-b11960/llama-server
LLAMA_SERVER ?= llama-server
glimmer:
	$(LLAMA_SERVER) -m $(GLIMMER_DIR)/Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf \
	  --mmproj $(GLIMMER_DIR)/mmproj-Muse-Glimmer-30B-Q4_K_M.gguf -a muse-glimmer-30B \
	  -ngl 99 -c 32768 -np 2 --jinja --host 127.0.0.1 --port 8080 --temp 1.0 --top-p 0.95 --top-k 64

# Phone / iPad on the same Wi-Fi, over HTTPS (needed for the microphone).
# Open https://<mac-ip>:8000/health once on the device and accept the warning, then https://<mac-ip>:3000
phone:
	./scripts/lan_cert.sh
	@echo "On your phone/iPad: 1) https://$$(cat certs/ip.txt):8000/health  2) https://$$(cat certs/ip.txt):3000"
	$(MAKE) -j2 phone-api phone-web

phone-api:
	cd api && ../$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --ssl-keyfile ../certs/lan-key.pem --ssl-certfile ../certs/lan-cert.pem $(if $(ENV_FILE),--env-file ../.env,)

phone-web:
	cd web && npx next dev -H 0.0.0.0 -p 3000 --experimental-https --experimental-https-key ../certs/lan-key.pem --experimental-https-cert ../certs/lan-cert.pem
