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
    voice: str = "Kore",
    voice_provider: str = "gemini",
    device_id: str = "default",
    project_id: str = "default",
    niche_id: str | None = None,
    custom_niche: str | None = None,
    caption_config: dict | None = None,
    input_mode: str = "ai_generated",
    provided_script: str | None = None,
    additional_context: str | None = None,
) -> None:
    """Execute the full video generation pipeline."""
    job_dir = JOBS_DIR / job_id
    video_id = job_id

    try:
        target_seconds = TARGET_DURATION_SECONDS.get(duration, 300.0)

        # ── Stage 1: Script ──────────────────────────────────────────────
        _set_stage(job_id, "script", "processing")
        if input_mode in ("script_provided", "script") and provided_script and provided_script.strip():
            print(f"[Pipeline] User provided custom script ({len(provided_script)} chars). Skipping Gemini script generation.")
            from app.models import GeneratedScript, ScriptScene
            
            # Split provided script by paragraphs or line breaks
            paragraphs = [p.strip() for p in provided_script.strip().split("\n") if p.strip()]
            scenes = []
            for idx, p_text in enumerate(paragraphs):
                word_count = len(p_text.split())
                est_sec = max(3.0, round((word_count / 150.0) * 60.0, 1))
                scenes.append(
                    ScriptScene(
                        narration=p_text,
                        visual_keywords=["cinematic", "documentary", style],
                        estimated_seconds=est_sec,
                    )
                )

            if not scenes:
                scenes = [ScriptScene(narration=provided_script.strip(), visual_keywords=["cinematic", style], estimated_seconds=10.0)]

            script = GeneratedScript(scenes=scenes)
            script_file = job_dir / "script.json"
            script_file.write_text(
                json.dumps({"scenes": [s.model_dump() for s in scenes]}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[Pipeline] Provided script parsed into {len(scenes)} scenes.")
        else:
            from app.services.gemini_script import generate_script
            script = await generate_script(
                idea,
                duration,
                style,
                job_dir,
                niche_id=niche_id,
                custom_niche=custom_niche,
                additional_context=additional_context,
            )
        _set_stage(job_id, "script", "done")

        # ── Dynamic Section Analysis (for non-predefined niches) ─────────
        from app.niches import find_niche_info
        niche_info = find_niche_info(niche_id or custom_niche or "")
        fixed_overlay = niche_info.get("section_overlay_type") if niche_info else None

        if not fixed_overlay:
            from app.services.gemini_section_analyzer import analyze_script_sections
            proposal = await analyze_script_sections([s.model_dump() for s in script.scenes], idea=idea)
            if proposal.get("should_split") and proposal.get("sections"):
                proposal_file = job_dir / "section_proposal.json"
                proposal_file.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")

                # Save pipeline state info so we can resume smoothly
                pipeline_state = {
                    "job_id": job_id,
                    "idea": idea,
                    "duration": duration,
                    "style": style,
                    "voice": voice,
                    "voice_provider": voice_provider,
                    "device_id": device_id,
                    "project_id": project_id,
                    "niche_id": niche_id,
                    "custom_niche": custom_niche,
                    "caption_config": caption_config,
                }
                (job_dir / "pipeline_state.json").write_text(
                    json.dumps(pipeline_state, ensure_ascii=False, indent=2), encoding="utf-8"
                )

                from app.db import update_video
                update_video(video_id=video_id, status="pending_section_approval")

                _update_status(
                    job_id,
                    status="pending_section_approval",
                    current_stage="pending_section_approval",
                    section_proposal=proposal,
                )
                print(f"[Pipeline] Paused for user section approval (job_id: {job_id})")
                return

        # ── Stage 2: TTS ─────────────────────────────────────────────────
        _set_stage(job_id, "tts", "processing")
        from app.services.gemini_tts import generate_all_speech, get_audio_duration_ffprobe
        audio_paths = await generate_all_speech(
            script.scenes, job_dir, voice=voice, provider=voice_provider
        )

        # ── Measure real durations via ffprobe ───────────────────────────
        audio_durations = [get_audio_duration_ffprobe(p) for p in audio_paths]
        total_audio_dur = sum(audio_durations)
        print(f"[Pipeline] Initial audio durations: {[round(d, 2) for d in audio_durations]}")
        print(f"[Pipeline] Initial total audio duration: {round(total_audio_dur, 2)}s (Target: {target_seconds}s)")

        # ── Strict Duration Enforcement Loop (up to 5 attempts) ──────────
        attempt = 0
        max_expansion_attempts = 5

        while total_audio_dur < target_seconds and attempt < max_expansion_attempts:
            attempt += 1
            gap_seconds = target_seconds - total_audio_dur
            print(
                f"[Pipeline Duration Loop] Attempt {attempt}/{max_expansion_attempts}: "
                f"Audio duration ({total_audio_dur:.1f}s) < target ({target_seconds}s). Gap: {gap_seconds:.1f}s. Expanding script..."
            )
            from app.services.gemini_script import expand_script_scenes
            new_scenes = await expand_script_scenes(
                idea=idea,
                needed_seconds=gap_seconds,
                current_scenes_count=len(script.scenes),
                style=style,
                job_dir=job_dir,
            )

            if not new_scenes:
                print(f"[Pipeline Duration Loop Warning] No new scenes returned on attempt {attempt}.")
                continue

            existing_count = len(script.scenes)
            script.scenes.extend(new_scenes)

            # Generate speech for NEW scenes only
            new_audio_paths = await generate_all_speech(
                new_scenes, job_dir, voice=voice, provider=voice_provider, start_index=existing_count
            )
            audio_paths.extend(new_audio_paths)

            new_durations = [get_audio_duration_ffprobe(p) for p in new_audio_paths]
            audio_durations.extend(new_durations)
            total_audio_dur = sum(audio_durations)
            print(f"[Pipeline Duration Loop] After expansion #{attempt}: Total duration = {total_audio_dur:.1f}s / {target_seconds}s")

        if total_audio_dur < target_seconds:
            err_msg = (
                f"تعذر الوصول للمدة المطلوبة ({target_seconds/60:.0f} دقائق) بعد 5 محاولات إضافة مشاهد. "
                f"المدة الفعلية المحققة: {total_audio_dur/60:.1f} دقيقة."
            )
            print(f"[Pipeline ERROR] {err_msg}")
            raise RuntimeError(err_msg)

        _set_stage(job_id, "tts", "done")

        # ── Stage 3: Footage ─────────────────────────────────────────────
        _set_stage(job_id, "footage", "processing")
        from app.services.footage import fetch_all_footage
        shots_per_scene = await fetch_all_footage(
            script.scenes, audio_durations, job_dir, style
        )
        _set_stage(job_id, "footage", "done")

        # ── Stage 3.5: Build review_data.json & Pause for Review ─────────────
        review_scenes = []
        for idx, sc in enumerate(script.scenes):
            shots_list = shots_per_scene[idx] if idx < len(shots_per_scene) else []
            shots_data = []
            for s_idx, shot_path in enumerate(shots_list):
                shots_data.append({
                    "shot_index": s_idx,
                    "clip_path": shot_path,
                    "stream_url": f"/api/jobs/{job_id}/clips/{idx}/{s_idx}",
                })
            review_scenes.append({
                "scene_index": idx,
                "narration": sc.narration,
                "visual_keywords": sc.visual_keywords,
                "audio_path": audio_paths[idx] if idx < len(audio_paths) else "",
                "audio_duration": audio_durations[idx] if idx < len(audio_durations) else 0.0,
                "shots": shots_data,
            })

        review_payload = {
            "job_id": job_id,
            "idea": idea,
            "duration": duration,
            "style": style,
            "voice": voice,
            "voice_provider": voice_provider,
            "device_id": device_id,
            "project_id": project_id,
            "niche_id": niche_id,
            "custom_niche": custom_niche,
            "caption_config": caption_config,
            "audio_paths": audio_paths,
            "audio_durations": audio_durations,
            "shots_per_scene": shots_per_scene,
            "scenes": review_scenes,
        }

        review_file = job_dir / "review_data.json"
        review_file.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        from app.db import update_video
        update_video(video_id=video_id, status="pending_review")

        _update_status(
            job_id,
            status="pending_review",
            current_stage="pending_review",
        )
        print(f"[Pipeline] Paused for user review (job_id: {job_id})")
        return

    except Exception as e:
        traceback.print_exc()
        user_msg = _format_user_friendly_error(e)
        from app.db import update_video
        update_video(video_id=video_id, status="failed")

        _update_status(
            job_id,
            status="failed",
            error=user_msg,
        )


async def resume_pipeline(
    job_id: str,
    edited_scenes: list[dict],
) -> None:
    """
    Resume pipeline after user review & edits.
    1. Re-generate TTS only for scenes where narration text changed.
    2. Update audio_paths & audio_durations.
    3. Update footage shots if alternative footage was selected.
    4. Run Stage 4 (Captions) & Stage 5 (Render).
    """
    job_dir = JOBS_DIR / job_id
    video_id = job_id
    review_file = job_dir / "review_data.json"

    if not review_file.exists():
        raise RuntimeError("Review data file review_data.json not found for job.")

    review_data = json.loads(review_file.read_text(encoding="utf-8"))

    voice = review_data.get("voice", "Kore")
    voice_provider = review_data.get("voice_provider", "gemini")
    style = review_data.get("style", "documentary")
    niche_id = review_data.get("niche_id")
    caption_config = review_data.get("caption_config")
    device_id = review_data.get("device_id", "default")
    project_id = review_data.get("project_id", "default")

    audio_paths = review_data.get("audio_paths", [])
    audio_durations = review_data.get("audio_durations", [])
    shots_per_scene = review_data.get("shots_per_scene", [])
    raw_scenes = review_data.get("scenes", [])

    from app.models import ScriptScene
    from app.services.gemini_tts import generate_all_speech, get_audio_duration_ffprobe

    edited_map = {item["scene_index"]: item for item in edited_scenes}

    script_scenes = []
    for idx, sc_info in enumerate(raw_scenes):
        edited_item = edited_map.get(idx, {})
        raw_new = edited_item.get("narration") if "narration" in edited_item else sc_info.get("narration")
        new_narration = (raw_new or "").strip()
        old_narration = (sc_info.get("narration") or "").strip()

        if "shots" in edited_item and isinstance(edited_item["shots"], list) and edited_item["shots"]:
            shots_per_scene[idx] = edited_item["shots"]

        scene_obj = ScriptScene(
            narration=new_narration,
            visual_keywords=sc_info.get("visual_keywords", []),
            estimated_seconds=sc_info.get("audio_duration", 5.0),
        )
        script_scenes.append(scene_obj)

        if new_narration != old_narration:
            print(f"[Resume Pipeline] Scene {idx} narration edited. Regenerating speech...")
            new_audio_paths = await generate_all_speech(
                [scene_obj], job_dir, voice=voice, provider=voice_provider, start_index=idx
            )
            if new_audio_paths and len(new_audio_paths) > 0:
                audio_paths[idx] = new_audio_paths[0]
                audio_durations[idx] = get_audio_duration_ffprobe(new_audio_paths[0])
                print(f"[Resume Pipeline] Scene {idx} new audio duration: {audio_durations[idx]:.2f}s")

    try:
        # ── Stage 4: Captions ────────────────────────────────────────────
        _set_stage(job_id, "captions", "processing")
        from app.services.captions import transcribe_all
        caption_data = await transcribe_all(audio_paths, job_dir, scenes=script_scenes)
        _set_stage(job_id, "captions", "done")

        # ── Stage 5: Render ──────────────────────────────────────────────
        _set_stage(job_id, "render", "processing")
        from app.services.render import render_video
        output_path = await render_video(
            job_dir,
            script_scenes,
            audio_paths,
            audio_durations,
            shots_per_scene,
            caption_data,
            style,
            niche_id,
            caption_config,
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

        # ── Move to Permanent Storage & Update SQLite DB ─────────────────
        from app.config import STORAGE_DIR
        from app.db import update_video

        perm_dir = STORAGE_DIR / device_id / project_id
        perm_dir.mkdir(parents=True, exist_ok=True)
        perm_file = perm_dir / f"{video_id}.mp4"

        import shutil
        shutil.copy2(output_path, perm_file)
        print(f"[Pipeline Storage] Saved permanent video to {perm_file}")

        update_video(
            video_id=video_id,
            status="completed",
            file_path=str(perm_file),
            duration=final_video_dur,
        )

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
        from app.db import update_video
        update_video(video_id=video_id, status="failed")

        _update_status(
            job_id,
            status="failed",
            error=user_msg,
        )


async def approve_sections_and_resume(job_id: str, apply_sections: bool) -> None:
    """
    Resume pipeline after user approves or declines dynamic section proposals.
    """
    job_dir = JOBS_DIR / job_id
    state_file = job_dir / "pipeline_state.json"
    proposal_file = job_dir / "section_proposal.json"
    script_file = job_dir / "script.json"

    if not state_file.exists() or not script_file.exists():
        raise RuntimeError("Pipeline state or script file missing for job.")

    state = json.loads(state_file.read_text(encoding="utf-8"))
    script_data = json.loads(script_file.read_text(encoding="utf-8"))

    if apply_sections and proposal_file.exists():
        proposal = json.loads(proposal_file.read_text(encoding="utf-8"))
        sections = proposal.get("sections", [])

        for sec in sections:
            idx = sec.get("scene_index")
            if idx is not None and 0 <= idx < len(script_data["scenes"]):
                if "section_number" in sec:
                    script_data["scenes"][idx]["section_number"] = sec["section_number"]
                if "section_title" in sec:
                    script_data["scenes"][idx]["section_title"] = sec["section_title"]

        script_file.write_text(json.dumps(script_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[Pipeline] Applied {len(sections)} sections to script for job {job_id}")

    # Resume pipeline by setting status to processing and running remaining stages
    _update_status(
        job_id,
        status="processing",
        current_stage="tts",
    )

    from app.models import GeneratedScript, ScriptScene
    scenes = [ScriptScene(**s) for s in script_data["scenes"]]
    script = GeneratedScript(scenes=scenes)

    voice = state.get("voice", "Kore")
    voice_provider = state.get("voice_provider", "gemini")
    style = state.get("style", "documentary")
    device_id = state.get("device_id", "default")
    project_id = state.get("project_id", "default")
    niche_id = state.get("niche_id")
    custom_niche = state.get("custom_niche")
    caption_config = state.get("caption_config")

    # ── Stage 2: TTS ─────────────────────────────────────────────────
    _set_stage(job_id, "tts", "processing")
    from app.services.gemini_tts import generate_all_speech, get_audio_duration_ffprobe
    audio_paths = await generate_all_speech(
        script.scenes, job_dir, voice=voice, provider=voice_provider
    )
    audio_durations = [get_audio_duration_ffprobe(p) for p in audio_paths]

    # ── Stage 3: Footage ─────────────────────────────────────────────
    _set_stage(job_id, "footage", "processing")
    from app.services.footage import fetch_all_footage
    shots_per_scene = await fetch_all_footage(
        script.scenes, audio_durations, job_dir, style
    )
    _set_stage(job_id, "footage", "done")

    # ── Stage 3.5: Build review_data.json & Pause for Review ─────────────
    review_scenes = []
    for idx, sc in enumerate(script.scenes):
        shots_list = shots_per_scene[idx] if idx < len(shots_per_scene) else []
        shots_data = []
        for s_idx, shot_path in enumerate(shots_list):
            shots_data.append({
                "shot_index": s_idx,
                "clip_path": shot_path,
                "stream_url": f"/api/jobs/{job_id}/clips/{idx}/{s_idx}",
            })
        review_scenes.append({
            "scene_index": idx,
            "narration": sc.narration,
            "visual_keywords": sc.visual_keywords,
            "audio_path": audio_paths[idx] if idx < len(audio_paths) else "",
            "audio_duration": audio_durations[idx] if idx < len(audio_durations) else 0.0,
            "shots": shots_data,
        })

    review_payload = {
        "job_id": job_id,
        "idea": state.get("idea", ""),
        "duration": state.get("duration", "5_min"),
        "style": style,
        "voice": voice,
        "voice_provider": voice_provider,
        "device_id": device_id,
        "project_id": project_id,
        "niche_id": niche_id,
        "custom_niche": custom_niche,
        "caption_config": caption_config,
        "audio_paths": audio_paths,
        "audio_durations": audio_durations,
        "shots_per_scene": shots_per_scene,
        "scenes": review_scenes,
    }

    review_file = job_dir / "review_data.json"
    review_file.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    from app.db import update_video
    update_video(video_id=job_id, status="pending_review")

    _update_status(
        job_id,
        status="pending_review",
        current_stage="pending_review",
    )
    print(f"[Pipeline] Paused for user review (job_id: {job_id})")



