"""
test_models.py — List all Gemini models available for this API key.
Groups them by: generateContent support vs TTS/speech support.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

# Load .env
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY not found in .env")

client = genai.Client(api_key=api_key)

print("=" * 70)
print("  Fetching all models visible to this API key...")
print("=" * 70)

generate_models = []
tts_models = []

for model in client.models.list():
    name = model.name
    methods = getattr(model, "supported_actions", None) or getattr(model, "supported_generation_methods", None) or []

    if "generateContent" in methods:
        generate_models.append((name, methods))
    if any(m in methods for m in ("generateSpeech", "tts")):
        tts_models.append((name, methods))

# ── Print generateContent models ─────────────────────────────────────
print(f"\n{'=' * 70}")
print(f"  MODELS supporting generateContent  ({len(generate_models)} found)")
print(f"{'=' * 70}")
for name, methods in sorted(generate_models):
    print(f"  {name}")
    print(f"      methods: {methods}")

# ── Print TTS models ─────────────────────────────────────────────────
print(f"\n{'=' * 70}")
print(f"  MODELS supporting TTS / generateSpeech  ({len(tts_models)} found)")
print(f"{'=' * 70}")
if tts_models:
    for name, methods in sorted(tts_models):
        print(f"  {name}")
        print(f"      methods: {methods}")
else:
    print("  (none found — TTS method name may differ, see raw dump below)")

# ── Raw dump of ALL models for reference ─────────────────────────────
print(f"\n{'=' * 70}")
print(f"  RAW: ALL models (for debugging)")
print(f"{'=' * 70}")
for model in client.models.list():
    name = model.name
    methods = getattr(model, "supported_actions", None) or getattr(model, "supported_generation_methods", None) or []
    print(f"  {name}  →  {methods}")
