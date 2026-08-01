"""
imaginAI — Pre-generate Voice Samples Script
Generates 4 short preview audio files (Puck, Charon, Kore, Aoede) using Gemini TTS
and saves them to frontend/public/voice-samples/ for zero-latency previewing.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.gemini_tts import generate_speech

VOICES = [
    {"name": "Puck", "gender": "male", "desc": "صوت رزين وهادئ"},
    {"name": "Charon", "gender": "male", "desc": "صوت دافئ وعميق"},
    {"name": "Kore", "gender": "female", "desc": "صوت طبيعي وحيوي"},
    {"name": "Aoede", "gender": "female", "desc": "صوت سينمائي ومميز"},
]

SAMPLE_TEXT = "مرحباً بك في imaginAI Mini، حيث تتحول أفكارك إلى فيديوهات مذهلة تلقائياً."


async def main():
    output_dir = backend_dir.parent / "frontend" / "public" / "voice-samples"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating voice samples into: {output_dir}")

    for voice in VOICES:
        v_name = voice["name"]
        out_file = str(output_dir / f"{v_name.lower()}.wav")
        print(f"Generating sample for voice '{v_name}'...")
        try:
            await generate_speech(SAMPLE_TEXT, out_file, voice=v_name)
            print(f"  ✓ Saved to {out_file}")
        except Exception as e:
            print(f"  ✗ Failed to generate for {v_name}: {e}")

        await asyncio.sleep(1)

    print("Done generating voice samples.")


if __name__ == "__main__":
    asyncio.run(main())
