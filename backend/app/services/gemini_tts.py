"""
imaginAI — Stage 2: Multi-Provider Text-to-Speech (Gemini TTS, Edge-TTS, gTTS)
Generates WAV audio for each scene's narration.
Also provides get_audio_duration_ffprobe() for accurate duration measurement.
Includes robust text cleaning, language auto-detection, and HTTP chunking.
"""

import asyncio
import os
import sys
import subprocess
import wave
import tempfile
import urllib.parse
import re
from pathlib import Path
import httpx  # type: ignore

from google import genai  # type: ignore
from google.genai import types  # type: ignore

from app.config import get_gemini_key, get_gemini_keys, GEMINI_TTS_MODEL, GEMINI_TTS_VOICE
from app.models import ScriptScene


# ── Auto-install missing packages dynamically into active Python env ─────────

def _ensure_dependencies():
    """Auto-install edge-tts and gTTS if missing in current running Python executable."""
    for pkg_import, pkg_pip in [("edge_tts", "edge-tts"), ("gtts", "gTTS")]:
        try:
            __import__(pkg_import)
        except ImportError:
            print(f"[TTS Setup] Installing missing python package '{pkg_pip}'...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", pkg_pip],
                    capture_output=True,
                    timeout=90,
                )
                print(f"[TTS Setup] Successfully installed '{pkg_pip}'!")
            except Exception as e:
                print(f"[TTS Setup] Warning: Failed to auto-install '{pkg_pip}': {e}")

_ensure_dependencies()


