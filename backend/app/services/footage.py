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


# ── License Validation Helper ────────────────────────────────────────────────

def _is_valid_license(extmetadata: dict, license_url_str: str = "") -> bool:
    """Return True if license is Public Domain, CC0, CC-BY, or open license."""
    lic_name = str(extmetadata.get("LicenseShortName", {}).get("value", "")).lower()
    lic_url = str(extmetadata.get("LicenseUrl", {}).get("value", "") or license_url_str).lower()
    usage_terms = str(extmetadata.get("UsageTerms", {}).get("value", "")).lower()
    combined = f"{lic_name} {lic_url} {usage_terms}"
    
    valid_keywords = [
        "public domain", "pd", "cc0", "cc-0", "cc by", "cc-by",
        "creativecommons.org/publicdomain", "creativecommons.org/licenses/by",
        "gfdl", "free artwork", "attribution"
    ]
    return any(kw in combined for kw in valid_keywords)


# ── Wikimedia & Archive.org & NASA Media search fallbacks ────────────────────

async def _search_wikimedia(keywords: list[str], client: httpx.AsyncClient) -> list[dict]:
    """Search Wikimedia Commons for public domain/CC landscape images and media."""
    query = " ".join(keywords[:3])
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"file:{query} landscape",
        "gsrlimit": 10,
        "prop": "imageinfo",
        "iiprop": "url|mime|dimensions|extmetadata",
    }
    results = []
    accepted_count = 0
    rejected_count = 0
    try:
        resp = await client.get(url, params=params, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            for pid, page in pages.items():
                imageinfo = page.get("imageinfo", [])
                if not imageinfo:
                    continue
                info = imageinfo[0]
                img_url = info.get("url")
                width = info.get("width", 0)
                height = info.get("height", 0)
                mime = info.get("mime", "")
                ext = info.get("extmetadata", {})
                
                # Mandatory license filtering condition
                lic_valid = _is_valid_license(ext)
                if img_url and (width >= height) and ("image" in mime or "video" in mime):
                    if lic_valid:
                        accepted_count += 1
                        artist = ext.get("Artist", {}).get("value", "Wikimedia Contributor")
                        results.append({
                            "source": "wikimedia",
                            "download_url": img_url,
                            "width": width,
                            "height": height,
                            "duration": 0,
                            "attribution": f"Media by {artist} from Wikimedia Commons",
                            "is_image": True,
                        })
                    else:
                        rejected_count += 1
                        lic_name = ext.get("LicenseShortName", {}).get("value", "Unknown")
                        print(f"[Footage] [Wikimedia REJECTED] '{page.get('title')}' due to non-free license: {lic_name}")
                else:
                    rejected_count += 1
            print(f"[Footage] [Wikimedia License Audit] Query '{query}': {accepted_count} Accepted, {rejected_count} Rejected")
    except Exception as e:
        print(f"[Footage] Wikimedia search failed for '{query}': {e}")
    return results


async def _search_archive_org(keywords: list[str], client: httpx.AsyncClient) -> list[dict]:
    """Search Archive.org for Public Domain / CC movies and images."""
    query = " ".join(keywords[:3])
    url = "https://archive.org/advancedsearch.php"
    params = {
        "q": f"{query} AND (mediatype:movies OR mediatype:image)",
        "fl[]": ["identifier", "title", "mediatype", "licenseurl"],
        "sort[]": "downloads desc",
        "rows": 8,
        "output": "json",
    }
    results = []
    accepted_count = 0
    rejected_count = 0
    try:
        resp = await client.get(url, params=params, timeout=12)
        if resp.status_code == 200:
            docs = resp.json().get("response", {}).get("docs", [])
            for doc in docs:
                identifier = doc.get("identifier")
                lic_url = doc.get("licenseurl", "")
                is_valid = _is_valid_license({}, lic_url) or ("publicdomain" in lic_url.lower()) or not lic_url
                if is_valid and identifier:
                    accepted_count += 1
                    meta_url = f"https://archive.org/metadata/{identifier}"
                    try:
                        m_resp = await client.get(meta_url, timeout=8)
                        if m_resp.status_code == 200:
                            files = m_resp.json().get("files", [])
                            media_f = next((f["name"] for f in files if f.get("name", "").endswith((".mp4", ".jpg", ".jpeg"))), None)
                            if media_f:
                                is_img = not media_f.endswith(".mp4")
                                results.append({
                                    "source": "archive_org",
                                    "download_url": f"https://archive.org/download/{identifier}/{media_f}",
                                    "width": 1920,
                                    "height": 1080,
                                    "duration": 0 if is_img else 10,
                                    "attribution": f"Media from Archive.org ({doc.get('title', identifier)})",
                                    "is_image": is_img,
                                })
                    except Exception:
                        pass
                else:
                    rejected_count += 1
                    print(f"[Footage] [Archive.org REJECTED] '{identifier}' due to non-free license: {lic_url}")
            print(f"[Footage] [Archive.org License Audit] Query '{query}': {accepted_count} Accepted, {rejected_count} Rejected")
    except Exception as e:
        print(f"[Footage] Archive.org search failed for '{query}': {e}")
    return results


async def _search_loc(keywords: list[str], client: httpx.AsyncClient) -> list[dict]:
    """Search Library of Congress (LOC) API for historical media."""
    query = " ".join(keywords[:3])
    url = "https://www.loc.gov/pictures/search/"
    params = {"q": query, "fo": "json", "c": 6}
    results = []
    try:
        resp = await client.get(url, params=params, timeout=12)
        if resp.status_code == 200:
            hits = resp.json().get("results", [])
            for item in hits:
                img_info = item.get("image", {})
                img_url = img_info.get("full") or img_info.get("square")
                if img_url:
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url
                    results.append({
                        "source": "loc",
                        "download_url": img_url,
                        "width": 1920,
                        "height": 1080,
                        "duration": 0,
                        "attribution": f"Historical media courtesy of Library of Congress ({item.get('title', 'LOC')})",
                        "is_image": True,
                    })
    except Exception as e:
        print(f"[Footage] LOC search failed for '{query}': {e}")
    return results


async def _search_nasa(keywords: list[str], client: httpx.AsyncClient) -> list[dict]:
    """Search NASA Image and Video Library API for space/science media."""
    query = " ".join(keywords[:3])
    url = "https://images-api.nasa.gov/search"
    params = {
        "q": query,
        "media_type": "image",
    }
    results = []
    try:
        resp = await client.get(url, params=params, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("collection", {}).get("items", [])[:6]
            for item in items:
                links = item.get("links", [])
                data_info = item.get("data", [{}])[0]
                img_url = None
                for link in links:
                    if link.get("rel") == "preview" or link.get("render") == "image":
                        img_url = link.get("href")
                        break
                if img_url:
                    results.append({
                        "source": "nasa",
                        "download_url": img_url,
                        "width": 1920,
                        "height": 1080,
                        "duration": 0,
                        "attribution": f"Media courtesy of NASA ({data_info.get('title', 'Public Domain')})",
                        "is_image": True,
                    })
    except Exception as e:
        print(f"[Footage] NASA search failed for '{query}': {e}")
    return results


async def _search_nasa_apod(client: httpx.AsyncClient) -> list[dict]:
    """Fetch NASA APOD (Astronomy Picture of the Day)."""
    import os
    nasa_key = os.getenv("NASA_API_KEY", "DEMO_KEY")
    url = "https://api.nasa.gov/planetary/apod"
    params = {"api_key": nasa_key}
    results = []
    try:
        resp = await client.get(url, params=params, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            img_url = data.get("url")
            if img_url and data.get("media_type") == "image":
                results.append({
                    "source": "nasa_apod",
                    "download_url": img_url,
                    "width": 1920,
                    "height": 1080,
                    "duration": 0,
                    "attribution": f"NASA APOD: {data.get('title', 'Space Image')}",
                    "is_image": True,
                })
    except Exception as e:
        print(f"[Footage] NASA APOD failed: {e}")
    return results


# ── Download file to local disk with Retries & User-Agent ────────────────────

async def _download_video(url: str, output_path: str, client: httpx.AsyncClient, max_retries: int = 3) -> None:
    """Download a video/image file to local disk with automatic retry on network drops."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }
    
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            async with client.stream("GET", url, headers=headers, timeout=90, follow_redirects=True) as resp:
                resp.raise_for_status()
                with open(output_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=16384):
                        f.write(chunk)
            print(f"[Footage] Downloaded to {output_path} (attempt {attempt})")
            return
        except Exception as e:
            last_err = e
            print(f"[Footage] Download attempt {attempt}/{max_retries} failed for {url}: {e}")
            # Clean incomplete file
            if Path(output_path).exists():
                try:
                    Path(output_path).unlink()
                except Exception:
                    pass
            if attempt < max_retries:
                await asyncio.sleep( attempt * 1.5 )
                
    raise RuntimeError(f"Failed to download footage after {max_retries} attempts: {last_err}")


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

    # 5. Wikimedia Commons Fallback
    if not candidates:
        print(f"[Footage] Trying Wikimedia Commons fallback for {keywords}...")
        candidates = await _search_wikimedia(keywords, client)

    # 6. Archive.org Fallback
    if not candidates:
        print(f"[Footage] Trying Archive.org fallback for {keywords}...")
        candidates = await _search_archive_org(keywords, client)

    # 7. Library of Congress (LOC) Fallback
    if not candidates:
        print(f"[Footage] Trying Library of Congress (LOC) fallback for {keywords}...")
        candidates = await _search_loc(keywords, client)

    # 8. NASA Media Fallback
    if not candidates:
        print(f"[Footage] Trying NASA Media API fallback for {keywords}...")
        candidates = await _search_nasa(keywords, client)

    # 9. NASA APOD Fallback
    if not candidates:
        print(f"[Footage] Trying NASA APOD fallback for {keywords}...")
        candidates = await _search_nasa_apod(client)

    # 10. Single broader keyword fallbacks
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

    # Try downloading candidates sequentially until one succeeds
    downloaded_successfully = False
    chosen = None
    final_output_path = output_path

    # Prioritize candidates not yet used
    ordered_candidates = [c for c in candidates if c["download_url"] not in used_urls] + [c for c in candidates if c["download_url"] in used_urls]

    for cand in ordered_candidates:
        is_image = cand.get("is_image", False)
        target_path = output_path
        if is_image and not target_path.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            target_path = str(Path(output_path).with_suffix(".jpg"))

        try:
            await _download_video(cand["download_url"], target_path, client)
            
            # Post-download verification via ffprobe (skip height check for images if valid)
            if not is_image and not _is_landscape(target_path):
                print(f"[Footage] Clip was not landscape ({target_path}), trying next candidate...")
                Path(target_path).unlink(missing_ok=True)
                continue
                
            chosen = cand
            final_output_path = target_path
            used_urls.add(chosen["download_url"])
            downloaded_successfully = True
            print(f"[Footage] [Shot Source Resolution] Source='{chosen['source']}' ({'IMAGE' if chosen.get('is_image') else 'VIDEO'}) for keywords={keywords}")
            break
        except Exception as dl_err:
            print(f"[Footage] Candidate download failed ({cand['download_url']}): {dl_err}. Trying next candidate...")
            continue

    if not downloaded_successfully or not chosen:
        print(f"[Footage] All download candidates failed for {keywords}. Generating local emergency dark frame...")
        fallback_img = str(Path(output_path).with_suffix(".jpg"))
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x0f172a:s=1920x1080:d=1", "-vframes", "1", fallback_img],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            final_output_path = fallback_img
            chosen = {
                "source": "imaginAI local fallback",
                "attribution": "Generated by imaginAI",
                "is_image": True,
            }
        except Exception as ff_err:
            raise RuntimeError(f"All candidates and local fallback generation failed: {ff_err}")

    # Save attribution
    attr_data = {
        "source": chosen["source"],
        "attribution": chosen["attribution"],
        "keywords": keywords,
        "is_image": chosen.get("is_image", False),
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
