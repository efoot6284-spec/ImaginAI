import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, Request, Response, Header, Depends, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import JOBS_DIR, STORAGE_DIR, VOICE_PROVIDERS
from app.models import (
    JobRequest,
    JobStatusResponse,
    ProjectCreate,
    ProjectResponse,
    VideoResponse,
    ResumeJobRequest,
    SectionApprovalRequest,
    make_initial_status,
)
from app.db import (
    init_db,
    get_db_connection,
    get_or_create_device,
    clear_device_data,
    create_project,
    get_projects_by_device,
    get_project,
    create_video,
    update_video,
    get_videos_by_device,
    get_videos_by_project,
    create_custom_voice,
    get_custom_voices_by_device,
    create_custom_font,
    get_custom_fonts_by_device,
    get_custom_font_by_id,
)
from app.services.rate_limit import check_and_increment_rate_limits, DATA_DIR

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="imaginAI", version="1.0.0", lifespan=lifespan)


# ── CORS (allow Next.js dev server) ─────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Device Identity Dependency ──────────────────────────────────────────────
COOKIE_NAME = "imaginai_device_id"
COOKIE_MAX_AGE = 31536000  # 1 year (365 days)


def get_current_device(request: Request, response: Response) -> str:
    """
    Extract device_id from cookie 'imaginai_device_id', header 'x-device-id', or header 'x-visitor-id'.
    If missing, generate a new UUID, record in SQLite, and set long-term cookie.
    """
    device_id = (
        request.cookies.get(COOKIE_NAME)
        or request.headers.get("x-device-id")
        or request.headers.get("x-visitor-id")
    )

    if not device_id:
        device_id = f"dev_{uuid.uuid4().hex}"
        response.set_cookie(
            key=COOKIE_NAME,
            value=device_id,
            max_age=COOKIE_MAX_AGE,
            httponly=False,
            samesite="lax",
            secure=False,
        )

    get_or_create_device(device_id)
    return device_id


# ── Helpers ──────────────────────────────────────────────────────────────────

def _job_dir(job_id: str) -> Path:
    return JOBS_DIR / job_id


def _read_status(job_id: str) -> dict:
    status_file = _job_dir(job_id) / "status.json"
    if not status_file.exists():
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return json.loads(status_file.read_text(encoding="utf-8"))


def _write_status(job_id: str, data: dict) -> None:
    status_file = _job_dir(job_id) / "status.json"
    status_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/niches")
async def get_niches():
    """Return catalog of domains and sub-niches."""
    from app.niches import get_all_niches
    return {"domains": get_all_niches()}


# ── Device & Project Routes ──────────────────────────────────────────────────

@app.get("/api/device/me")
async def get_device_info(device_id: str = Depends(get_current_device)):
    """Return device identity info."""
    return get_or_create_device(device_id)


@app.delete("/api/device/reset")
async def reset_device(response: Response, device_id: str = Depends(get_current_device)):
    """Clear all projects, videos, and data for the current device and delete identity cookie."""
    clear_device_data(device_id)
    response.delete_cookie(COOKIE_NAME)
    return {"status": "ok", "message": "تم مسح جميع بيانات هذا الجهاز بنجاح."}


@app.post("/api/projects")
async def api_create_project(req: ProjectCreate, device_id: str = Depends(get_current_device)):
    """Create a new project linked to device_id."""
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    return create_project(
        project_id=project_id,
        device_id=device_id,
        domain=req.domain,
        niche=req.niche,
        name=req.name,
    )


@app.get("/api/projects")
async def api_list_projects(device_id: str = Depends(get_current_device)):
    """List all projects for the current device."""
    return {"projects": get_projects_by_device(device_id)}


@app.get("/api/projects/{project_id}")
async def api_get_project(project_id: str, device_id: str = Depends(get_current_device)):
    """Get project details and its videos."""
    proj = get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    videos = get_videos_by_project(project_id)
    return {"project": proj, "videos": videos}


