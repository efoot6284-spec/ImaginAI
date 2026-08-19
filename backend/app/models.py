"""
imaginAI Backend — Pydantic Models
Schemas for requests, responses, and internal data structures.
"""

from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


# ── Request / Response ───────────────────────────────────────────────────────

DurationType = Literal["5_min", "8_min", "10_min", "15_min", "short", "medium"]
DEFAULT_DURATION: DurationType = "5_min"


class ProjectCreate(BaseModel):
    """POST /api/projects request."""
    domain: str = Field(..., description="Selected domain e.g. الغموض والرعب")
    niche: str = Field(..., description="Selected niche e.g. قصص رعب")
    name: str = Field(..., min_length=1, max_length=200, description="Project name")


class ProjectResponse(BaseModel):
    """Project entity response."""
    project_id: str
    device_id: str
    domain: str
    niche: str
    name: str
    created_at: str
    video_count: Optional[int] = 0
    last_video_at: Optional[str] = None


class VideoResponse(BaseModel):
    """Video entity response."""
    video_id: str
    project_id: str
    title: str
    file_path: Optional[str] = None
    duration: float = 0.0
    created_at: str
    status: str
    project_name: Optional[str] = None
    domain: Optional[str] = None
    niche: Optional[str] = None


class JobRequest(BaseModel):
    """POST /api/jobs request body."""
    idea: Optional[str] = Field(None, max_length=2000, description="The user's video prompt idea")
    duration: DurationType = Field(
        default=DEFAULT_DURATION, description="5_min, 8_min, 10_min, or 15_min"
    )
    style: Literal["mystery", "listicle", "documentary", "motivational"] = Field(
        "documentary", description="Montage style template"
    )
    voice_provider: Literal["gemini", "fish-audio", "edge-tts", "gtts"] = Field("edge-tts", description="TTS Provider")
    voice: str = Field("ar-SA-HamedNeural", description="TTS voice identifier")
    niche_id: Optional[str] = Field(None, description="Selected sub-niche ID")
    custom_niche: Optional[str] = Field(None, description="Custom user-written niche if not in catalog")
    music_track: Optional[str] = Field("auto", description="Background music selection: auto, none, or track_id")
    domain: Optional[str] = Field(None, description="Domain name e.g. الغموض والرعب")
    niche: Optional[str] = Field(None, description="Niche name e.g. قصص رعب")
    project_id: Optional[str] = Field(None, description="Associated project_id from DB")
    input_mode: Literal["ai_generated", "script_provided", "idea", "script"] = Field("ai_generated", description="Input mode")
    provided_script: Optional[str] = Field(None, description="Script provided by user if script_provided mode")
    additional_context: Optional[str] = Field(None, description="Additional background info/context")
    strict_focus: Optional[str] = Field(None, description="Strict points to focus on")
    caption_config: Optional[dict] = Field(None, description="Custom caption styling parameters")


class JobStatusResponse(BaseModel):
    """GET /api/jobs/{job_id}/status response."""
    job_id: str
    status: Literal["pending", "processing", "pending_review", "done", "failed"]
    current_stage: Optional[str] = None
    stages: dict[str, Literal["pending", "processing", "done", "failed"]]
    error: Optional[str] = None
    output_url: Optional[str] = None


class EditedScene(BaseModel):
    scene_index: int
    narration: Optional[str] = None
    shots: Optional[list[str]] = None


class ResumeJobRequest(BaseModel):
    edited_scenes: list[EditedScene] = Field(default_factory=list)


class SectionApprovalRequest(BaseModel):
    apply_sections: bool = Field(True, description="Whether to apply proposed section overlays or skip")


# ── Internal data ────────────────────────────────────────────────────────────

class ScriptScene(BaseModel):
    """One scene from the generated script."""
    narration: str
    visual_keywords: list[str]
    estimated_seconds: float  # kept for schema compatibility; real duration comes from ffprobe
    section_number: Optional[int | str] = None
    section_title: Optional[str] = None


class SceneShot(BaseModel):
    """A single stock-footage shot within a scene."""
    clip_path: str
    duration_seconds: float  # ffprobe-measured duration the shot will be trimmed to
    keywords: list[str]


class GeneratedScript(BaseModel):
    """Full script output from Gemini."""
    scenes: list[ScriptScene]


class WordTimestamp(BaseModel):
    """A single word with its start/end time."""
    word: str
    start: float
    end: float


# ── Defaults ─────────────────────────────────────────────────────────────────

STAGE_NAMES = ["script", "tts", "footage", "captions", "render"]

def make_initial_status(job_id: str) -> dict:
    """Create the initial status.json content for a new job."""
    return {
        "job_id": job_id,
        "status": "pending",
        "current_stage": None,
        "stages": {s: "pending" for s in STAGE_NAMES},
        "error": None,
        "output_url": None,
    }