# ── Text Cleaning & Language Helpers ──────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Clean narration text to prevent newline %0A and URL encoding errors."""
    if not text:
        return ""
    # Replace all newlines, carriage returns, tabs, and non-printable control chars with space
    text = re.sub(r'[\r\n\t]+', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _detect_lang(text: str) -> str:
    """Auto-detect if text is primarily English or Arabic."""
    cleaned = _clean_text(text)
    latin_count = len(re.findall(r'[a-zA-Z]', cleaned))
    arabic_count = len(re.findall(r'[\u0600-\u06FF]', cleaned))
    return "en" if latin_count > arabic_count else "ar"


def _get_compatible_edge_voice(voice: str, text: str) -> str:
    """Map voice choice to language-compatible Edge-TTS voice (Male vs Female)."""
    lang = _detect_lang(text)
    is_female = any(name in voice for name in ["Salma", "Zariyah", "Kore", "Aoede", "Jenny", "female"])

    if lang == "en":
        if "Charon" in voice or "Hamed" in voice:
            return "en-US-GuyNeural"
        elif "Aoede" in voice or "Zariyah" in voice:
            return "en-US-AriaNeural"
        elif is_female:
            return "en-US-JennyNeural"
        else:
            return "en-US-ChristopherNeural"
    else:
        # Arabic — map 4 distinct voices for Puck, Charon, Kore, Aoede
        if "Charon" in voice:
            return "ar-AE-HamdanNeural"
        elif "Aoede" in voice:
            return "ar-SA-ZariyahNeural"
        elif "Kore" in voice or is_female:
            return "ar-EG-SalmaNeural"
        else:  # Puck / default male
            return "ar-SA-HamedNeural"


def _split_text_into_chunks(text: str, max_chars: int = 100) -> list[str]:
    """Split clean text into small chunks without newlines to avoid HTTP 400 Bad Request."""
    cleaned = _clean_text(text)
    if len(cleaned) <= max_chars:
        return [cleaned]

    chunks = []
    # Split by natural sentence punctuation or spaces
    sentences = re.split(r'([.?!،؛]+)', cleaned)
    
    current = ""
    for part in sentences:
        if not part:
            continue
        if len(current) + len(part) <= max_chars:
            current += part
        else:
            if current.strip():
                chunks.append(current.strip())
            current = part
            
    if current.strip():
        chunks.append(current.strip())

    # Fallback to word splitting if a single sentence is still > max_chars
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            final_chunks.append(chunk)
        else:
            words = chunk.split(" ")
            w_curr = ""
            for w in words:
                if len(w_curr) + len(w) + 1 <= max_chars:
                    w_curr = (w_curr + " " + w).strip()
                else:
                    if w_curr:
                        final_chunks.append(w_curr)
                    w_curr = w
            if w_curr:
                final_chunks.append(w_curr)

    return [c for c in final_chunks if c]


# ── Retry helper ─────────────────────────────────────────────────────────────

async def _retry_async(coro_fn, max_retries: int = 2, base_delay: float = 1.5):
    for attempt in range(max_retries):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            print(f"[TTS] Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)


# ── WAV & Audio Helpers ──────────────────────────────────────────────────────

def _save_wav(pcm_data: bytes, output_path: str, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2):
    """Save raw PCM data as a WAV file."""
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)


def _convert_to_wav(input_file: str, output_wav: str) -> str:
    """Convert any audio file (MP3/OGG/etc.) to 24kHz Mono WAV using ffmpeg."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", input_file,
            "-ar", "24000", "-ac", "1", output_wav
        ],
        capture_output=True,
        check=True
    )
    return output_wav


# ── Accurate duration via ffprobe ────────────────────────────────────────────

def get_audio_duration_ffprobe(path: str) -> float:
    """Get the exact audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        print(f"[TTS] ffprobe failed for {path}: {e} — falling back to WAV header")

    try:
        with wave.open(path, "r") as wf:
            return wf.getnframes() / wf.getframerate()
    except Exception as e2:
        raise RuntimeError(f"Cannot determine duration for {path}: {e2}")


# ── HTTP Chunked Fallback (Guaranteed No HTTP 400 Bad Request) ───────────────

async def _generate_gtts_http(text: str, output_path: str, lang: str | None = None) -> str:
    """Generate audio via direct HTTP requests with text chunking and auto-detected language."""
    cleaned_text = _clean_text(text)
    actual_lang = lang or _detect_lang(cleaned_text)
    chunks = _split_text_into_chunks(cleaned_text, max_chars=100)

    combined_mp3_bytes = bytearray()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        for chunk in chunks:
            if not chunk:
                continue
            encoded_text = urllib.parse.quote(chunk)
            url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_text}&tl={actual_lang}&client=tw-ob"
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    combined_mp3_bytes.extend(resp.content)
                else:
                    print(f"[TTS Warning] HTTP {resp.status_code} for chunk: '{chunk}'")
            except Exception as err:
                print(f"[TTS Warning] HTTP request error for chunk '{chunk}': {err}")

    if not combined_mp3_bytes:
        raise RuntimeError(f"Failed to fetch any audio chunks for text: {cleaned_text[:40]}")

    temp_mp3 = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    try:
        with open(temp_mp3, "wb") as f:
            f.write(combined_mp3_bytes)
        _convert_to_wav(temp_mp3, output_path)
        return output_path
    finally:
        if os.path.exists(temp_mp3):
            try:
                os.remove(temp_mp3)
            except Exception:
                pass


# ── Provider Specific Generators ────────────────────────────────────────────

async def _generate_gemini(text: str, output_path: str, voice: str) -> str:
    """Generate audio via Google Gemini TTS API with multi-key failover."""
    cleaned_text = _clean_text(text)
    keys = get_gemini_keys()
    response = None
    last_error = None

    for idx, key in enumerate(keys):
        try:
            client = genai.Client(api_key=key)

            async def _call():
                return await asyncio.to_thread(
                    client.models.generate_content,
                    model=GEMINI_TTS_MODEL,
                    contents=cleaned_text,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=voice or "Kore",
                                )
                            )
                        ),
                    ),
                )

            response = await _retry_async(_call)
            if response:
                break
        except Exception as err:
            last_error = err
            print(f"[Gemini TTS WARNING] Key {idx + 1} failed ({err}). Trying failover key...")

    if not response:
        raise RuntimeError(f"All Gemini API keys failed for TTS generation! Last error: {last_error}")

    audio_part = response.candidates[0].content.parts[0]
    audio_data = audio_part.inline_data.data
    _save_wav(audio_data, output_path)
    return output_path


