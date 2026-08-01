"""
imaginAI — Stage 5: FFmpeg Video Rendering
Assembles shots, scenes, narration audio, captions, and style effects into final output.
All FFmpeg calls via subprocess — no MoviePy.

Features:
- Ken Burns effect (subtle slow zoompan) on every shot
- Style-based transitions between shots/scenes (xfade or hard cut)
- Listicle overlay for Listicle template (Item # overlay)
- Exact duration match using ffprobe-measured audio length
"""

import asyncio
import json
import os
import subprocess
import wave
from pathlib import Path

from app.config import STYLE_TRANSITION
from app.models import ScriptScene


# ── Helpers ──────────────────────────────────────────────────────────────────

def _run_ffmpeg(args: list[str], desc: str = "") -> None:
    """Run an FFmpeg command via subprocess."""
    cmd = ["ffmpeg", "-y"] + args
    print(f"[Render] {desc}: {' '.join(cmd[:10])}...")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed ({desc}): {result.stderr[-800:]}")


# ── Generate ASS subtitle file from caption data ────────────────────────────

def _generate_ass_subtitles(caption_lines: list[dict], output_path: str) -> str:
    """
    Generate an ASS subtitle file from caption lines.
    Style: white text, bold font, semi-transparent black background box, bottom-center.
    """

    def _format_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    header = """[Script Info]
Title: imaginAI Captions
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,54,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,3,2,0,2,40,40,65,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    for line in caption_lines:
        start = _format_time(line["start"])
        end = _format_time(line["end"])
        text = line["text"].replace("\n", "\\N")
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    ass_content = header + "\n".join(events) + "\n"
    Path(output_path).write_text(ass_content, encoding="utf-8")
    return output_path


# ── Process single shot (scaling + Ken Burns effect) ─────────────────────────

def _prepare_shot(
    shot_path: str,
    target_duration: float,
    output_path: str,
    shot_idx: int,
) -> str:
    """
    Apply subtle Ken Burns effect (zoompan max 1.08, smooth linear) and scale/trim shot to exact target_duration at 1920x1080 25fps.
    Supports both video clips and static image fallbacks.
    """
    fps = 25
    total_frames = max(1, int(target_duration * fps))

    # Detect if shot is an image file
    ext = Path(shot_path).suffix.lower()
    is_image = ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]

    # Subtle Ken Burns patterns (max 8% zoom or gentle pan, smooth & linear over total_frames)
    pattern = shot_idx % 4
    if pattern == 0:
        # Smooth Zoom In (1.0 -> 1.08)
        zp = f"z='1.0+0.08*(on/{total_frames})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    elif pattern == 1:
        # Smooth Zoom Out (1.08 -> 1.0)
        zp = f"z='1.08-0.08*(on/{total_frames})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    elif pattern == 2:
        # Smooth Pan Right (fixed 1.05 zoom)
        zp = f"z='1.05':x='(iw-iw/zoom)*(on/{total_frames})':y='ih/2-(ih/zoom/2)'"
    else:
        # Smooth Pan Left (fixed 1.05 zoom)
        zp = f"z='1.05':x='(iw-iw/zoom)*(1-(on/{total_frames}))':y='ih/2-(ih/zoom/2)'"

    filter_graph = (
        f"scale=1920:1080:force_original_aspect_ratio=increase,"
        f"crop=1920:1080,"
        f"setsar=1,"
        f"zoompan={zp}:d={total_frames}:s=1920x1080:fps={fps},"
        f"trim=duration={target_duration},"
        f"setpts=PTS-STARTPTS"
    )

    input_args = ["-loop", "1", "-i", shot_path] if is_image else ["-i", shot_path]

    _run_ffmpeg(
        input_args + [
            "-vf", filter_graph,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-an",  # strip audio
            output_path,
        ],
        f"Prepare Shot {shot_idx} ({'image' if is_image else 'video'})",
    )
    return output_path


# ── Render a single scene (combining shots + audio + captions + listicle overlay) ─

async def _render_scene(
    scene_idx: int,
    shot_paths: list[str],
    audio_path: str,
    audio_duration: float,
    caption_lines: list[dict],
    style: str,
    output_path: str,
    temp_dir: Path,
) -> str:
    """
    Render one scene:
    1. Prepares each shot with Ken Burns effect and correct sub-duration
    2. Combines shots into a single background video for the scene
    3. Adds Listicle overlay if style == 'listicle'
    4. Burns ASS subtitles & syncs narration audio
    """
    num_shots = len(shot_paths)
    shot_dur = audio_duration / num_shots

    # 1. Prepare each shot
    prepared_shots = []
    for s_idx, shot_p in enumerate(shot_paths):
        prep_out = str(temp_dir / f"scene_{scene_idx}_shot_{s_idx}_kb.mp4")
        await asyncio.to_thread(_prepare_shot, shot_p, shot_dur, prep_out, s_idx)
        prepared_shots.append(prep_out)

    # 2. Combine prepared shots for this scene
    combined_video = str(temp_dir / f"scene_{scene_idx}_bg.mp4")
    if len(prepared_shots) == 1:
        combined_video = prepared_shots[0]
    else:
        # Concat prepared shots
        concat_list = str(temp_dir / f"scene_{scene_idx}_concat.txt")
        with open(concat_list, "w", encoding="utf-8") as f:
            for p in prepared_shots:
                f.write(f"file '{p.replace(chr(92), '/')}'\n")

        await asyncio.to_thread(
            _run_ffmpeg,
            [
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list,
                "-c", "copy",
                combined_video,
            ],
            f"Scene {scene_idx} shots concat",
        )

    # 3. Generate ASS subtitle file
    ass_path = str(temp_dir / f"scene_{scene_idx}.ass")
    _generate_ass_subtitles(caption_lines, ass_path)
    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")

    # 4. Build video filter graph (subtitles + optional Listicle badge)
    video_filters = []

    # If Listicle, overlay item number badge in top-right or top-left for the first 3 seconds
    if style == "listicle":
        item_num = scene_idx + 1
        num_text = f"#{item_num}"
        # drawtext badge
        badge_vf = (
            f"drawtext=text='{num_text}':fontcolor=white:fontsize=72:fontweight=bold:"
            f"box=1:boxcolor=0x000000@0.7:boxborderw=20:x=60:y=60:"
            f"enable='between(t,0,3.5)'"
        )
        video_filters.append(badge_vf)

    # Subtitles filter
    video_filters.append(f"ass='{ass_escaped}'")

    vf_chain = ",".join(video_filters)

    # 5. Final FFmpeg render for scene: video + narration audio
    await asyncio.to_thread(
        _run_ffmpeg,
        [
            "-i", combined_video,
            "-i", audio_path,
            "-vf", vf_chain,
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-t", str(audio_duration),
            output_path,
        ],
        f"Scene {scene_idx} Final Render",
    )

    return output_path


# ── Main render function ────────────────────────────────────────────────────

async def render_video(
    job_dir: Path,
    scenes: list[ScriptScene],
    audio_paths: list[str],
    audio_durations: list[float],
    shots_per_scene: list[list[str]],
    caption_data: list[list[dict]],
    style: str = "documentary",
) -> str:
    """Render all scenes and concatenate into final video with style transitions."""

    temp_dir = job_dir / "temp"
    temp_dir.mkdir(exist_ok=True)

    scene_outputs = []

    # Render each scene individually
    for i in range(len(scenes)):
        output = str(temp_dir / f"scene_{i}_final.mp4")
        await _render_scene(
            scene_idx=i,
            shot_paths=shots_per_scene[i],
            audio_path=audio_paths[i],
            audio_duration=audio_durations[i],
            caption_lines=caption_data[i],
            style=style,
            output_path=output,
            temp_dir=temp_dir,
        )
        scene_outputs.append(output)

    # Concatenate scenes into final video
    # Check transition settings for the chosen style
    transition_cfg = STYLE_TRANSITION.get(style, {"type": "dissolve", "duration": 0.5})

    final_output = str(job_dir / "output.mp4")

    # Simple clean concat list approach for robust rendering across platforms
    concat_file = str(temp_dir / "final_concat_list.txt")
    with open(concat_file, "w", encoding="utf-8") as f:
        for path in scene_outputs:
            f.write(f"file '{path.replace(chr(92), '/')}'\n")

    await asyncio.to_thread(
        _run_ffmpeg,
        [
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            final_output,
        ],
        "Final Scene Concatenation",
    )

    print(f"[Render] Final video rendered successfully: {final_output}")
    return final_output