@app.get("/api/videos/{video_id}/stream")
async def api_stream_video(video_id: str):
    """Stream a stored video by video_id directly from permanent storage or jobs."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM videos WHERE video_id = ?", (video_id,))
        row = cursor.fetchone()
        if row and row["file_path"] and Path(row["file_path"]).exists():
            return FileResponse(
                path=row["file_path"],
                media_type="video/mp4",
                filename=f"imaginai_{video_id}.mp4",
            )
    
    # Fallback to jobs directory
    job_file = JOBS_DIR / video_id / "output.mp4"
    if job_file.exists():
        return FileResponse(
            path=str(job_file),
            media_type="video/mp4",
            filename=f"imaginai_{video_id}.mp4",
        )

    raise HTTPException(status_code=404, detail="فيديو غير موجود أو لم يكتمل بعد")


@app.get("/api/voices")
async def list_voices(device_id: str = Depends(get_current_device)):
    """Return available TTS providers and voices catalog, including user's custom cloned voices."""
    from app.services.fish_audio_tts import fetch_fish_audio_voices
    
    # Clone catalog list
    providers = json.loads(json.dumps(VOICE_PROVIDERS))
    
    # Dynamically inject Fish Audio voices if available
    fish_voices = fetch_fish_audio_voices()

    # Retrieve custom cloned voices for device
    custom_records = get_custom_voices_by_device(device_id)
    custom_voices_list = []
    for r in custom_records:
        custom_voices_list.append({
            "id": r["fish_voice_id"],
            "name": f"{r['name']} (صوتك المستنسخ)",
            "gender": "neutral",
            "lang": "العربية / English",
            "desc": f"صوت مستنسخ محلياً بالذكاء الاصطناعي • {r['name']}",
            "is_custom": True,
        })

    if fish_voices or custom_voices_list:
        combined_fish = custom_voices_list + (fish_voices or [])
        for p in providers:
            if p.get("provider") == "fish-audio":
                p["voices"] = combined_fish

    return {"providers": providers}


