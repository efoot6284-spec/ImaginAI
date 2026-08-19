"""
imaginAI — Dynamic Script Section Analyzer
Uses Gemini 3.6 Flash to analyze generated scripts for remaining niches (non-predefined 6 niches).
Determines if script contains clear sections/stages and proposes section titles and numbers.
"""

import json
import os
from google import genai
from google.genai import types

from app.config import get_gemini_key, GEMINI_SCRIPT_MODEL


ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "should_split": {"type": "boolean"},
        "suggested_overlay_type": {"type": "string", "enum": ["numbered", "stage"]},
        "reasoning": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scene_index": {"type": "integer"},
                    "section_number": {"type": "integer"},
                    "section_title": {"type": "string"},
                },
                "required": ["scene_index", "section_title"],
            },
        },
    },
    "required": ["should_split", "reasoning"],
}


async def analyze_script_sections(scenes: list[dict], idea: str = "") -> dict:
    """
    Analyze script scenes to determine if section titles/numbers are appropriate.
    Returns dict matching ANALYSIS_SCHEMA.
    """
    try:
        api_key = get_gemini_key()
    except Exception as e:
        print(f"[Section Analyzer Warning] Gemini API key issue: {e}. Skipping dynamic analysis.")
        return {"should_split": False, "reasoning": "No Gemini API key"}

    client = genai.Client(api_key=api_key)

    formatted_scenes = []
    for idx, sc in enumerate(scenes):
        narration = sc.get("narration", "") if isinstance(sc, dict) else getattr(sc, "narration", "")
        formatted_scenes.append(f"Scene #{idx}: {narration}")

    full_text = "\n".join(formatted_scenes)

    prompt = f"""راجع هذا السكريبت الخاص بفيديو ذكاء اصطناعي:

فكرة الفيديو: {idea}

مشاهد السكريبت:
{full_text}

المطلوب:
1. حلل النص: هل يحتوي هذا السكريبت على أقسام، خطوات، عناصر، قواعد، أو مراحل متعددة واضحة ومستقلة يستفيد الفيديو جداً من إظهار عنوان أو رقم لها قبل كل قسم؟ (مثال: قائمة بنصائح، خطوات عملية متتالية، أو مراقبة مراحل).
2. إذا كان الجواب نعم (should_split = true):
   - حدد نوع التراكب المناسب: 'numbered' (إذا كانت نقاط/قواعد/عناصر ترقيم) أو 'stage' (إذا كانت مراحل/تنقلات زمنية).
   - حدد رقم المشهد (scene_index) الذي يبدأ عنده كل قسم جديد، مع عنوان قصير جداً (2-4 كلمات بالعربية) ورقم القسم إن وجد.
3. إذا كان السكريبت قصة متصلة وسردية واحدة بدون نقاط مستقيمة، أرجع should_split = false.

أجب بصيغة JSON فقط مطابقة للهيكل المطلوبة.
"""

    try:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ANALYSIS_SCHEMA,
            temperature=0.2,
        )

        response = client.models.generate_content(
            model=GEMINI_SCRIPT_MODEL,
            contents=prompt,
            config=config,
        )

        raw_text = response.text or "{}"
        print(f"[Section Analyzer Output] {raw_text}")
        data = json.loads(raw_text)
        return data

    except Exception as e:
        print(f"[Section Analyzer Error] {e}")
        return {"should_split": False, "reasoning": str(e)}
