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

def hex_to_ass_color(hex_str: str, alpha: str = "00") -> str:
    """Convert #RRGGBB hex string to ASS &H[AA][BB][GG][RR] format."""
    if not hex_str:
        return f"&H{alpha}FFFFFF"
    clean = hex_str.lstrip("#").upper()
    if len(clean) == 6:
        r, g, b = clean[0:2], clean[2:4], clean[4:6]
        return f"&H{alpha}{b}{g}{r}"
    return f"&H{alpha}FFFFFF"


def _generate_ass_subtitles(
    caption_lines: list[dict], output_path: str, caption_config: dict | None = None
) -> str:
    """
    Generate an ASS subtitle file from caption lines.
    Supports custom font, colors (primary + highlight), alignment, background box/effects, 
    and CapCut-style animated subtitle effects (Karaoke and Pop).
    """
    cfg = caption_config or {}

    # Font
    font_raw = cfg.get("font", "Cairo")
    if font_raw in ["Geist", "Plus_Jakarta_Sans", "Plus Jakarta Sans"]:
        fontname = "Plus Jakarta Sans"
    elif font_raw == "Almarai":
        fontname = "Almarai"
    elif font_raw == "Montserrat":
        fontname = "Montserrat"
    elif font_raw == "Poppins":
        fontname = "Poppins"
    elif font_raw.startswith("custom:"):
        font_id = font_raw.split(":", 1)[1]
        from app.db import get_custom_font_by_id
        font_row = get_custom_font_by_id(font_id)
        if font_row:
            fontname = font_row["font_name"]
        else:
            fontname = "Cairo"
    else:
        fontname = font_raw or "Cairo"

    # Size
    size_percent = float(cfg.get("size_percent", 100))
    fontsize = max(24, int(54 * (size_percent / 100.0)))

    # Colors (Primary Text & Highlight Color)
    color_hex = cfg.get("color", "#FFFFFF")
    primary_color = hex_to_ass_color(color_hex)

    highlight_hex = cfg.get("highlight_color", "#FACC15")
    highlight_color = hex_to_ass_color(highlight_hex)
    secondary_color = highlight_color

    # Position
    pos_raw = cfg.get("position", "bottom")
    if pos_raw == "top":
        alignment = 8
        margin_v = 50
    elif pos_raw == "middle":
        alignment = 5
        margin_v = 0
    else:  # bottom
        alignment = 2
        margin_v = 65

    # Effect
    effect_raw = cfg.get("effect", "none")
    if effect_raw == "shadow":
        border_style = 1
        outline = 1
        shadow = 3
        back_color = "&H80000000"
    elif effect_raw == "box":
        border_style = 3
        outline = 0
        shadow = 0
        back_color = "&H96000000"
    elif effect_raw == "outline":
        border_style = 1
        outline = 3
        shadow = 0
        back_color = "&H00000000"
    else:  # none, karaoke, pop
        border_style = 1
        outline = 1
        shadow = 0
        back_color = "&H00000000"

    def _format_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    header = f"""[Script Info]
Title: imaginAI Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{fontname},{fontsize},{primary_color},{secondary_color},&H00000000,{back_color},-1,0,0,0,100,100,0,0,{border_style},{outline},{shadow},{alignment},40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    for line in caption_lines:
        start_sec = float(line["start"])
        end_sec = float(line["end"])
        text_raw = line.get("text", "").strip()
        words = text_raw.split()

        if not words:
            continue

        if effect_raw == "karaoke":
            # ASS Karaoke effect using \k tags
            dur_total = max(0.1, end_sec - start_sec)
            dur_per_word_cs = max(1, int((dur_total / len(words)) * 100))
            k_words = [f"{{\\k{dur_per_word_cs}}}{w}" for w in words]
            ass_text = " ".join(k_words)
            start_str = _format_time(start_sec)
            end_str = _format_time(end_sec)
            events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{ass_text}")

        elif effect_raw == "pop":
            # CapCut Pop effect: scale up current word & change color
            dur_total = max(0.1, end_sec - start_sec)
            word_dur = dur_total / len(words)
            for i, w in enumerate(words):
                w_start = start_sec + (i * word_dur)
                w_end = w_start + word_dur
                start_str = _format_time(w_start)
                end_str = _format_time(w_end)
                
                word_parts = []
                for j, word_item in enumerate(words):
                    if j == i:
                        word_parts.append(f"{{\\fscx130\\fscy130\\c{highlight_color}}}{word_item}{{\\r}}")
                    else:
                        word_parts.append(word_item)
                
                ass_text = " ".join(word_parts)
                events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{ass_text}")
        else:
            # Standard static subtitles
            start_str = _format_time(start_sec)
            end_str = _format_time(end_sec)
            text = text_raw.replace("\n", "\\N")
            events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}")

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
    caption_config: dict | None = None,
    scene_obj: ScriptScene | None = None,
    overlay_type: str | None = None,
) -> str:
    """
    Render one scene:
    1. Prepares each shot with Ken Burns effect and correct sub-duration
    2. Combines shots into a single background video for the scene
    3. Adds Section Overlay (numbered/stage) or Listicle overlay
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
    _generate_ass_subtitles(caption_lines, ass_path, caption_config)
    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")

    # 4. Build video filter graph (subtitles + Section Overlay / Listicle badge)
    video_filters = []

    # Check for Section Overlays (numbered or stage)
    sec_num = getattr(scene_obj, "section_number", None) if scene_obj else None
    sec_title = getattr(scene_obj, "section_title", None) if scene_obj else None

    # Fallback to style=='listicle' if sec_num is absent
    if overlay_type == "numbered" or (sec_num is not None or sec_title):
        if sec_num is not None or sec_title:
            # 1. Blur effect for first 2 seconds
            video_filters.append("boxblur=luma_radius=15:luma_power=2:enable='between(t,0,2.0)'")
            # 2. Draw section number if available
            if sec_num is not None:
                sec_num_str = f"#{sec_num}" if not str(sec_num).startswith("#") else str(sec_num)
                video_filters.append(
                    f"drawtext=text='{sec_num_str}':fontcolor=0xFACC15:fontsize=120:fontweight=bold:"
                    f"x=(w-text_w)/2:y=(h-text_h)/2-60:enable='between(t,0,2.0)'"
                )
            # 3. Draw section title if available
            if sec_title:
                clean_title = str(sec_title).replace("'", "").replace(":", "")
                video_filters.append(
                    f"drawtext=text='{clean_title}':fontcolor=white:fontsize=48:fontweight=bold:"
                    f"box=1:boxcolor=0x000000@0.7:boxborderw=18:x=(w-text_w)/2:y=(h-text_h)/2+70:"
                    f"enable='between(t,0,2.0)'"
                )
    elif overlay_type == "stage" and sec_title:
        clean_title = str(sec_title).replace("'", "").replace(":", "")
        video_filters.append(
            f"drawtext=text='{clean_title}':fontcolor=0xFACC15:fontsize=52:fontweight=bold:"
            f"box=1:boxcolor=0x000000@0.75:boxborderw=20:x=(w-text_w)/2:y=180:"
            f"enable='between(t,0,2.5)'"
        )
    elif style == "listicle":
        item_num = scene_idx + 1
        num_text = f"#{item_num}"
        badge_vf = (
            f"drawtext=text='{num_text}':fontcolor=white:fontsize=72:fontweight=bold:"
            f"box=1:boxcolor=0x000000@0.7:boxborderw=20:x=60:y=60:"
            f"enable='between(t,0,3.5)'"
        )
        video_filters.append(badge_vf)

    # Subtitles filter
    fonts_dirs = []
    default_fonts_dir = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"
    if default_fonts_dir.exists():
        fonts_dirs.append(str(default_fonts_dir).replace("\\", "/").replace(":", "\\:"))

    font_raw = (caption_config or {}).get("font", "")
    if font_raw.startswith("custom:"):
        font_id = font_raw.split(":", 1)[1]
        from app.db import get_custom_font_by_id
        font_row = get_custom_font_by_id(font_id)
        if font_row and Path(font_row["file_path"]).exists():
            custom_dir = str(Path(font_row["file_path"]).parent).replace("\\", "/").replace(":", "\\:")
            if custom_dir not in fonts_dirs:
                fonts_dirs.append(custom_dir)

    if fonts_dirs:
        fonts_dir_param = ":".join(fonts_dirs)
        video_filters.append(f"ass='{ass_escaped}':fontsdir='{fonts_dir_param}'")
    else:
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
    niche_id: str | None = None,
    caption_config: dict | None = None,
) -> str:
    """Render all scenes and concatenate into final video with style transitions and background music."""

    temp_dir = job_dir / "temp"
    temp_dir.mkdir(exist_ok=True)

    scene_outputs = []

    # Get niche overlay type if available
    overlay_type = None
    if niche_id:
        from app.niches import find_niche_info
        info = find_niche_info(niche_id)
        if info:
            overlay_type = info.get("section_overlay_type")

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
            caption_config=caption_config,
            scene_obj=scenes[i],
            overlay_type=overlay_type,
        )
        scene_outputs.append(output)

    final_output = str(job_dir / "output.mp4")

    # Simple clean concat list approach
    concat_file = str(temp_dir / "final_concat_list.txt")
    with open(concat_file, "w", encoding="utf-8") as f:
        for path in scene_outputs:
            f.write(f"file '{path.replace(chr(92), '/')}'\n")

    raw_unmixed_output = str(temp_dir / "raw_concat.mp4") if niche_id != "none" else final_output

    await asyncio.to_thread(
        _run_ffmpeg,
        [
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            raw_unmixed_output,
        ],
        "Final Scene Concatenation",
    )

    # ── Audio Ducking & Background Music Mix ──────────────────────────────────
    if niche_id != "none":
        try:
            total_duration = sum(audio_durations)
            from app.services.music import get_music_track_for_niche
            music_track = get_music_track_for_niche(niche_id, total_duration, job_dir)

            if music_track and Path(music_track).exists():
                print(f"[Render] Mixing background music track '{music_track}' with audio ducking...")
                # Audio filter: volume 15% background music mixed with main narration audio
                filter_complex = "[1:a]volume=0.15[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
                await asyncio.to_thread(
                    _run_ffmpeg,
                    [
                        "-i", raw_unmixed_output,
                        "-i", music_track,
                        "-filter_complex", filter_complex,
                        "-map", "0:v",
                        "-map", "[aout]",
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        final_output,
                    ],
                    "Background Music Audio Ducking Mix",
                )
        except Exception as e:
            print(f"[Render] Background music mix error: {e}. Falling back to unmixed audio.")
            if raw_unmixed_output != final_output and Path(raw_unmixed_output).exists():
                import shutil
                shutil.copy(raw_unmixed_output, final_output)

    print(f"[Render] Final video rendered successfully: {final_output}")
    return final_output
