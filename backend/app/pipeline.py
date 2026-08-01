"""
imaginAI Backend — Pipeline Orchestrator
Runs the 5 stages in order and updates status.json after each stage.
Real audio durations (measured via ffprobe) are the single source of truth
for all timing throughout the pipeline.
"""

import json
import traceback
from pathlib import Path

from app.config import JOBS_DIR
from app.models import STAGE_NAMES


def _status_path(job_id: str) -> Path:
    return JOBS_DIR / job_id / "status.json"


def _format_user_friendly_error(err: Exception) -> str:
    """Map raw technical errors to friendly, actionable Arabic messages for end users."""
    raw_str = str(err)
    raw_lower = raw_str.lower()

    if any(k in raw_lower for k in ["429", "resourceexhausted", "quota", "rate limit"]):
        return "تجاوز السيرفر الحد المؤقت لاستخدام الخادم (Quota Exceeded)، يرجى المحاولة بعد بضع دقائق."
    elif "404" in raw_lower or "not_found" in raw_lower:
        return "حدث خطأ في الاتصال بـ Gemini API، يرجى إعادة المحاولة لاحقاً."
    elif "ffmpeg" in raw_lower or "render" in raw_lower:
        return "حدث خطأ أثناء رندر ومعالجة المشاهد، يرجى المحاولة مجدداً."
    elif any(k in raw_lower for k in ["pexels", "pixabay", "footage"]):
        return "تعذر جلب لقطات الفيديو المطلوبة من الخوادم المصدرية، يرجى المحاولة مجدداً."
    else:
        return f"حدث خطأ أثناء معالجة الفيديو: {raw_str[:150]}"


def _update_status(job_id: str, **kwargs) -> None:
    """Read status.json, merge kwargs, write back."""
    path = _status_path(job_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(kwargs)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _set_stage(job_id: str, stage: str, state: str) -> None:
    """Update a single stage's state inside status.json."""
    path = _status_path(job_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["stages"][stage] = state
    data["current_stage"] = stage
    data["status"] = "processing"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


TARGET_DURATION_SECONDS = {
    "5_min": 300.0,
    "8_min": 480.0,
    "10_min": 600.0,
    "short": 300.0,
    "medium": 480.0,
}


async def run_pipeline(
    job_id: str,
    idea: str,
    duration: str,
    style: str = "documentary",
    voice: str = "ar-SA-HamedNeural",
    voice_provider: str = "edge-tts",
) -> None:
    """Execute the full video generation pipeline."""
    job_dir = JOBS_DIR / job_id

    try:
        target_seconds = TARGET_DURATION_SECONDS.get(duration, 300.0)

        # ── Stage 1: Script ──────────────────────────────────────────────
        _set_stage(job_id, "script", "processing")
        from app.services.gemini_script import generate_script
        script = await generate_script(idea, duration, style, job_dir)
        _set_stage(job_id, "script", "done")

        # ── Stage 2: TTS ─────────────────────────────────────────────────
        _set_stage(job_id, "tts", "processing")
        from app.services.gemini_tts import generate_all_speech, get_audio_duration_ffprobe
        audio_paths = await generate_all_speech(
            script.scenes, job_dir, voice=voice, provider=voice_provider
        )

        # ── Measure real durations via ffprobe ───────────────────────────
        audio_durations = [get_audio_duration_ffprobe(p) for p in audio_paths]
        total_audio_dur = sum(audio_durations)
        print(f"[Pipeline] Real audio durations: {[round(d, 2) for d in audio_durations]}")
        print(f"[Pipeline] Total audio duration: {round(total_audio_dur, 2)}s (Target: {target_seconds}s)")

        # ── Duration Check: If < 85% of target, re-request longer script ──────
        min_required_dur = target_seconds * 0.85
        if total_audio_dur < min_required_dur:
            print(
                f"[Pipeline WARNING] Audio duration ({total_audio_dur:.1f}s) is below 85% of requested target ({target_seconds}s). "
                f"Re-generating expanded script..."
            )
            expanded_prompt = (
                f"{idea}\n\n"
                f"[IMPORTANT INSTRUCTION FOR SCRIPT LENGTH: The previous generated script was too short ({total_audio_dur:.0f} seconds). "
                f"You MUST expand the script with additional detailed scenes to cover at least {int(target_seconds)} seconds of total spoken duration.]"
            )
            script = await generate_script(expanded_prompt, duration, style, job_dir)
            audio_paths = await generate_all_speech(
                script.scenes, job_dir, voice=voice, provider=voice_provider
            )
            audio_durations = [get_audio_duration_ffprobe(p) for p in audio_paths]
            total_audio_dur = sum(audio_durations)
            print(f"[Pipeline] Re-generated script audio duration: {round(total_audio_dur, 2)}s")

        _set_stage(job_id, "tts", "done")

        # ── Stage 3: Footage ─────────────────────────────────────────────
        _set_stage(job_id, "footage", "processing")
        from app.services.footage import fetch_all_footage
        shots_per_scene = await fetch_all_footage(
            script.scenes, audio_durations, job_dir, style
        )
        _set_stage(job_id, "footage", "done")

        # ── Stage 4: Captions ────────────────────────────────────────────
        _set_stage(job_id, "captions", "processing")
        from app.services.captions import transcribe_all
        caption_data = await transcribe_all(audio_paths, job_dir)
        _set_stage(job_id, "captions", "done")

        # ── Stage 5: Render ──────────────────────────────────────────────
        _set_stage(job_id, "render", "processing")
        from app.services.render import render_video
        output_path = await render_video(
            job_dir,
            script.scenes,
            audio_paths,
            audio_durations,
            shots_per_scene,
            caption_data,
            style,
        )

        # ── Stage 6: Strict Final Validation Check ───────────────────────
        out_file = Path(output_path)
        if not out_file.exists() or out_file.stat().st_size == 0:
            raise RuntimeError("Final video rendering failed: Output file does not exist or is empty.")

        final_video_dur = get_audio_duration_ffprobe(output_path)
        expected_audio_dur = sum(audio_durations)
        dur_diff = abs(final_video_dur - expected_audio_dur)

        print(f"[Pipeline Validation] Final video duration: {final_video_dur:.2f}s, Audio total: {expected_audio_dur:.2f}s (Diff: {dur_diff:.2f}s)")

        if dur_diff > 1.0:
            raise RuntimeError(
                f"Final video validation failed: Video duration ({final_video_dur:.2f}s) does not match total narration duration ({expected_audio_dur:.2f}s, diff > 1s)."
            )

        _set_stage(job_id, "render", "done")

        # ── Done ─────────────────────────────────────────────────────────
        _update_status(
            job_id,
            status="done",
            current_stage=None,
            output_url=f"/api/jobs/{job_id}/download",
        )

    except Exception as e:
        traceback.print_exc()
        user_msg = _format_user_friendly_error(e)
        _update_status(
            job_id,
            status="failed",
            error=user_msg,
        )
