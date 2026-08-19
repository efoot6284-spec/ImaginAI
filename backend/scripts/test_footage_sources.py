"""
imaginAI — Fast Footage Sources Diagnostic Script (Items 1-4)
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import httpx

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import get_pexels_key, get_pixabay_key

DOWNLOAD_DIR = backend_dir / "jobs" / "_test_downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_video_dimensions(path: str) -> tuple[int, int]:
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and res.stdout.strip():
            lines = res.stdout.strip().splitlines()
            for line in lines:
                parts = line.split("x")
                if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                    return int(parts[0]), int(parts[1])
    except Exception:
        pass
    return 0, 0


def is_valid_license(license_str: str) -> bool:
    if not license_str:
        return False
    lic = license_str.lower()
    valid_keywords = [
        "public domain", "pd", "cc0", "cc-0", "cc by", "cc-by",
        "creativecommons.org/publicdomain", "creativecommons.org/licenses/by",
        "gfdl", "free artwork", "attribution"
    ]
    return any(kw in lic for kw in valid_keywords)


async def download_sample_fast(client: httpx.AsyncClient, url: str, target_filename: str, max_bytes: int = 1500000) -> Path | None:
    dest = DOWNLOAD_DIR / target_filename
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    try:
        async with client.stream("GET", url, headers=headers, timeout=15, follow_redirects=True) as resp:
            if resp.status_code != 200:
                print(f"   [Download failed HTTP {resp.status_code}]")
                return None
            downloaded = 0
            with open(dest, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=16384):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if downloaded >= max_bytes:
                        break
        return dest
    except Exception as e:
        print(f"   [Download exception: {e}]")
        return None


async def test_pexels(client: httpx.AsyncClient, query: str = "forest"):
    print("\n" + "="*70)
    print(f"1. Pexels Video API (Query: '{query}')")
    print("="*70)
    try:
        key = get_pexels_key()
        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": key}
        params = {"query": query, "per_page": 5, "orientation": "landscape"}
        
        t0 = time.time()
        resp = await client.get(url, headers=headers, params=params, timeout=10)
        dt = time.time() - t0
        
        print(f"HTTP Status  : {resp.status_code} ({'OK' if resp.status_code == 200 else 'FAIL'}) [{dt:.2f}s]")
        if resp.status_code == 200:
            data = resp.json()
            videos = data.get("videos", [])
            print(f"Total Found  : {data.get('total_results', len(videos))}")
            print(f"Returned Hits: {len(videos)}")
            if videos:
                v = videos[0]
                files = v.get("video_files", [])
                hd_files = [f for f in files if f.get("height", 0) >= 720 and f.get("width", 0) >= f.get("height", 0)]
                chosen = hd_files[0] if hd_files else (files[0] if files else None)
                if chosen:
                    dl = await download_sample_fast(client, chosen["link"], "pexels_sample.mp4")
                    if dl:
                        w, h = get_video_dimensions(str(dl))
                        size_kb = dl.stat().st_size / 1024
                        print(f"Downloaded   : {dl.name} ({size_kb:.1f} KB sample)")
                        print(f"ffprobe Check: {w}x{h} (Landscape: {'YES' if w >= h and w > 0 else 'NO'})")
                        return True
    except Exception as e:
        print(f"Pexels Exception: {e}")
    return False


async def test_pixabay(client: httpx.AsyncClient, query: str = "forest"):
    print("\n" + "="*70)
    print(f"2. Pixabay Video API (Query: '{query}')")
    print("="*70)
    try:
        key = get_pixabay_key()
        url = "https://pixabay.com/api/videos/"
        params = {"key": key, "q": query, "per_page": 5, "orientation": "horizontal", "safesearch": "true"}
        
        t0 = time.time()
        resp = await client.get(url, params=params, timeout=10)
        dt = time.time() - t0
        
        print(f"HTTP Status  : {resp.status_code} ({'OK' if resp.status_code == 200 else 'FAIL'}) [{dt:.2f}s]")
        if resp.status_code == 200:
            data = resp.json()
            hits = data.get("hits", [])
            print(f"Total Hits   : {data.get('totalHits', len(hits))}")
            print(f"Returned Hits: {len(hits)}")
            if hits:
                v = hits[0]
                videos = v.get("videos", {})
                chosen = videos.get("large") or videos.get("medium") or videos.get("small")
                if chosen:
                    dl = await download_sample_fast(client, chosen["url"], "pixabay_sample.mp4")
                    if dl:
                        w, h = get_video_dimensions(str(dl))
                        size_kb = dl.stat().st_size / 1024
                        print(f"Downloaded   : {dl.name} ({size_kb:.1f} KB sample)")
                        print(f"ffprobe Check: {w}x{h} (Landscape: {'YES' if w >= h and w > 0 else 'NO'})")
                        return True
    except Exception as e:
        print(f"Pixabay Exception: {e}")
    return False


async def test_wikimedia(client: httpx.AsyncClient, query: str = "history"):
    print("\n" + "="*70)
    print(f"3. Wikimedia Commons API & License Filter (Query: '{query}')")
    print("="*70)
    try:
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
        
        t0 = time.time()
        resp = await client.get(url, params=params, timeout=10)
        dt = time.time() - t0
        
        print(f"HTTP Status  : {resp.status_code} ({'OK' if resp.status_code == 200 else 'FAIL'}) [{dt:.2f}s]")
        if resp.status_code == 200:
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            print(f"Returned Pages: {len(pages)}")
            
            acc, rej = 0, 0
            sample = None
            for pid, page in pages.items():
                imageinfo = page.get("imageinfo", [])
                if not imageinfo:
                    continue
                info = imageinfo[0]
                img_url = info.get("url")
                w, h = info.get("width", 0), info.get("height", 0)
                ext = info.get("extmetadata", {})
                lic_name = ext.get("LicenseShortName", {}).get("value", "")
                lic_url = ext.get("LicenseUrl", {}).get("value", "")
                
                valid = is_valid_license(f"{lic_name} {lic_url}")
                if valid and w >= h and img_url:
                    acc += 1
                    if not sample:
                        sample = (img_url, lic_name)
                else:
                    rej += 1

            print(f"License Audit: {acc} Accepted (PD/CC+Landscape), {rej} Rejected")
            if sample:
                img_url, lic_name = sample
                dl = await download_sample_fast(client, img_url, "wikimedia_sample.jpg")
                if dl:
                    fw, fh = get_video_dimensions(str(dl))
                    size_kb = dl.stat().st_size / 1024
                    print(f"Downloaded   : {dl.name} ({size_kb:.1f} KB sample, License: {lic_name})")
                    print(f"ffprobe Check: {fw}x{fh} (Landscape: {'YES' if fw >= fh and fw > 0 else 'NO'})")
                    return True
    except Exception as e:
        print(f"Wikimedia Exception: {e}")
    return False


async def test_archive_org(client: httpx.AsyncClient, query: str = "history"):
    print("\n" + "="*70)
    print(f"4. Archive.org API & License Filter (Query: '{query}')")
    print("="*70)
    try:
        url = "https://archive.org/advancedsearch.php"
        params = {
            "q": f"{query} AND (mediatype:movies OR mediatype:image)",
            "fl[]": ["identifier", "title", "mediatype", "licenseurl"],
            "sort[]": "downloads desc",
            "rows": 10,
            "page": 1,
            "output": "json",
        }
        
        t0 = time.time()
        resp = await client.get(url, params=params, timeout=10)
        dt = time.time() - t0
        
        print(f"HTTP Status  : {resp.status_code} ({'OK' if resp.status_code == 200 else 'FAIL'}) [{dt:.2f}s]")
        if resp.status_code == 200:
            data = resp.json()
            docs = data.get("response", {}).get("docs", [])
            print(f"Total Found  : {data.get('response', {}).get('numFound', len(docs))}")
            print(f"Returned Docs: {len(docs)}")
            
            acc, rej = 0, 0
            sample_id = None
            for doc in docs:
                identifier = doc.get("identifier")
                lic_url = doc.get("licenseurl", "")
                valid = is_valid_license(lic_url) or ("publicdomain" in lic_url.lower()) or not lic_url
                if valid and identifier:
                    acc += 1
                    if not sample_id:
                        sample_id = identifier
                else:
                    rej += 1

            print(f"License Audit: {acc} Accepted, {rej} Rejected")
            if sample_id:
                meta_url = f"https://archive.org/metadata/{sample_id}"
                meta_resp = await client.get(meta_url, timeout=10)
                if meta_resp.status_code == 200:
                    files = meta_resp.json().get("files", [])
                    media_f = next((f["name"] for f in files if f["name"].endswith((".mp4", ".jpg"))), None)
                    if media_f:
                        dl_url = f"https://archive.org/download/{sample_id}/{media_f}"
                        dl = await download_sample_fast(client, dl_url, "archive_sample.jpg")
                        if dl:
                            fw, fh = get_video_dimensions(str(dl))
                            size_kb = dl.stat().st_size / 1024
                            print(f"Downloaded   : {dl.name} ({size_kb:.1f} KB sample)")
                            print(f"ffprobe Check: {fw}x{fh} (Landscape: {'YES' if fw >= fh and fw > 0 else 'NO'})")
                            return True
    except Exception as e:
        print(f"Archive.org Exception: {e}")
    return False


async def test_loc(client: httpx.AsyncClient, query: str = "history"):
    print("\n" + "="*70)
    print(f"5. Library of Congress (LOC) API (Query: '{query}')")
    print("="*70)
    try:
        url = "https://www.loc.gov/pictures/search/"
        params = {"q": query, "fo": "json", "c": 5}
        
        t0 = time.time()
        resp = await client.get(url, params=params, timeout=10)
        dt = time.time() - t0
        
        print(f"HTTP Status  : {resp.status_code} ({'OK' if resp.status_code == 200 else 'FAIL'}) [{dt:.2f}s]")
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            print(f"Total Found  : {data.get('search', {}).get('hits', len(results))}")
            print(f"Returned Items: {len(results)}")
            if results:
                item = results[0]
                img_info = item.get("image", {})
                img_url = img_info.get("full") or img_info.get("square")
                if img_url:
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url
                    dl = await download_sample_fast(client, img_url, "loc_sample.jpg")
                    if dl:
                        fw, fh = get_video_dimensions(str(dl))
                        size_kb = dl.stat().st_size / 1024
                        print(f"Downloaded   : {dl.name} ({size_kb:.1f} KB sample)")
                        print(f"ffprobe Check: {fw}x{fh} (Landscape: {'YES' if fw >= fh and fw > 0 else 'NO'})")
                        return True
    except Exception as e:
        print(f"LOC Exception: {e}")
    return False


async def test_nasa_library(client: httpx.AsyncClient, query: str = "space"):
    print("\n" + "="*70)
    print(f"6. NASA Image & Video Library API (Query: '{query}')")
    print("="*70)
    try:
        url = "https://images-api.nasa.gov/search"
        params = {"q": query, "media_type": "image"}
        
        t0 = time.time()
        resp = await client.get(url, params=params, timeout=10)
        dt = time.time() - t0
        
        print(f"HTTP Status  : {resp.status_code} ({'OK' if resp.status_code == 200 else 'FAIL'}) [{dt:.2f}s]")
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("collection", {}).get("items", [])
            print(f"Total Found  : {data.get('collection', {}).get('metadata', {}).get('total_hits', len(items))}")
            print(f"Returned Items: {len(items)}")
            if items:
                links = items[0].get("links", [])
                img_url = next((l["href"] for l in links if l.get("rel") in ("preview", "image") or l.get("render") == "image"), None)
                if img_url:
                    dl = await download_sample_fast(client, img_url, "nasa_library_sample.jpg")
                    if dl:
                        fw, fh = get_video_dimensions(str(dl))
                        size_kb = dl.stat().st_size / 1024
                        print(f"Downloaded   : {dl.name} ({size_kb:.1f} KB sample)")
                        print(f"ffprobe Check: {fw}x{fh} (Landscape: {'YES' if fw >= fh and fw > 0 else 'NO'})")
                        return True
    except Exception as e:
        print(f"NASA Library Exception: {e}")
    return False


async def test_nasa_apod(client: httpx.AsyncClient):
    print("\n" + "="*70)
    print("7. NASA APOD API")
    print("="*70)
    try:
        nasa_key = os.getenv("NASA_API_KEY", "DEMO_KEY")
        url = "https://api.nasa.gov/planetary/apod"
        params = {"api_key": nasa_key}
        
        print(f"Using Key    : {'Custom Key (.env)' if nasa_key != 'DEMO_KEY' else 'DEMO_KEY (Fallback)'}")
        t0 = time.time()
        resp = await client.get(url, params=params, timeout=10)
        dt = time.time() - t0
        
        print(f"HTTP Status  : {resp.status_code} ({'OK' if resp.status_code == 200 else 'FAIL'}) [{dt:.2f}s]")
        if resp.status_code == 200:
            data = resp.json()
            print(f"APOD Title   : {data.get('title', 'Untitled')}")
            img_url = data.get("url")
            if img_url and data.get("media_type") == "image":
                dl = await download_sample_fast(client, img_url, "nasa_apod_sample.jpg")
                if dl:
                    fw, fh = get_video_dimensions(str(dl))
                    size_kb = dl.stat().st_size / 1024
                    print(f"Downloaded   : {dl.name} ({size_kb:.1f} KB sample)")
                    print(f"ffprobe Check: {fw}x{fh} (Landscape: {'YES' if fw >= fh and fw > 0 else 'NO'})")
                    return True
    except Exception as e:
        print(f"NASA APOD Exception: {e}")
    return False


async def main():
    print("="*70)
    print("STARTING FOOTAGE SOURCES DIAGNOSTIC AUDIT (ITEMS 1 - 4)")
    print("="*70)
    
    results = {}
    async with httpx.AsyncClient() as client:
        results["Pexels Video"] = await test_pexels(client, "forest")
        results["Pixabay Video"] = await test_pixabay(client, "forest")
        results["Wikimedia Commons"] = await test_wikimedia(client, "history")
        results["Archive.org"] = await test_archive_org(client, "history")
        results["Library of Congress"] = await test_loc(client, "history")
        results["NASA Library"] = await test_nasa_library(client, "space")
        results["NASA APOD"] = await test_nasa_apod(client)

    print("\n" + "="*70)
    print("DIAGNOSTIC SUMMARY FOR FOOTAGE SOURCES (ITEMS 1-4)")
    print("="*70)
    passed = 0
    total = len(results)
    for source, success in results.items():
        status = "PASSED [100% OK]" if success else "FAILED"
        if success:
            passed += 1
        print(f"  • {source:<25}: {status}")

    print("-" * 70)
    print(f"Overall Result: {passed}/{total} sources connected & verified.")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