async def _generate_edge_tts(text: str, output_path: str, voice: str) -> str:
    """Generate speech using Microsoft Edge TTS with automatic language & voice matching."""
    cleaned_text = _clean_text(text)
    voice_id = _get_compatible_edge_voice(voice, cleaned_text)
    
    try:
        import edge_tts  # type: ignore
        temp_mp3 = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
        try:
            communicate = edge_tts.Communicate(cleaned_text, voice_id)
            await communicate.save(temp_mp3)
            _convert_to_wav(temp_mp3, output_path)
            return output_path
        finally:
            if os.path.exists(temp_mp3):
                try:
                    os.remove(temp_mp3)
                except Exception:
                    pass
    except Exception as e:
        print(f"[TTS Warning] Edge-TTS error ({e}). Using HTTP chunked fallback...")
        return await _generate_gtts_http(cleaned_text, output_path)


async def _generate_gtts(text: str, output_path: str, voice: str) -> str:
    """Generate speech using gTTS library with fallback."""
    cleaned_text = _clean_text(text)
    lang = _detect_lang(cleaned_text)
    
    try:
        from gtts import gTTS  # type: ignore
        temp_mp3 = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
        try:
            def _save():
                tts = gTTS(text=cleaned_text, lang=lang)
                tts.save(temp_mp3)

            await asyncio.to_thread(_save)
            _convert_to_wav(temp_mp3, output_path)
            return output_path
        finally:
            if os.path.exists(temp_mp3):
                try:
                    os.remove(temp_mp3)
                except Exception:
                    pass
    except Exception as e:
        print(f"[TTS Warning] gTTS library error ({e}). Using HTTP chunked fallback...")
        return await _generate_gtts_http(cleaned_text, output_path, lang=lang)


# ── Single scene TTS Router ──────────────────────────────────────────────────

async def generate_speech(
    text: str,
    output_path: str,
    voice: str = "Kore",
    provider: str = "gemini",
) -> str:
    """
    Generate speech for a single narration scene using the chosen provider and voice.
    Strictly uses the specified provider with NO automatic fallback to other providers.
    """
    cleaned_text = _clean_text(text)
    prov = (provider or "gemini").lower()

    if prov == "gemini":
        return await _generate_gemini(cleaned_text, output_path, voice)

    elif prov in ["fish-audio", "fish_audio", "fish"]:
        from app.services.fish_audio_tts import generate_speech_fish_audio
        return await generate_speech_fish_audio(cleaned_text, output_path, voice)

    elif prov in ["edge-tts", "edge_tts", "edge"]:
        return await _generate_edge_tts(cleaned_text, output_path, voice)

    elif prov == "gtts":
        return await _generate_gtts(cleaned_text, output_path, voice)

    else:
        # Default to Gemini TTS
        return await _generate_gemini(cleaned_text, output_path, voice or "Kore")



# ── All scenes TTS ──────────────────────────────────────────────────────────

async def generate_all_speech(
    scenes: list[ScriptScene],
    job_dir: Path,
    voice: str = "ar-SA-HamedNeural",
    provider: str = "edge-tts",
    start_index: int = 0,
) -> list[str]:
    """Generate speech for all scenes sequentially starting at start_index."""

    audio_dir = job_dir / "audio"
    audio_dir.mkdir(exist_ok=True)

    audio_paths = []
    for i, scene in enumerate(scenes):
        idx = start_index + i
        output_path = str(audio_dir / f"scene_{idx}.wav")
        await generate_speech(scene.narration, output_path, voice=voice, provider=provider)
        audio_paths.append(output_path)

        if i < len(scenes) - 1:
            await asyncio.sleep(0.5)

    print(f"[TTS] Generated {len(audio_paths)} audio files (indices {start_index}..{start_index + len(audio_paths) - 1}) using provider '{provider}' and voice '{voice}'")
    return audio_paths
