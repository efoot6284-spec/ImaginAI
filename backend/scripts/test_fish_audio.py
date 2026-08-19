"""
Test Fish Audio List Voices integration independently.
"""
import sys
from pathlib import Path

# Add backend dir to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.fish_audio_tts import fetch_fish_audio_voices

def main():
    print("Testing Fish Audio API List Voices...")
    voices = fetch_fish_audio_voices()
    print(f"Total voices retrieved: {len(voices)}")
    for v in voices[:10]:
        print(f" - ID: {v['id']} | Name: {v['name']} | Gender: {v['gender']} | Lang: {v['lang']}")

if __name__ == "__main__":
    main()
