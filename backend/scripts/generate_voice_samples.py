"""
imaginAI — Static Voice Sample Generator Script
Generates static audio samples (5-8 seconds) for all available voices of Gemini and Fish Audio.
Outputs to: frontend/public/voice-samples/{provider}/{voice_id}.mp3
"""

import asyncio
import os
import sys
import subprocess
import tempfile
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add backend directory to sys.path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import VOICE_PROVIDERS
from app.services.gemini_tts import generate_speech
from app.services.fish_audio_tts import fetch_fish_audio_voices, generate_speech_fish_audio

SAMPLE_TEXT_AR = "مرحباً بك! هذه عينة صوتية لتجربة نبرة الصوت وسرعة الكلام في منصة إيماجن أي آي."
SAMPLE_TEXT_EN = "Hello! This is a sample audio preview to demonstrate the voice tone and speech rate in ImaginAI."

FRONTEND_PUBLIC_DIR = backend_dir.parent / "frontend" / "public" / "voice-samples"


def convert_wav_to_mp3(wav_path: str, mp3_path: str):
    """Convert WAV file to MP3 using ffmpeg."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame", "-qscale:a", "2", mp3_path],
        capture_output=True,
        check=True,
    )


async def generate_all_samples():
    FRONTEND_PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[Sample Generator] Saving static voice samples to: {FRONTEND_PUBLIC_DIR}")

    # 1. Gemini Voices
    gemini_dir = FRONTEND_PUBLIC_DIR / "gemini"
    gemini_dir.mkdir(exist_ok=True)

    gemini_provider = next((p for p in VOICE_PROVIDERS if p["provider"] == "gemini"), None)
    if gemini_provider and isinstance(gemini_provider, dict):
        voices_list = gemini_provider.get("voices", [])
        for voice in voices_list:
            if isinstance(voice, dict):
                voice_id = voice["id"]
                safe_id = voice_id.replace("/", "_").replace("\\", "_")
                out_mp3 = gemini_dir / f"{safe_id}.mp3"
                
                if out_mp3.exists() and out_mp3.stat().st_size > 1000:
                    print(f" [Gemini] Sample already exists for {voice_id}, skipping.")
                    continue

                print(f" [Gemini] Generating sample for voice: {voice_id}...")
                temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
                try:
                    text = SAMPLE_TEXT_EN if voice.get("lang") == "English" else SAMPLE_TEXT_AR
                    await generate_speech(text, temp_wav, voice=voice_id, provider="gemini")
                    convert_wav_to_mp3(temp_wav, str(out_mp3))
                    print(f" ✓ Generated {out_mp3.name}")
                except Exception as e:
                    print(f" ✗ Error generating Gemini sample for {voice_id}: {e}")
                finally:
                    if os.path.exists(temp_wav):
                        try:
                            os.remove(temp_wav)
                        except Exception:
                            pass


    # 2. Fish Audio Voices
    fish_dir = FRONTEND_PUBLIC_DIR / "fish-audio"
    fish_dir.mkdir(exist_ok=True)

    fish_voices = fetch_fish_audio_voices()
    if not fish_voices:
        fish_voices = [{
            "id": "default",
            "name": "Default Voice",
            "lang": "العربية",
        }]

    for voice in fish_voices:
        voice_id = voice["id"]
        safe_id = voice_id.replace("/", "_").replace("\\", "_")
        out_mp3 = fish_dir / f"{safe_id}.mp3"

        if out_mp3.exists() and out_mp3.stat().st_size > 1000:
            print(f" [Fish Audio] Sample already exists for {voice_id}, skipping.")
            continue

        print(f" [Fish Audio] Generating sample for voice: {voice_id}...")
        temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        try:
            text = SAMPLE_TEXT_EN if voice.get("lang") == "English" else SAMPLE_TEXT_AR
            await generate_speech_fish_audio(text, temp_wav, voice_id=voice_id)
            convert_wav_to_mp3(temp_wav, str(out_mp3))
            print(f" ✓ Generated {out_mp3.name}")
        except Exception as e:
            print(f" ✗ Warning: Could not generate Fish Audio sample for {voice_id} ({e})")
        finally:
            if os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except Exception:
                    pass

    print("[Sample Generator] Finished processing all static voice samples!")


if __name__ == "__main__":
    asyncio.run(generate_all_samples())
