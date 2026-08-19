"""
imaginAI — Royalty-Free Background Music Manager
Provides curated music tracks mapped to niches and procedural ambient audio generation as fallback.
"""

import math
import wave
import struct
from pathlib import Path
from typing import Dict, Any, List

MUSIC_CATALOG: Dict[str, Dict[str, Any]] = {
    "dark_ambient": {
        "title": "غموض وظلال خافية",
        "genre": "Dark Ambient",
        "description": "موسيقى هادئة وتوتيرية تناسب قصص الرعب والجرائم",
        "bpm": 60,
        "base_freqs": [110, 138, 164],
    },
    "epic_oriental": {
        "title": "أصداء الشرق العظيمة",
        "genre": "Epic Oriental",
        "description": "أنغام تاريخية وملحمية شرقية مناسبة للتاريخ والتراث",
        "bpm": 80,
        "base_freqs": [146, 174, 220],
    },
    "cinematic_orchestral": {
        "title": "أوركسترا سينمائية",
        "genre": "Cinematic Orchestral",
        "description": "أجواء مهيبة وملحمية للحضارات القديمة والمعارك",
        "bpm": 90,
        "base_freqs": [130, 164, 196],
    },
    "corporate_inspiring": {
        "title": "إلهام ريادة الأعمال",
        "genre": "Corporate Inspiring",
        "description": "إيقاع حديث وتحفيزي مناسب للمال والأعمال",
        "bpm": 110,
        "base_freqs": [174, 220, 261],
    },
    "synthwave_future": {
        "title": "نبض المستقبل الرقمي",
        "genre": "Future Synth",
        "description": "إلكترونيك مستقبلي مناسب للذكاء الاصطناعي والتكنولوجيا",
        "bpm": 100,
        "base_freqs": [130, 174, 261],
    },
    "cosmic_ambient": {
        "title": "أعماق الفلك والكون",
        "genre": "Cosmic Ambient",
        "description": "ألحان فضائية ساحرة ومسترخية للكون والفيزياء",
        "bpm": 55,
        "base_freqs": [98, 146, 196],
    },
    "calm_acoustic": {
        "title": "هدوء وتطوير الذات",
        "genre": "Acoustic Chill",
        "description": "أنغام هادئة مريحة للأعصاب وعلم النفس",
        "bpm": 70,
        "base_freqs": [164, 220, 293],
    },
}


def generate_procedural_background_track(track_id: str, duration_sec: float, output_path: str) -> str:
    """
    Generate a high-quality ambient background WAV track procedurally
    if no MP3/WAV file exists locally. Ensures 100% reliable background audio out-of-the-box.
    """
    info = MUSIC_CATALOG.get(track_id, MUSIC_CATALOG["dark_ambient"])
    base_freqs = info["base_freqs"]
    sample_rate = 44100
    num_samples = int(sample_rate * duration_sec)

    out_file = wave.open(output_path, "w")
    out_file.setnchannels(2)  # Stereo
    out_file.setsampwidth(2)  # 16-bit
    out_file.setframerate(sample_rate)

    out = bytearray()
    for i in range(num_samples):
        t = i / sample_rate
        # Slow ambient drone wave with gentle LFO modulating harmonic amplitude
        lfo = 0.6 + 0.4 * math.sin(2 * math.pi * 0.1 * t)
        
        sample_l = 0.0
        sample_r = 0.0
        for idx, freq in enumerate(base_freqs):
            w = 2 * math.pi * freq * t
            amp = (0.15 / (idx + 1)) * lfo
            sample_l += amp * math.sin(w)
            sample_r += amp * math.cos(w + 0.3)

        # Soft clip & scale to 16-bit PCM integer
        val_l = int(max(-32767, min(32767, sample_l * 10000)))
        val_r = int(max(-32767, min(32767, sample_r * 10000)))
        out.extend(struct.pack("<hh", val_l, val_r))

    out_file.writeframes(out)
    out_file.close()
    print(f"[Music] Generated procedural ambient music track '{track_id}' ({duration_sec:.1f}s) to {output_path}")
    return output_path


def get_music_track_for_niche(niche_id: str | None, total_seconds: float, job_dir: Path) -> str | None:
    """
    Return local music file path for the given niche.
    If no pre-existing MP3 audio track is present in data/music, generates a high-quality ambient track.
    """
    if niche_id == "none":
        return None

    from app.niches import find_niche_info
    niche_info = find_niche_info(niche_id or "") if niche_id else None
    track_id = niche_info.get("music_style", "dark_ambient") if niche_info else "dark_ambient"

    music_dir = job_dir / "music"
    music_dir.mkdir(exist_ok=True)
    custom_track_path = music_dir / f"{track_id}.wav"

    if not custom_track_path.exists():
        generate_procedural_background_track(track_id, total_seconds + 5.0, str(custom_track_path))

    return str(custom_track_path)
