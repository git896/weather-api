# ============================================================
#  Weather Station REST API
#  FastAPI + SQLite
#  Swagger UI: http://localhost:8000/docs
#  ReDoc:      http://localhost:8000/redoc
# ============================================================

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import os
from datetime import datetime

# ── Config ───────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "weather.db")

app = FastAPI(
    title="Weather Station API",
    description="""
## 🌤️ Weather Station REST API

Serves temperature and humidity data collected by a **Raspberry Pi Pico W**
with an **SHTC3** sensor, stored in a local SQLite database.

### Data Sources
- **Indoor**: Pico W → SHTC3 sensor → this API
- **Location**: Naperville, IL

### Features
- Get latest sensor reading
- Get reading history with configurable limit
- Post new readings from the Pico W
- Delete old readings
""",
    version="1.0.0",
    contact={
        "name": "Weather Station",
        "email": "saikatde55@gmail.com",
    },
)

# ── CORS (allows Flutter web app to call this API) ────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Database setup ────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            temp_c    REAL    NOT NULL,
            temp_f    REAL    NOT NULL,
            humidity  REAL    NOT NULL,
            created   TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ── Pydantic models ───────────────────────────────────────────
class ReadingIn(BaseModel):
    temp_c: float
    humidity: float

    class Config:
        json_schema_extra = {
            "example": {
                "temp_c": 22.5,
                "humidity": 58.3
            }
        }

class ReadingOut(BaseModel):
    id: int
    temp_c: float
    temp_f: float
    humidity: float
    created: str

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "temp_c": 22.5,
                "temp_f": 72.5,
                "humidity": 58.3,
                "created": "2026-06-29 12:00:00"
            }
        }

class ReadingListOut(BaseModel):
    count: int
    readings: List[ReadingOut]

class StatusOut(BaseModel):
    status: str
    total_readings: int
    latest_reading: Optional[ReadingOut]
    db_path: str

# ── Routes ────────────────────────────────────────────────────

@app.get(
    "/",
    tags=["Health"],
    summary="API health check",
    response_description="API status and basic info"
)
def root():
    """Check if the API is running and get basic info."""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    conn.close()
    return {
        "status": "online",
        "api": "Weather Station API",
        "version": "1.0.0",
        "docs": "/docs",
        "total_readings": count
    }


@app.get(
    "/api/status",
    response_model=StatusOut,
    tags=["Health"],
    summary="Detailed API and database status",
)
def get_status():
    """Get detailed status including latest reading and total count."""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    row = conn.execute(
        "SELECT * FROM readings ORDER BY created DESC LIMIT 1"
    ).fetchone()
    conn.close()

    latest = None
    if row:
        latest = ReadingOut(
            id=row["id"], temp_c=row["temp_c"], temp_f=row["temp_f"],
            humidity=row["humidity"], created=row["created"]
        )
    return StatusOut(
        status="online",
        total_readings=count,
        latest_reading=latest,
        db_path=DB_PATH
    )


@app.get(
    "/api/readings",
    response_model=ReadingListOut,
    tags=["Readings"],
    summary="Get reading history",
    response_description="List of sensor readings ordered by newest first"
)
def get_readings(
    limit: int = Query(default=6, ge=1, le=500, description="Number of readings to return (1-500)")
):
    """
    Get the most recent sensor readings.

    - **limit**: How many readings to return (default 6, max 500)
    """
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM readings ORDER BY created DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    readings = [
        ReadingOut(
            id=r["id"], temp_c=r["temp_c"], temp_f=r["temp_f"],
            humidity=r["humidity"], created=r["created"]
        ) for r in rows
    ]
    return ReadingListOut(count=len(readings), readings=readings)


@app.get(
    "/api/readings/latest",
    response_model=ReadingOut,
    tags=["Readings"],
    summary="Get the most recent reading",
    response_description="Single most recent sensor reading"
)
def get_latest():
    """Get the single most recent temperature and humidity reading from the Pico W."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM readings ORDER BY created DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="No readings found yet")
    return ReadingOut(
        id=row["id"], temp_c=row["temp_c"], temp_f=row["temp_f"],
        humidity=row["humidity"], created=row["created"]
    )


@app.get(
    "/api/readings/{reading_id}",
    response_model=ReadingOut,
    tags=["Readings"],
    summary="Get a specific reading by ID",
)
def get_reading(reading_id: int):
    """Get a single reading by its database ID."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM readings WHERE id = ?", (reading_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Reading {reading_id} not found")
    return ReadingOut(
        id=row["id"], temp_c=row["temp_c"], temp_f=row["temp_f"],
        humidity=row["humidity"], created=row["created"]
    )


@app.post(
    "/api/readings",
    response_model=ReadingOut,
    status_code=201,
    tags=["Readings"],
    summary="Post a new sensor reading",
    response_description="The newly created reading"
)
def create_reading(reading: ReadingIn):
    """
    Post a new temperature and humidity reading.

    Called by the **Raspberry Pi Pico W** every 5 minutes automatically.

    - **temp_c**: Temperature in Celsius
    - **humidity**: Relative humidity percentage (0-100)
    """
    temp_f = round(reading.temp_c * 9 / 5 + 32, 2)
    created = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO readings (temp_c, temp_f, humidity, created) VALUES (?, ?, ?, ?)",
        (reading.temp_c, temp_f, reading.humidity, created)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return ReadingOut(
        id=new_id, temp_c=reading.temp_c, temp_f=temp_f,
        humidity=reading.humidity, created=created
    )


@app.delete(
    "/api/readings/{reading_id}",
    tags=["Readings"],
    summary="Delete a specific reading",
)
def delete_reading(reading_id: int):
    """Delete a single reading by its ID."""
    conn = get_db()
    row = conn.execute("SELECT id FROM readings WHERE id = ?", (reading_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Reading {reading_id} not found")
    conn.execute("DELETE FROM readings WHERE id = ?", (reading_id,))
    conn.commit()
    conn.close()
    return {"deleted": reading_id}


@app.delete(
    "/api/readings",
    tags=["Readings"],
    summary="Delete old readings",
)
def delete_old_readings(
    keep: int = Query(default=100, ge=1, description="Number of most recent readings to keep")
):
    """
    Delete old readings, keeping only the most recent N records.
    Useful for managing database size over time.
    """
    conn = get_db()
    conn.execute("""
        DELETE FROM readings WHERE id NOT IN (
            SELECT id FROM readings ORDER BY created DESC LIMIT ?
        )
    """, (keep,))
    deleted = conn.total_changes
    conn.commit()
    conn.close()
    return {"deleted_count": deleted, "kept": keep}
