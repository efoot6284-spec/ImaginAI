"""
imaginAI — Stage 4: Captions via Groq Whisper
Transcribes audio files and extracts word-level timestamps.
"""

import asyncio
import json
from pathlib import Path

import httpx

from app.config import get_groq_key, GROQ_WHISPER_MODEL
from app.models import WordTimestamp


# ── Retry helper ─────────────────────────────────────────────────────────────

async def _retry_async(coro_fn, max_retries: int = 3, base_delay: float = 2.0):
    for attempt in range(max_retries):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            print(f"[Captions] Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)


# ── Fallback timestamp generator ─────────────────────────────────────────────

def _generate_estimated_word_timestamps(audio_path: str, text: str = "") -> list[WordTimestamp]:
    """Fallback: estimate word timestamps linearly based on audio file duration."""
    import wave
    duration = 5.0
    try:
        with wave.open(audio_path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration = frames / float(rate)
    except Exception:
        pass

    words_raw = [w.strip() for w in text.split() if w.strip()]
    if not words_raw:
        words_raw = ["..." for _ in range(5)]

    time_per_word = duration / len(words_raw)
    result = []
    curr = 0.0
    for w in words_raw:
        end_time = curr + time_per_word
        result.append(WordTimestamp(word=w, start=round(curr, 2), end=round(end_time, 2)))
        curr = end_time
    return result


# ── Single file transcription ───────────────────────────────────────────────

async def transcribe_audio(audio_path: str, narration_text: str = "") -> list[WordTimestamp]:
    """Transcribe a single WAV file using Groq Whisper, falling back to estimation if API fails (e.g. 401 Unauthorized)."""

    async def _call():
        async with httpx.AsyncClient() as client:
            with open(audio_path, "rb") as f:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {get_groq_key()}"},
                    files={"file": (Path(audio_path).name, f, "audio/wav")},
                    data={
                        "model": GROQ_WHISPER_MODEL,
                        "response_format": "verbose_json",
                        "timestamp_granularities[]": "word",
                    },
                    timeout=60,
                )
                resp.raise_for_status()
                return resp.json()

    try:
        data = await _retry_async(_call, max_retries=2, base_delay=1.0)
        # Extract word-level timestamps
        words = []
        if isinstance(data, dict):
            for w in data.get("words", []):
                words.append(WordTimestamp(
                    word=w["word"],
                    start=w["start"],
                    end=w["end"],
                ))
            if words:
                return words
    except Exception as e:
        print(f"[Captions] Groq Whisper API error ({e}). Using estimated timestamp fallback...")

    return _generate_estimated_word_timestamps(audio_path, narration_text)


# ── Group words into subtitle lines ─────────────────────────────────────────

def group_words_into_lines(words: list[WordTimestamp], max_words_per_line: int = 5) -> list[dict]:
    """
    Group words into subtitle lines of max N words.
    Returns list of {"text": str, "start": float, "end": float}.
    """
    if not words:
        return []

    lines = []
    for i in range(0, len(words), max_words_per_line):
        chunk = words[i:i + max_words_per_line]
        lines.append({
            "text": " ".join(w.word for w in chunk),
            "start": chunk[0].start,
            "end": chunk[-1].end,
        })
    return lines


# ── All scenes ──────────────────────────────────────────────────────────────

async def transcribe_all(
    audio_paths: list[str],
    job_dir: Path,
    scenes: list | None = None,
) -> list[list[dict]]:
    """
    Transcribe all audio files, return grouped subtitle lines per scene.
    Also saves caption data to job_dir/captions/.
    """

    captions_dir = job_dir / "captions"
    captions_dir.mkdir(exist_ok=True)

    all_captions = []

    for i, audio_path in enumerate(audio_paths):
        print(f"[Captions] Transcribing scene {i}...")
        narration = scenes[i].narration if (scenes and i < len(scenes)) else ""
        words = await transcribe_audio(audio_path, narration_text=narration)
        lines = group_words_into_lines(words)

        # Save caption data
        caption_file = captions_dir / f"scene_{i}.json"
        caption_file.write_text(
            json.dumps(lines, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        all_captions.append(lines)

        # Small delay between API calls
        if i < len(audio_paths) - 1:
            await asyncio.sleep(0.3)

    print(f"[Captions] Transcribed {len(all_captions)} scenes")
    return all_captions

