"""
imaginAI Backend — Pydantic Models
Schemas for requests, responses, and internal data structures.
"""

from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


# ── Request / Response ───────────────────────────────────────────────────────

DurationType = Literal["5_min", "8_min", "10_min", "short", "medium"]
DEFAULT_DURATION: DurationType = "5_min"


class JobRequest(BaseModel):
    """POST /api/jobs request body."""
    idea: str = Field(..., min_length=3, max_length=2000, description="The user's video idea")
    duration: DurationType = Field(
        default=DEFAULT_DURATION, description="5 min, 8 min, or 10 min"
    )
    style: Literal["mystery", "listicle", "documentary", "motivational"] = Field(
        "documentary", description="Montage style template"
    )
    voice_provider: Literal["gemini", "edge-tts", "gtts"] = Field("edge-tts", description="TTS Provider")
    voice: str = Field("ar-SA-HamedNeural", description="TTS voice identifier")


class JobStatusResponse(BaseModel):
    """GET /api/jobs/{job_id}/status response."""
    job_id: str
    status: Literal["pending", "processing", "done", "failed"]
    current_stage: Optional[str] = None
    stages: dict[str, Literal["pending", "processing", "done", "failed"]]
    error: Optional[str] = None
    output_url: Optional[str] = None


# ── Internal data ────────────────────────────────────────────────────────────

class ScriptScene(BaseModel):
    """One scene from the generated script."""
    narration: str
    visual_keywords: list[str]
    estimated_seconds: float  # kept for schema compatibility; real duration comes from ffprobe


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
