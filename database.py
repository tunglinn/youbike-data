import sqlite3
import time
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "youbike.db")


def _conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS availability (
                station_uid TEXT,
                timestamp INTEGER,
                available_rent_bikes INTEGER,
                available_return_bikes INTEGER,
                capacity INTEGER,
                service_status INTEGER
            );

            CREATE TABLE IF NOT EXISTS station_meta (
                station_uid TEXT PRIMARY KEY,
                name TEXT,
                lat REAL,
                lng REAL,
                capacity INTEGER
            );

            CREATE TABLE IF NOT EXISTS scrape_log (
                timestamp INTEGER,
                stations_fetched INTEGER,
                success INTEGER,
                error_message TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_avail_uid_ts
                ON availability (station_uid, timestamp DESC);
        """)


def insert_batch(readings: list[dict], scrape_meta: dict | None = None):
    """Insert a list of availability dicts and an optional scrape_log row."""
    with _conn() as con:
        con.executemany(
            """INSERT INTO availability
               (station_uid, timestamp, available_rent_bikes,
                available_return_bikes, capacity, service_status)
               VALUES (:station_uid, :timestamp, :available_rent_bikes,
                       :available_return_bikes, :capacity, :service_status)""",
            readings,
        )
        if scrape_meta:
            con.execute(
                """INSERT INTO scrape_log
                   (timestamp, stations_fetched, success, error_message)
                   VALUES (:timestamp, :stations_fetched, :success, :error_message)""",
                scrape_meta,
            )


def get_total_rows() -> int:
    with _conn() as con:
        return con.execute("SELECT COUNT(*) FROM availability").fetchone()[0]


def get_db_size_mb() -> float:
    try:
        return os.path.getsize(DB_PATH) / (1024 * 1024)
    except FileNotFoundError:
        return 0.0


def get_latest_scrape_time() -> int | None:
    with _conn() as con:
        row = con.execute(
            "SELECT timestamp FROM scrape_log ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None


def get_scrape_count_today() -> int:
    midnight = int(time.time()) // 86400 * 86400
    with _conn() as con:
        return con.execute(
            "SELECT COUNT(*) FROM scrape_log WHERE timestamp >= ?", (midnight,)
        ).fetchone()[0]


def get_empty_stations() -> list[dict]:
    with _conn() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT a.station_uid, m.name,
                   a.available_rent_bikes, a.available_return_bikes, a.capacity
            FROM availability a
            JOIN station_meta m USING (station_uid)
            WHERE a.timestamp = (
                SELECT MAX(timestamp) FROM availability
                WHERE station_uid = a.station_uid
            )
            AND a.available_rent_bikes = 0
            ORDER BY m.name
        """).fetchall()
        return [dict(r) for r in rows]


def get_full_stations() -> list[dict]:
    with _conn() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT a.station_uid, m.name,
                   a.available_rent_bikes, a.available_return_bikes, a.capacity
            FROM availability a
            JOIN station_meta m USING (station_uid)
            WHERE a.timestamp = (
                SELECT MAX(timestamp) FROM availability
                WHERE station_uid = a.station_uid
            )
            AND a.available_return_bikes = 0
            ORDER BY m.name
        """).fetchall()
        return [dict(r) for r in rows]


def get_low_stations(threshold: int = 3) -> list[dict]:
    with _conn() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT a.station_uid, m.name,
                   a.available_rent_bikes, a.available_return_bikes, a.capacity
            FROM availability a
            JOIN station_meta m USING (station_uid)
            WHERE a.timestamp = (
                SELECT MAX(timestamp) FROM availability
                WHERE station_uid = a.station_uid
            )
            AND a.available_rent_bikes > 0
            AND a.available_rent_bikes <= ?
            ORDER BY a.available_rent_bikes, m.name
        """, (threshold,)).fetchall()
        return [dict(r) for r in rows]


def get_station_history(station_uid: str, hours: int = 24) -> list[dict]:
    cutoff = int(time.time()) - hours * 3600
    with _conn() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT timestamp, available_rent_bikes, available_return_bikes
            FROM availability
            WHERE station_uid = ? AND timestamp >= ?
            ORDER BY timestamp ASC
        """, (station_uid, cutoff)).fetchall()
        return [dict(r) for r in rows]


def get_all_latest() -> list[dict]:
    with _conn() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT a.station_uid, m.name, m.lat, m.lng,
                   a.available_rent_bikes, a.available_return_bikes, a.capacity
            FROM availability a
            JOIN station_meta m USING (station_uid)
            WHERE a.timestamp = (
                SELECT MAX(timestamp) FROM availability
                WHERE station_uid = a.station_uid
            )
            ORDER BY m.name
        """).fetchall()
        return [dict(r) for r in rows]