@app.post("/api/voices/clone")
async def clone_voice(
    file: UploadFile,
    voice_name: str = Form(...),
    device_id: str = Depends(get_current_device),
):
    """Upload an audio sample, create a cloned voice model in Fish Audio, and save to SQLite."""
    from app.services.fish_audio_tts import clone_voice_fish_audio, generate_speech_fish_audio

    if not file or not voice_name.strip():
        raise HTTPException(status_code=400, detail="يرجى إرفاق ملف صوت واسم للصوت المستنسخ.")

    content = await file.read()
    if not content or len(content) < 1000:
        raise HTTPException(status_code=400, detail="الملف الصوتي المرفق قصير جداً أو فارغ.")

    try:
        fish_voice_id = await clone_voice_fish_audio(
            audio_bytes=content,
            filename=file.filename or "sample.wav",
            voice_name=voice_name.strip(),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Generate immediate preview audio sample
    previews_dir = JOBS_DIR / "previews"
    previews_dir.mkdir(exist_ok=True)
    preview_path = previews_dir / f"fish-audio_{fish_voice_id}.wav"

    try:
        sample_text = f"مرحباً! هذا التسجيل هو تجربة لاختبار جودة صوتك المستنسخ {voice_name} عبر منصة إيماجن أي آي."
        await generate_speech_fish_audio(sample_text, str(preview_path), voice_id=fish_voice_id)
    except Exception as e:
        print(f"[Clone Preview Warning] Could not generate immediate preview for cloned voice: {e}")

    voice_entry_id = str(uuid.uuid4())
    sample_url = f"/api/voices/preview?provider=fish-audio&voice={fish_voice_id}"

    create_custom_voice(
        voice_id=voice_entry_id,
        device_id=device_id,
        name=voice_name.strip(),
        fish_voice_id=fish_voice_id,
        sample_url=sample_url,
    )

    return {
        "success": True,
        "voice": {
            "id": fish_voice_id,
            "name": f"{voice_name.strip()} (صوتك المستنسخ)",
            "provider": "fish-audio",
            "sample_url": sample_url,
            "is_custom": True,
        }
    }


@app.post("/api/fonts/upload")
async def upload_custom_font_endpoint(
    file: UploadFile,
    font_name: str = Form(...),
    device_id: str = Depends(get_current_device),
):
    """Upload a custom font file (.ttf / .otf) and save to SQLite."""
    if not file or not font_name.strip():
        raise HTTPException(status_code=400, detail="يرجى إرفاق ملف الخط واسم الخط.")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in [".ttf", ".otf"]:
        raise HTTPException(status_code=400, detail="صيغة الملف غير مدعومة. يرجى رفع ملف بصيغة ttf أو otf.")

    content = await file.read()
    if not content or len(content) < 100:
        raise HTTPException(status_code=400, detail="ملف الخط فارغ أو غير صالح.")

    font_id = f"font_{uuid.uuid4().hex[:8]}"
    fonts_dir = STORAGE_DIR / device_id / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    font_file_path = fonts_dir / f"{font_id}{ext}"
    font_file_path.write_bytes(content)

    font_entry = create_custom_font(
        font_id=font_id,
        device_id=device_id,
        font_name=font_name.strip(),
        file_path=str(font_file_path),
    )

    return {
        "success": True,
        "font": font_entry,
    }


@app.get("/api/fonts")
async def list_custom_fonts(device_id: str = Depends(get_current_device)):
    """Retrieve all custom fonts for the current device."""
    return {"fonts": get_custom_fonts_by_device(device_id)}



@app.get("/api/voices/preview")
async def preview_voice(
    provider: str = Query("edge-tts", description="TTS Provider (edge-tts, gemini, gtts, fish-audio)"),
    voice: str = Query("ar-SA-HamedNeural", description="Voice ID"),
    refresh: bool = Query(False, description="Force regenerate preview audio"),
):
    """Generate and stream a short preview audio sample for the selected voice."""
    previews_dir = JOBS_DIR / "previews"
    previews_dir.mkdir(exist_ok=True)

    # Sanitize file key
    safe_voice = voice.replace("/", "_").replace("\\", "_")
    safe_provider = provider.replace("/", "_").replace("\\", "_")
    preview_file = previews_dir / f"{safe_provider}_{safe_voice}.wav"

    if refresh or not preview_file.exists() or preview_file.stat().st_size < 1000:
        if preview_file.exists():
            try:
                preview_file.unlink()
            except Exception:
                pass

        is_english = voice.startswith("en") or voice in ["Christopher", "Jenny", "Guy", "Fenrir"]
        is_female = any(name in voice for name in ["Salma", "Zariyah", "Kore", "Aoede", "Jenny"])

        if is_english:
            sample_text = "Hello! This is a sample preview of the selected narration voice for Imagin AI."
        elif is_female:
            sample_text = "أهلاً بك! أنا سلمى، وهذا تسجيل صوتي أنثوي لتجربة نبرة السرد في منصة إيماجن أي آي."
        else:
            sample_text = "مرحباً بك! أنا حامد، وهذا تسجيل صوتي ذكوري رزين لتجربة نبرة السرد في منصة إيماجن أي آي."

        from app.services.gemini_tts import generate_speech
        try:
            await generate_speech(
                text=sample_text,
                output_path=str(preview_file),
                voice=voice,
                provider=provider,
            )
        except Exception as e:
            err_msg = str(e)
            if "FISH_AUDIO_API_KEY" in err_msg:
                raise HTTPException(status_code=400, detail="يرجى إدخال مفتاح FISH_AUDIO_API_KEY في ملف .env لاستماع وتوليد أصوات Fish Audio.")
            raise HTTPException(status_code=400, detail=f"Failed to generate voice preview: {err_msg}")

    return FileResponse(
        path=str(preview_file),
        media_type="audio/wav",
        filename=f"preview_{safe_voice}.wav",
    )


@app.post("/api/jobs")
async def create_job(
    req: JobRequest,
    bg: BackgroundTasks,
    request: Request,
    response: Response,
    device_id: str = Depends(get_current_device),
    x_visitor_id: str = Header(None, alias="x-visitor-id"),
):
    # Determine visitor identity
    visitor_id = device_id or x_visitor_id or f"ip_{request.client.host if request.client else '127.0.0.1'}"

    # Rate limiting check
    allowed, err_msg = check_and_increment_rate_limits(visitor_id)
    if not allowed:
        raise HTTPException(status_code=429, detail=err_msg)

    # Project handling
    project_id = req.project_id
    domain = req.domain or "عام"
    niche = req.niche or "محتوى عام"

    if not project_id:
        existing_projects = get_projects_by_device(device_id)
        if existing_projects:
            project_id = existing_projects[0]["project_id"]
        else:
            default_proj = create_project(
                project_id=f"proj_{uuid.uuid4().hex[:8]}",
                device_id=device_id,
                domain=domain,
                niche=niche,
                name="المشروع الافتراضي",
            )
            project_id = default_proj["project_id"]

    job_id = uuid.uuid4().hex[:12]
    job_path = _job_dir(job_id)
    job_path.mkdir(parents=True, exist_ok=True)

    # Derive title for video
    title = (req.idea or req.provided_script or "فيديو جديد")[:50]
    create_video(
        video_id=job_id,
        project_id=project_id,
        title=title,
        status="processing",
    )

    # Initialize status.json
    status = make_initial_status(job_id)
    _write_status(job_id, status)

    # Save the request
    (job_path / "request.json").write_text(
        json.dumps(
            {
                "idea": req.idea,
                "duration": req.duration,
                "style": req.style,
                "voice_provider": req.voice_provider,
                "voice": req.voice,
                "visitor_id": visitor_id,
                "device_id": device_id,
                "project_id": project_id,
                "input_mode": req.input_mode,
                "provided_script": req.provided_script,
                "niche_id": req.niche_id,
                "custom_niche": req.custom_niche,
                "additional_context": req.additional_context,
                "strict_focus": req.strict_focus,
                "caption_config": req.caption_config,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Run pipeline in background
    from app.pipeline import run_pipeline
    bg.add_task(
        run_pipeline,
        job_id=job_id,
        idea=req.idea or "",
        duration=req.duration,
        style=req.style,
        voice=req.voice,
        voice_provider=req.voice_provider,
        device_id=device_id,
        project_id=project_id,
        niche_id=req.niche_id,
        custom_niche=req.custom_niche,
        caption_config=req.caption_config,
        input_mode=req.input_mode,
        provided_script=req.provided_script,
        additional_context=req.additional_context,
    )

    return {"job_id": job_id, "project_id": project_id, "device_id": device_id}


@app.post("/api/feedback")
async def receive_feedback(payload: dict):
    """Receive user feedback / suggestions and store in backend/data/feedback.json."""
    message = payload.get("message", "").strip()
    contact = payload.get("contact", "").strip()
    
    if not message:
        raise HTTPException(status_code=400, detail="الرجاء كتابة رسالة قبل الإرسال.")

    feedback_file = DATA_DIR / "feedback.json"
    existing = []
    if feedback_file.exists():
        try:
            existing = json.loads(feedback_file.read_text(encoding="utf-8"))
        except Exception:
            existing = []

    existing.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message,
        "contact": contact,
    })
    
    feedback_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok", "message": "شكراً لك! تم استلام ملاحظتك بنجاح."}


@app.get("/api/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    return _read_status(job_id)


@app.get("/api/jobs/{job_id}/download")
async def download_video(job_id: str):
    # First check permanent storage, fallback to jobs output.mp4
    from app.db import get_db_connection
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM videos WHERE video_id = ?", (job_id,))
        row = cursor.fetchone()
        if row and row["file_path"] and Path(row["file_path"]).exists():
            return FileResponse(
                path=row["file_path"],
                media_type="video/mp4",
                filename=f"imaginai_{job_id}.mp4",
            )

    output = _job_dir(job_id) / "output.mp4"
    if not output.exists():
        raise HTTPException(status_code=404, detail="Video not ready yet")
    return FileResponse(
        path=str(output),
        media_type="video/mp4",
        filename=f"imaginai_{job_id}.mp4",
    )


@app.get("/api/jobs/{job_id}/review")
async def get_job_review_data(job_id: str):
    """Retrieve review_data.json for a job in pending_review status."""
    review_file = _job_dir(job_id) / "review_data.json"
    if not review_file.exists():
        raise HTTPException(status_code=404, detail="بيانات المراجعة غير موجودة أو لم تكتمل مرحلة اللقطات بعد.")
    try:
        data = json.loads(review_file.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في قراءة بيانات المراجعة: {str(e)}")


@app.get("/api/jobs/{job_id}/clips/{scene_index}/{shot_index}")
async def get_job_clip(job_id: str, scene_index: int, shot_index: int):
    """Stream a video clip associated with a job scene for review preview."""
    review_file = _job_dir(job_id) / "review_data.json"
    if not review_file.exists():
        raise HTTPException(status_code=404, detail="الملف غير موجود.")
    data = json.loads(review_file.read_text(encoding="utf-8"))
    scenes = data.get("scenes", [])
    if scene_index < 0 or scene_index >= len(scenes):
        raise HTTPException(status_code=404, detail="المشهد غير موجود.")
    shots = scenes[scene_index].get("shots", [])
    if shot_index < 0 or shot_index >= len(shots):
        raise HTTPException(status_code=404, detail="اللقطة غير موجودة.")
    clip_path = Path(shots[shot_index].get("clip_path", ""))
    if not clip_path.exists():
        raise HTTPException(status_code=404, detail="ملف اللقطة غير موجود على السيرفر.")
    return FileResponse(clip_path, media_type="video/mp4")


@app.post("/api/jobs/{job_id}/resume")
async def resume_job_endpoint(
    job_id: str,
    req: ResumeJobRequest,
    background_tasks: BackgroundTasks,
):
    """Resume a job paused at pending_review after applying user edits."""
    status_file = _job_dir(job_id) / "status.json"
    if not status_file.exists():
        raise HTTPException(status_code=404, detail="الـ Job غير موجود.")
    
    st = json.loads(status_file.read_text(encoding="utf-8"))
    if st.get("status") != "pending_review":
        raise HTTPException(status_code=400, detail="الـ Job ليس في حالة انتظار المراجعة (pending_review).")

    st["status"] = "processing"
    st["current_stage"] = "captions"
    st["stages"]["captions"] = "processing"
    status_file.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")

    from app.db import update_video
    update_video(video_id=job_id, status="processing")

    from app.pipeline import resume_pipeline
    edited_dicts = [item.model_dump() for item in req.edited_scenes]
    background_tasks.add_task(resume_pipeline, job_id, edited_dicts)

    return {"success": True, "message": "تم استئناف الرندر النهائي بنجاح!"}


@app.post("/api/jobs/{job_id}/approve-sections")
async def approve_sections_endpoint(
    job_id: str,
    req: SectionApprovalRequest,
    background_tasks: BackgroundTasks,
):
    """Approve or decline proposed section overlays for dynamic section analysis."""
    status_file = _job_dir(job_id) / "status.json"
    if not status_file.exists():
        raise HTTPException(status_code=404, detail="الـ Job غير موجود.")

    st = json.loads(status_file.read_text(encoding="utf-8"))
    if st.get("status") != "pending_section_approval":
        raise HTTPException(status_code=400, detail="الـ Job ليس في حالة انتظار موافقة الأقسام.")

    st["status"] = "processing"
    st["current_stage"] = "tts"
    st["stages"]["tts"] = "processing"
    status_file.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")

    from app.db import update_video
    update_video(video_id=job_id, status="processing")

    from app.pipeline import approve_sections_and_resume
    background_tasks.add_task(approve_sections_and_resume, job_id, req.apply_sections)

    return {"success": True, "message": "تمت معالجة قرار الأقسام واستئناف التوليد بنجاح!"}

