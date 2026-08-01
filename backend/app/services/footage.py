"""
imaginAI — Stage 3: Stock Footage Retrieval
Searches Pexels (primary) then Pixabay (fallback) for video clips.
Downloads locally — no hotlinking.
Filters for horizontal videos (orientation=landscape/horizontal) and validates
dimensions via ffprobe after download (rejecting vertical height > width).
Splits long scenes into multiple shots according to style template max shot duration.
"""

import asyncio
import json
import math
import subprocess
import time
from pathlib import Path

import httpx

from app.config import get_pexels_key, get_pixabay_key, STYLE_MAX_SHOT_DURATION
from app.models import ScriptScene


# ── Pixabay cache (24h requirement) ─────────────────────────────────────────

_PIXABAY_CACHE_FILE = Path(__file__).resolve().parent.parent.parent / "jobs" / "_pixabay_cache.json"
_PIXABAY_CACHE_TTL = 86400  # 24 hours in seconds


def _load_pixabay_cache() -> dict:
    if _PIXABAY_CACHE_FILE.exists():
        try:
            data = json.loads(_PIXABAY_CACHE_FILE.read_text(encoding="utf-8"))
            now = time.time()
            return {k: v for k, v in data.items() if now - v.get("_ts", 0) < _PIXABAY_CACHE_TTL}
        except Exception:
            return {}
    return {}


def _save_pixabay_cache(cache: dict) -> None:
    _PIXABAY_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PIXABAY_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


# ── FFprobe video dimension validation ──────────────────────────────────────

def _get_video_dimensions(path: str) -> tuple[int, int]:
    """
    Get video width and height using ffprobe.
    Returns (width, height). Returns (0, 0) if failed.
    """
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split("x")
            if len(parts) >= 2:
                return int(parts[0]), int(parts[1])
    except Exception as e:
        print(f"[Footage] ffprobe dimensions check failed for {path}: {e}")
    return 0, 0


def _is_landscape(path: str) -> bool:
    """Return True if width >= height (landscape/horizontal format)."""
    width, height = _get_video_dimensions(path)
    if width > 0 and height > 0:
        if height > width:
            print(f"[Footage] Rejected vertical video: {width}x{height} for {path}")
            return False
    return True


# ── Pexels search ───────────────────────────────────────────────────────────

async def _search_pexels(keywords: list[str], min_duration: float, client: httpx.AsyncClient) -> list[dict]:
    """Search Pexels Videos API with orientation=landscape. Returns candidate video list."""
    query = " ".join(keywords[:3])
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": get_pexels_key()}
    params = {
        "query": query,
        "per_page": 10,
        "size": "medium",
        "orientation": "landscape",  # Force horizontal orientation
    }

    results = []
    try:
        resp = await client.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for video in data.get("videos", []):
            files = video.get("video_files", [])
            hd_files = [f for f in files if f.get("height", 0) >= 720 and (f.get("width", 0) >= f.get("height", 0))]
            chosen = hd_files[0] if hd_files else (files[0] if files else None)
            if chosen:
                results.append({
                    "source": "pexels",
                    "download_url": chosen["link"],
                    "width": chosen.get("width"),
                    "height": chosen.get("height"),
                    "duration": video.get("duration", 0),
                    "attribution": f"Video by {video.get('user', {}).get('name', 'Unknown')} from Pexels",
                    "original_url": video.get("url", ""),
                })
    except Exception as e:
        print(f"[Footage] Pexels search failed for '{query}': {e}")

    return results


# ── Pixabay search (with caching) ───────────────────────────────────────────

async def _search_pixabay(keywords: list[str], min_duration: float, client: httpx.AsyncClient) -> list[dict]:
    """Search Pixabay Videos API with orientation=horizontal and 24h caching."""
    query = " ".join(keywords[:3])
    cache_key = query.lower().strip()

    cache = _load_pixabay_cache()
    if cache_key in cache:
        print(f"[Footage] Pixabay cache hit for '{query}'")
        cached_list = cache[cache_key].get("results")
        if cached_list:
            return cached_list

    url = "https://pixabay.com/api/videos/"
    params = {
        "key": get_pixabay_key(),
        "q": query,
        "per_page": 10,
        "safesearch": "true",
        "orientation": "horizontal",  # Force horizontal orientation
    }

    results = []
    try:
        resp = await client.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for video in data.get("hits", []):
            videos = video.get("videos", {})
            chosen = videos.get("large") or videos.get("medium") or videos.get("small")
            if chosen:
                results.append({
                    "source": "pixabay",
                    "download_url": chosen["url"],
                    "width": chosen.get("width"),
                    "height": chosen.get("height"),
                    "duration": video.get("duration", 0),
                    "attribution": f"Video by {video.get('user', 'Unknown')} from Pixabay",
                    "pixabay_page": video.get("pageURL", ""),
                })

        cache[cache_key] = {"results": results, "_ts": time.time()}
        _save_pixabay_cache(cache)
    except Exception as e:
        print(f"[Footage] Pixabay search failed for '{query}': {e}")

    return results


