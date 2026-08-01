"""
imaginAI Backend — FastAPI Application
Main entry point with CORS, routes, multi-provider TTS previews, and background pipeline execution.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import JOBS_DIR, VOICE_PROVIDERS
from app.models import JobRequest, JobStatusResponse, make_initial_status

app = FastAPI(title="imaginAI", version="1.0.0")

# ── CORS (allow Next.js dev server) ─────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/api/voices")
async def list_voices():
    """Return available TTS providers and voices catalog."""
    return {"providers": VOICE_PROVIDERS}


@app.get("/api/voices/preview")
async def preview_voice(
    provider: str = Query("edge-tts", description="TTS Provider (edge-tts, gemini, gtts)"),
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
        # Delete existing stale preview if present
        if preview_file.exists():
            try:
                preview_file.unlink()
            except Exception:
                pass

        # Sample text tailored for male vs female & language
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
            raise HTTPException(status_code=500, detail=f"Failed to generate voice preview: {str(e)}")

    return FileResponse(
        path=str(preview_file),
        media_type="audio/wav",
        filename=f"preview_{safe_voice}.wav",
    )



from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, Request, Header
from app.services.rate_limit import check_and_increment_rate_limits, DATA_DIR


@app.post("/api/jobs")
async def create_job(
    req: JobRequest,
    bg: BackgroundTasks,
    request: Request,
    x_visitor_id: str = Header(None, alias="x-visitor-id"),
):
    # Determine visitor identity (x-visitor-id header or client IP)
    client_ip = request.client.host if request.client else "127.0.0.1"
    visitor_id = x_visitor_id or f"ip_{client_ip}"

    # Rate limiting check (4 videos / visitor / 24h & 20 videos / day global)
    allowed, err_msg = check_and_increment_rate_limits(visitor_id)
    if not allowed:
        raise HTTPException(status_code=429, detail=err_msg)

    job_id = uuid.uuid4().hex[:12]
    job_path = _job_dir(job_id)
    job_path.mkdir(parents=True, exist_ok=True)

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
        job_id,
        req.idea,
        req.duration,
        req.style,
        req.voice,
        req.voice_provider,
    )

    return {"job_id": job_id}


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
    output = _job_dir(job_id) / "output.mp4"
    if not output.exists():
        raise HTTPException(status_code=404, detail="Video not ready yet")
    return FileResponse(
        path=str(output),
        media_type="video/mp4",
        filename=f"imaginai_{job_id}.mp4",
    )
