"""
imaginAI — Fish Audio TTS Service
Integrates with Fish Audio API (https://api.fish.audio) for voice listing and text-to-speech generation.
"""

import os
import tempfile
import httpx # type: ignore
from pathlib import Path
from app.config import get_fish_audio_key
from app.services.gemini_tts import _clean_text, _convert_to_wav, _save_wav

FISH_AUDIO_BASE_URL = "https://api.fish.audio/v1"


def fetch_fish_audio_voices() -> list[dict]:
    """
    Fetch available TTS voices/models from Fish Audio API.
    Fetches user models (if API key provided) and public market models.
    """
    api_key = None
    try:
        api_key = get_fish_audio_key()
    except Exception:
        pass

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    voices = []
    seen_ids = set()

    # Query endpoints: user's own models (if key available) + public featured models
    endpoints = []
    if api_key:
        endpoints.append("https://api.fish.audio/model?page_size=50&self=true")
    endpoints.append("https://api.fish.audio/model?page_size=50")

    with httpx.Client(timeout=15.0) as client:
        for url in endpoints:
            try:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("items", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    for item in items:
                        model_id = item.get("_id") or item.get("id")
                        title = item.get("title") or item.get("name")
                        if not model_id or not title:
                            continue
                        if model_id in seen_ids:
                            continue
                        seen_ids.add(model_id)

                        langs = item.get("languages", []) or []
                        tags = item.get("tags", []) or []
                        tags_lower = [str(t).lower() for t in tags]

                        lang_str = "العربية / English"
                        if any(l in ["ar", "ara"] for l in langs) or "arabic" in tags_lower:
                            lang_str = "العربية"
                        elif any(l in ["en", "eng"] for l in langs) or "english" in tags_lower:
                            lang_str = "English"
                        elif any(l in ["ja", "jpn"] for l in langs) or "japanese" in tags_lower:
                            lang_str = "Japanese"
                        elif any(l in ["zh", "zho"] for l in langs) or "chinese" in tags_lower:
                            lang_str = "Chinese"

                        gender = "neutral"
                        title_lower = str(title).lower()
                        if "male" in tags_lower or "boy" in tags_lower or "man" in title_lower:
                            gender = "male"
                        elif "female" in tags_lower or "girl" in tags_lower or "woman" in title_lower:
                            gender = "female"

                        desc = item.get("description") or f"صوت Fish Audio • {title}"
                        if len(desc) > 120:
                            desc = desc[:117] + "..."

                        voices.append({
                            "id": str(model_id),
                            "name": str(title),
                            "gender": gender,
                            "lang": lang_str,
                            "desc": desc,
                        })
            except Exception as err:
                print(f"[Fish Audio Warning] Error calling {url}: {err}")

    print(f"[Fish Audio] Retrieved {len(voices)} voices from API.")
    return voices



async def generate_speech_fish_audio(text: str, output_path: str, voice_id: str) -> str:
    """
    Generate audio via Fish Audio REST API (POST /v1/tts) using specific voice_id (reference_id).
    Saves and converts result to WAV at output_path.
    """
    cleaned_text = _clean_text(text)
    if not cleaned_text:
        raise ValueError("Text cannot be empty for Fish Audio TTS")

    api_key = get_fish_audio_key() # Will raise RuntimeError if missing

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "model": "s2.1-pro-free",
    }

    payload = {
        "text": cleaned_text,
        "format": "mp3",
    }
    if voice_id and voice_id != "default":
        payload["reference_id"] = voice_id

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            f"{FISH_AUDIO_BASE_URL}/tts",
            json=payload,
            headers=headers,
        )

        if response.status_code != 200:
            err_detail = response.text[:200]
            raise RuntimeError(f"Fish Audio API error (HTTP {response.status_code}): {err_detail}")

        audio_bytes = response.content
        if not audio_bytes or len(audio_bytes) < 100:
            raise RuntimeError("Fish Audio API returned invalid empty audio payload")

    # Write temp MP3 file and convert to 24kHz WAV
    temp_mp3 = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    try:
        with open(temp_mp3, "wb") as f:
            f.write(audio_bytes)
        _convert_to_wav(temp_mp3, output_path)
        return output_path
    finally:
        if os.path.exists(temp_mp3):
            try:
                os.remove(temp_mp3)
            except Exception:
                pass


async def clone_voice_fish_audio(audio_bytes: bytes, filename: str, voice_name: str) -> str:
    """
    Submit an audio sample to Fish Audio API (POST https://api.fish.audio/model)
    to create a custom cloned voice model. Returns the created model's ID (fish_voice_id).
    """
    if not audio_bytes or len(audio_bytes) < 1000:
        raise ValueError("تعدينة الملف الصوتي قصيرة جداً أو تالفة. يرجى اختيار ملف أو تسجيل بصوت واضح بين 10 إلى 30 ثانية.")

    api_key = get_fish_audio_key() # Will raise error if key missing

    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    files = {
        "voices": (filename or "voice_sample.wav", audio_bytes, "audio/mpeg" if filename.endswith(".mp3") else "audio/wav"),
    }
    data = {
        "title": voice_name or "صوت مخصص",
        "type": "tts",
        "train_mode": "fast",
        "visibility": "private",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.fish.audio/model",
            data=data,
            files=files,
            headers=headers,
        )

        if response.status_code not in (200, 201):
            err_text = response.text[:250]
            raise RuntimeError(f"خطأ من API استنساخ الصوت في Fish Audio (HTTP {response.status_code}): {err_text}")

        res_json = response.json()
        fish_voice_id = res_json.get("_id") or res_json.get("id")
        if not fish_voice_id:
            raise RuntimeError(f"لم يتم إرجاع المعرف (fish_voice_id) بنجاح: {res_json}")

        print(f"[Fish Audio Clone SUCCESS] Created cloned model ID: {fish_voice_id} for '{voice_name}'")
        return str(fish_voice_id)

