"""
imaginAI — Stage 1: Script Generation via Gemini
Generates a structured JSON script from a user's idea based on duration and style.
"""

import asyncio
import json
from pathlib import Path

from google import genai  # type: ignore
from google.genai import types  # type: ignore

from app.config import get_gemini_key, get_gemini_keys, GEMINI_SCRIPT_MODEL
from app.models import GeneratedScript, ScriptScene


# ── Retry helper ─────────────────────────────────────────────────────────────

async def _retry_async(coro_fn, max_retries: int = 3, base_delay: float = 2.0):
    """Call an async function with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            print(f"[Script] Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)


# ── Duration config ──────────────────────────────────────────────────────────

DURATION_CONFIG = {
    "5_min": {
        "label": "5 دقائق",
        "scenes_range": "10 to 14",
        "total_seconds": 300,
        "min_words": 750,
    },
    "8_min": {
        "label": "8 دقائق",
        "scenes_range": "16 to 20",
        "total_seconds": 480,
        "min_words": 1200,
    },
    "10_min": {
        "label": "10 دقائق",
        "scenes_range": "20 to 25",
        "total_seconds": 600,
        "min_words": 1500,
    },
    "15_min": {
        "label": "15 دقيقة",
        "scenes_range": "30 to 40",
        "total_seconds": 900,
        "min_words": 2250,
    },
    # Legacy fallbacks
    "short": {
        "label": "5 دقائق",
        "scenes_range": "10 to 14",
        "total_seconds": 300,
        "min_words": 750,
    },
    "medium": {
        "label": "8 دقائق",
        "scenes_range": "16 to 20",
        "total_seconds": 480,
        "min_words": 1200,
    },
}

# ── Style Prompts ────────────────────────────────────────────────────────────

STYLE_PROMPTS = {
    "mystery": (
        "TONE & STYLE: Mystery / Crime. Write in a suspenseful, dramatic, atmospheric tone. "
        "Use engaging cliffhangers, intriguing questions, and mysterious narration. "
        "Keep sentences punchy and tense."
    ),
    "listicle": (
        "TONE & STYLE: Top 10 / Listicle. Structure the narration into distinct, numbered items "
        "(e.g., 'Number 1...', 'Next up...'). Each scene should focus on a clear item or countdown point. "
        "Make it engaging, fast-paced, and informative."
    ),
    "documentary": (
        "TONE & STYLE: Documentary. Write in a calm, authoritative, educational, and cinematic tone. "
        "Use insightful context, smooth transitions, and thoughtful storytelling."
    ),
    "motivational": (
        "TONE & STYLE: Motivational. Write in a high-energy, inspiring, powerful, and bold tone. "
        "Use strong action verbs, direct audience encouragement, and rising emotion."
    ),
}


# ── System prompt builder ───────────────────────────────────────────────────

GOLDEN_RULE_PROMPT = (
    "\n- GOLDEN RULE (تنبيه صارم): اكتب السكريبت لتعليق صوتي بشري طبيعي. "
    "يُمنع منعاً باتاً استخدام مقدمات إنشائية مثل (مرحباً بكم في قناتنا) أو عبارات جافة مثل (في هذا الفيديو سوف نستعرض). "
    "ابدأ بالقصة أو الهوك فوراً بدون مقدمات."
)


def _build_system_prompt(duration_cfg: dict, style: str, niche_id: str | None = None, custom_niche: str | None = None) -> str:
    style_instruction = STYLE_PROMPTS.get(style, STYLE_PROMPTS["documentary"])
    niche_prompt = ""
    overlay_instruction = ""

    if niche_id or custom_niche:
        from app.niches import find_niche_info
        info = find_niche_info(niche_id or custom_niche or "")
        if info:
            script_style = info.get("script_style", "")
            niche_prompt = f"\n- NICHE SPECIFIC INSTRUCTION ({info.get('title', custom_niche)}): {script_style}"

            overlay_type = info.get("section_overlay_type")
            if overlay_type == "numbered":
                overlay_instruction = (
                    "\n- CRITICAL SECTION OVERLAY RULE (Numbered): Each scene that starts a new point, rule, item, or section MUST include 'section_number' (integer) and 'section_title' (short Arabic title e.g. 'العنصر الأول' or point title). "
                    "For Top 10 / countdown scripts, section_number MUST count down (10 -> 9 -> 8... down to 1). For other lists, section_number MUST count up (1 -> 2 -> 3...)."
                )
            elif overlay_type == "stage":
                overlay_instruction = (
                    "\n- CRITICAL SECTION OVERLAY RULE (Stage): Each scene that introduces a new phase, stage, time jump, or zone MUST include 'section_title' (short Arabic stage title e.g. 'بعد ثانية واحدة', 'منطقة الشفق'). Do NOT include section_number."
                )

    return f"""You are a professional video script writer. Given a topic/idea from the user, write a compelling video script.

Rules:
- The video target duration is {duration_cfg['label']} ({duration_cfg['total_seconds']} seconds total).
- Split the script into {duration_cfg['scenes_range']} scenes.
- CRITICAL LENGTH RULE: Write a comprehensive, detailed script. The TOTAL word count across all scene narrations MUST BE AT LEAST {duration_cfg['min_words']} words so that the spoken narration covers the target duration of {duration_cfg['total_seconds']} seconds at a standard speech rate (~150 words per minute). Do NOT write a short summary script.
- Each scene should have:
  - "narration": the narrator text to be spoken (natural, engaging, conversational tone matching the required style)
  - "visual_keywords": 2-4 English keywords describing the ideal background footage for this scene (for stock video search)
  - "estimated_seconds": approximate duration estimate in seconds
  - "section_number": (optional) integer item/point number if this scene starts a numbered section
  - "section_title": (optional) string header title if this scene starts a new section or stage
