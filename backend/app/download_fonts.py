"""
Download TTF fonts for FFmpeg ASS subtitle rendering.
"""

import os
from pathlib import Path
import urllib.request

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONTS_DIR.mkdir(parents=True, exist_ok=True)

FONTS = {
    "Cairo-Bold.ttf": "https://github.com/google/fonts/raw/main/ofl/cairo/static/Cairo-Bold.ttf",
    "Almarai-Bold.ttf": "https://github.com/google/fonts/raw/main/ofl/almarai/Almarai-Bold.ttf",
    "PlusJakartaSans-Bold.ttf": "https://github.com/google/fonts/raw/main/ofl/plusjakartasans/static/PlusJakartaSans-Bold.ttf",
}

def download_fonts():
    print(f"[*] Downloading fonts to {FONTS_DIR}...")
    for filename, url in FONTS.items():
        dest = FONTS_DIR / filename
        if not dest.exists() or dest.stat().st_size < 1000:
            print(f" -> Downloading {filename} from {url}...")
            try:
                urllib.request.urlretrieve(url, str(dest))
                print(f"    [OK] Downloaded {filename} ({dest.stat().st_size} bytes)")
            except Exception as e:
                print(f"    [!] Failed to download {filename}: {e}")
        else:
            print(f"    [OK] {filename} already exists ({dest.stat().st_size} bytes)")

if __name__ == "__main__":
    download_fonts()