# ── Pixabay Images search (with caching) ───────────────────────────────────

async def _search_pexels_images(keywords: list[str], client: httpx.AsyncClient) -> list[dict]:
    """Search Pexels Photos API with orientation=landscape."""
    query = " ".join(keywords[:3])
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": get_pexels_key()}
    params = {
        "query": query,
        "per_page": 10,
        "orientation": "landscape",
    }
    results = []
    try:
        resp = await client.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for photo in data.get("photos", []):
            src = photo.get("src", {})
            img_url = src.get("large2x") or src.get("large") or src.get("original")
            if img_url:
                results.append({
                    "source": "pexels_image",
                    "download_url": img_url,
                    "width": photo.get("width"),
                    "height": photo.get("height"),
                    "duration": 0,
                    "attribution": f"Photo by {photo.get('photographer', 'Unknown')} from Pexels",
                    "original_url": photo.get("url", ""),
                    "is_image": True,
                })
    except Exception as e:
        print(f"[Footage] Pexels image search failed for '{query}': {e}")

    return results


async def _search_pixabay_images(keywords: list[str], client: httpx.AsyncClient) -> list[dict]:
    """Search Pixabay Photos API with orientation=horizontal and 24h caching."""
    query = " ".join(keywords[:3])
    cache_key = f"img_{query.lower().strip()}"

    cache = _load_pixabay_cache()
    if cache_key in cache:
        cached_list = cache[cache_key].get("results")
        if cached_list:
            return cached_list

    url = "https://pixabay.com/api/"
    params = {
        "key": get_pixabay_key(),
        "q": query,
        "per_page": 10,
        "safesearch": "true",
        "orientation": "horizontal",
        "image_type": "photo",
    }

    results = []
    try:
        resp = await client.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for hit in data.get("hits", []):
            img_url = hit.get("largeImageURL") or hit.get("webformatURL")
            if img_url:
                results.append({
                    "source": "pixabay_image",
                    "download_url": img_url,
                    "width": hit.get("imageWidth"),
                    "height": hit.get("imageHeight"),
                    "duration": 0,
                    "attribution": f"Photo by {hit.get('user', 'Unknown')} from Pixabay",
                    "pixabay_page": hit.get("pageURL", ""),
                    "is_image": True,
                })

        cache[cache_key] = {"results": results, "_ts": time.time()}
        _save_pixabay_cache(cache)
    except Exception as e:
        print(f"[Footage] Pixabay image search failed for '{query}': {e}")

    return results


# ── Download file to local disk ─────────────────────────────────────────────

async def _download_video(url: str, output_path: str, client: httpx.AsyncClient) -> None:
    """Download a video/image file to local disk (no hotlinking)."""
    async with client.stream("GET", url, timeout=60, follow_redirects=True) as resp:
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            async for chunk in resp.aiter_bytes(chunk_size=8192):
                f.write(chunk)
    print(f"[Footage] Downloaded to {output_path}")


# ── Fetch single clip/image with landscape verification ────────────────────

