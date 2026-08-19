"""
imaginAI Database Module — SQLite Persistence
Handles storage for devices, projects, and videos in backend/data/imaginai.db.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import DATA_DIR

DB_PATH: Path = DATA_DIR / "imaginai.db"


def get_db_connection() -> sqlite3.Connection:
    """Return a thread-safe connection to the SQLite database."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize database schema if tables do not exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # devices table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                first_seen_at TEXT NOT NULL
            )
        """)

        # projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                niche TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (device_id) REFERENCES devices (device_id) ON DELETE CASCADE
            )
        """)

        # videos table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                file_path TEXT,
                duration REAL DEFAULT 0.0,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'processing',
                FOREIGN KEY (project_id) REFERENCES projects (project_id) ON DELETE CASCADE
            )
        """)

        # custom_voices table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_voices (
                id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                name TEXT NOT NULL,
                fish_voice_id TEXT NOT NULL,
                sample_url TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (device_id) REFERENCES devices (device_id) ON DELETE CASCADE
            )
        """)

        # custom_fonts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_fonts (
                id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                font_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (device_id) REFERENCES devices (device_id) ON DELETE CASCADE
            )
        """)

        conn.commit()


# ── Device Operations ────────────────────────────────────────────────────────

def get_or_create_device(device_id: str) -> Dict[str, Any]:
    """Get device or create if it doesn't exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute("INSERT INTO devices (device_id, first_seen_at) VALUES (?, ?)", (device_id, now))
        conn.commit()
        return {"device_id": device_id, "first_seen_at": now}


def clear_device_data(device_id: str) -> None:
    """Delete all projects and videos associated with a device_id."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Find all project_ids for device
        cursor.execute("SELECT project_id FROM projects WHERE device_id = ?", (device_id,))
        project_rows = cursor.fetchall()
        project_ids = [r["project_id"] for r in project_rows]
        
        if project_ids:
            placeholders = ",".join("?" * len(project_ids))
            cursor.execute(f"DELETE FROM videos WHERE project_id IN ({placeholders})", project_ids)
        
        cursor.execute("DELETE FROM projects WHERE device_id = ?", (device_id,))
        cursor.execute("DELETE FROM devices WHERE device_id = ?", (device_id,))
        conn.commit()


# ── Project Operations ───────────────────────────────────────────────────────

def create_project(project_id: str, device_id: str, domain: str, niche: str, name: str) -> Dict[str, Any]:
    """Create a new project linked to device_id."""
    get_or_create_device(device_id)
    now = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO projects (project_id, device_id, domain, niche, name, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project_id, device_id, domain, niche, name, now),
        )
        conn.commit()
    return {
        "project_id": project_id,
        "device_id": device_id,
        "domain": domain,
        "niche": niche,
        "name": name,
        "created_at": now,
    }


def get_projects_by_device(device_id: str) -> List[Dict[str, Any]]:
    """Retrieve all projects for a specific device, including video count & latest video timestamp."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.*,
                   COUNT(v.video_id) AS video_count,
                   MAX(v.created_at) AS last_video_at
            FROM projects p
            LEFT JOIN videos v ON p.project_id = v.project_id
            WHERE p.device_id = ?
            GROUP BY p.project_id
            ORDER BY p.created_at DESC
            """,
            (device_id,),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    """Get project by project_id."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


# ── Video Operations ─────────────────────────────────────────────────────────

def create_video(
    video_id: str,
    project_id: str,
    title: str,
    duration: float = 0.0,
    status: str = "processing",
    file_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a video entry in processing status."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO videos (video_id, project_id, title, file_path, duration, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (video_id, project_id, title, file_path, duration, now, status),
        )
        conn.commit()
    return {
        "video_id": video_id,
        "project_id": project_id,
        "title": title,
        "file_path": file_path,
        "duration": duration,
        "created_at": now,
        "status": status,
    }


def update_video(
    video_id: str,
    status: str,
    file_path: Optional[str] = None,
    duration: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Update status, file_path, and duration of a video."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        updates = ["status = ?"]
        params: List[Any] = [status]

        if file_path is not None:
            updates.append("file_path = ?")
            params.append(file_path)
        if duration is not None:
            updates.append("duration = ?")
            params.append(duration)

        params.append(video_id)
        sql = f"UPDATE videos SET {', '.join(updates)} WHERE video_id = ?"
        cursor.execute(sql, params)
        conn.commit()

        cursor.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_videos_by_project(project_id: str) -> List[Dict[str, Any]]:
    """Get all videos for a given project."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def get_videos_by_device(device_id: str) -> List[Dict[str, Any]]:
    """Get all videos across all projects belonging to a device."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT v.*, p.name AS project_name, p.niche AS niche, p.domain AS domain
            FROM videos v
            JOIN projects p ON v.project_id = p.project_id
            WHERE p.device_id = ?
            ORDER BY v.created_at DESC
            """,
            (device_id,),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


# ── Custom Voice Operations ──────────────────────────────────────────────────

def create_custom_voice(
    voice_id: str,
    device_id: str,
    name: str,
    fish_voice_id: str,
    sample_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Store a custom cloned voice entry."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO custom_voices (id, device_id, name, fish_voice_id, sample_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (voice_id, device_id, name, fish_voice_id, sample_url, now),
        )
        conn.commit()
    return {
        "id": voice_id,
        "device_id": device_id,
        "name": name,
        "fish_voice_id": fish_voice_id,
        "sample_url": sample_url,
        "created_at": now,
    }


def get_custom_voices_by_device(device_id: str) -> List[Dict[str, Any]]:
    """Retrieve all custom cloned voices for a given device."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM custom_voices WHERE device_id = ? ORDER BY created_at DESC",
            (device_id,),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


# ── Custom Font Operations ───────────────────────────────────────────────────

def create_custom_font(
    font_id: str,
    device_id: str,
    font_name: str,
    file_path: str,
) -> Dict[str, Any]:
    """Store a custom font entry."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO custom_fonts (id, device_id, font_name, file_path, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (font_id, device_id, font_name, file_path, now),
        )
        conn.commit()
    return {
        "id": font_id,
        "device_id": device_id,
        "font_name": font_name,
        "file_path": file_path,
        "created_at": now,
    }


def get_custom_fonts_by_device(device_id: str) -> List[Dict[str, Any]]:
    """Retrieve all custom fonts for a given device."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM custom_fonts WHERE device_id = ? ORDER BY created_at DESC",
            (device_id,),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def get_custom_font_by_id(font_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a custom font entry by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM custom_fonts WHERE id = ?",
            (font_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