- CRITICAL LANGUAGE RULE: The narration MUST be written in the EXACT SAME LANGUAGE as the user's idea/input prompt.
  - If the user's idea is written in Arabic, narration MUST be 100% in Arabic.
  - If the user's idea is written in English, narration MUST be 100% in English.
  - If the user's idea is written in French, German, Spanish, or any other language, narration MUST be in that SAME language.
  - NEVER translate or switch narration to a different language.
- Visual keywords should ALWAYS be in English (for stock footage search).
- {style_instruction}{niche_prompt}{overlay_instruction}{GOLDEN_RULE_PROMPT}
"""


# ── JSON Schema for structured output ────────────────────────────────────────

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "narration": {"type": "string"},
                    "visual_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "estimated_seconds": {"type": "number"},
                    "section_number": {"type": "integer"},
                    "section_title": {"type": "string"},
                },
                "required": ["narration", "visual_keywords", "estimated_seconds"],
            },
        }
    },
    "required": ["scenes"],
}


# ── Main function ────────────────────────────────────────────────────────────

async def generate_script(
    idea: str,
    duration: str,
    style: str = "documentary",
    job_dir: Path = Path("."),
    niche_id: str | None = None,
    custom_niche: str | None = None,
    additional_context: str | None = None,
) -> GeneratedScript:
    """Generate a video script from the user's idea using Gemini."""

    cfg = DURATION_CONFIG.get(duration, DURATION_CONFIG["short"])
    system = _build_system_prompt(cfg, style, niche_id=niche_id, custom_niche=custom_niche)

    user_prompt = idea
    if additional_context and additional_context.strip():
        user_prompt = (
            f"الفكرة الأساسية:\n{idea}\n\n"
            f"معلومات إضافية ونقاط هامة يجب الاعتماد عليها والتركيز عليها بالفيديو:\n{additional_context.strip()}"
        )

    keys = get_gemini_keys()
    raw = None
    last_error = None

    for idx, key in enumerate(keys):
        try:
            print(f"[Gemini Script] Trying API key {idx + 1}/{len(keys)}...")
            client = genai.Client(api_key=key)

            async def _call():
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=GEMINI_SCRIPT_MODEL,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        response_mime_type="application/json",
                        response_schema=SCRIPT_SCHEMA,
                        temperature=0.9,
                    ),
                )
                return response.text

            raw = await _retry_async(_call)
            if raw:
                break
        except Exception as err:
            last_error = err
            print(f"[Gemini Script WARNING] Key {idx + 1} failed ({err}). Trying failover key...")

    if not raw:
        raise RuntimeError(f"All Gemini API keys failed for script generation! Last error: {last_error}")

    data = json.loads(raw)

    # Validate and parse
    script = GeneratedScript(
        scenes=[ScriptScene(**s) for s in data["scenes"]]
    )

    # Save to job directory
    script_file = job_dir / "script.json"
    script_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"[Script] Generated {len(script.scenes)} scenes (style={style}), saved to {script_file}")
    return script


async def expand_script_scenes(
    idea: str,
    needed_seconds: float,
    current_scenes_count: int,
    style: str = "documentary",
    job_dir: Path = Path("."),
) -> list[ScriptScene]:
    """Generate additional scenes to cover remaining needed seconds without rewriting existing script."""
    needed_words = max(150, int((needed_seconds / 60.0) * 150))
    style_instruction = STYLE_PROMPTS.get(style, STYLE_PROMPTS["documentary"])

    system = f"""You are a professional video script writer extending an existing script on the topic/idea.
Rules:
- Generate ONLY NEW ADDITIONAL scenes (starting from Scene #{current_scenes_count + 1}).
- Do NOT rewrite or summarize past scenes.
- The additional narration MUST cover at least {needed_words} total words ({needed_seconds:.0f} seconds spoken duration).
- The narration MUST be written in the EXACT SAME LANGUAGE as the user's idea.
- Visual keywords must be in English.
- {style_instruction}
"""

    keys = get_gemini_keys()
    raw = None
    last_error = None

    prompt = f"Topic/Idea: {idea}\n\nPlease generate additional scenes to extend the narration for another {needed_seconds:.0f} seconds."

    for idx, key in enumerate(keys):
        try:
            client = genai.Client(api_key=key)
            async def _call():
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=GEMINI_SCRIPT_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        response_mime_type="application/json",
                        response_schema=SCRIPT_SCHEMA,
                        temperature=0.9,
                    ),
                )
                return response.text
            raw = await _retry_async(_call)
            if raw:
                break
        except Exception as err:
            last_error = err

    if not raw:
        raise RuntimeError(f"Failed to expand script scenes: {last_error}")

    data = json.loads(raw)
    new_scenes = [ScriptScene(**s) for s in data["scenes"]]
    print(f"[Script Expansion] Added {len(new_scenes)} extra scenes for {needed_seconds:.1f}s gap")
    return new_scenes