async def fetch_footage_for_shot(
    keywords: list[str],
    min_duration: float,
    output_path: str,
    attr_path: str,
    client: httpx.AsyncClient,
    used_urls: set[str],
) -> str:
    """Fetch clip: Pexels Video -> Pixabay Video -> Pexels Image -> Pixabay Image fallback."""
    # 1. Pexels Video
    candidates = await _search_pexels(keywords, min_duration, client)

    # 2. Pixabay Video
    if not candidates:
        print(f"[Footage] Pexels video had no results for {keywords}, trying Pixabay video...")
        candidates = await _search_pixabay(keywords, min_duration, client)

    # 3. Pexels Image Fallback
    if not candidates:
        print(f"[Footage] No video found for {keywords}, trying Pexels image fallback...")
        candidates = await _search_pexels_images(keywords, client)

    # 4. Pixabay Image Fallback
    if not candidates:
        print(f"[Footage] No Pexels image found for {keywords}, trying Pixabay image fallback...")
        candidates = await _search_pixabay_images(keywords, client)

    # 5. Single broader keyword fallbacks
    if not candidates:
        for kw in keywords:
            candidates = await _search_pexels([kw], min_duration, client)
            if candidates:
                break
        if not candidates:
            for kw in keywords:
                candidates = await _search_pexels_images([kw], client)
                if candidates:
                    break

    if not candidates:
        raise RuntimeError(f"No footage or image found for keywords: {keywords}")

    # Pick candidate not in used_urls, or first one
    chosen = None
    for cand in candidates:
        if cand["download_url"] not in used_urls:
            chosen = cand
            break
    if not chosen:
        chosen = candidates[0]

    used_urls.add(chosen["download_url"])

    # Determine final file path (if image, use .jpg extension)
    is_image = chosen.get("is_image", False)
    final_output_path = output_path
    if is_image and not final_output_path.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        final_output_path = str(Path(output_path).with_suffix(".jpg"))

    # Download locally
    await _download_video(chosen["download_url"], final_output_path, client)

    # Post-download verification via ffprobe (skip strict height check for images if valid)
    if not is_image and not _is_landscape(final_output_path):
        print(f"[Footage] Downloaded clip was not landscape ({final_output_path}). Trying next candidate...")
        for cand in candidates:
            if cand["download_url"] == chosen["download_url"]:
                continue
            await _download_video(cand["download_url"], final_output_path, client)
            if _is_landscape(final_output_path):
                chosen = cand
                used_urls.add(chosen["download_url"])
                break

    # Save attribution
    attr_data = {
        "source": chosen["source"],
        "attribution": chosen["attribution"],
        "keywords": keywords,
        "is_image": is_image,
    }
    Path(attr_path).write_text(json.dumps(attr_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return final_output_path


# ── All scenes & shots fetching ─────────────────────────────────────────────

async def fetch_all_footage(
    scenes: list[ScriptScene],
    audio_durations: list[float],
    job_dir: Path,
    style: str = "documentary",
) -> list[list[str]]:
    """
    Fetch footage for all scenes, splitting long scenes into multiple shots
    based on style's MAX_SHOT_DURATION.
    Returns list of list of clip paths per scene: [[s0_shot0, s0_shot1], [s1_shot0], ...]
    """
    clips_dir = job_dir / "clips"
    clips_dir.mkdir(exist_ok=True)

    max_shot_dur = STYLE_MAX_SHOT_DURATION.get(style, 10.0)
    all_scene_shots: list[list[str]] = []
    used_urls: set[str] = set()

    async with httpx.AsyncClient() as client:
        for scene_idx, scene in enumerate(scenes):
            scene_duration = audio_durations[scene_idx]
            # Calculate how many shots needed for this scene
            num_shots = max(1, math.ceil(scene_duration / max_shot_dur))
            shot_target_dur = scene_duration / num_shots

            print(
                f"[Footage] Scene {scene_idx} ({scene_duration:.2f}s, style='{style}') "
                f"split into {num_shots} shot(s) (~{shot_target_dur:.2f}s each)"
            )

            scene_clip_paths = []
            for shot_idx in range(num_shots):
                output = str(clips_dir / f"scene_{scene_idx}_shot_{shot_idx}.mp4")
                attr = str(clips_dir / f"scene_{scene_idx}_shot_{shot_idx}_attr.json")

                # Keyword variations per shot for variety
                kw = scene.visual_keywords.copy()
                if shot_idx > 0 and len(kw) > 1:
                    # Rotate or modify keywords slightly for different shots
                    kw = kw[shot_idx % len(kw):] + kw[:shot_idx % len(kw)]

                await fetch_footage_for_shot(
                    keywords=kw,
                    min_duration=shot_target_dur,
                    output_path=output,
                    attr_path=attr,
                    client=client,
                    used_urls=used_urls,
                )
                scene_clip_paths.append(output)

                if shot_idx < num_shots - 1:
                    await asyncio.sleep(0.3)

            all_scene_shots.append(scene_clip_paths)

            if scene_idx < len(scenes) - 1:
                await asyncio.sleep(0.5)

    print(f"[Footage] Fetched footage for {len(scenes)} scenes (total shots: {sum(len(s) for s in all_scene_shots)})")
    return all_scene_shots
