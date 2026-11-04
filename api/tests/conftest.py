import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["LLM_FAKE"] = "1"
os.environ["DEMO_MODE"] = "0"
os.environ.setdefault("VERIFIER_MODEL_CHECK", "1")
