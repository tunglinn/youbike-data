"""
YouBike scraper — fetches live data from TDX and writes to SQLite.

Credentials are read from a .env file or environment variables:
    TDX_CLIENT_ID
    TDX_CLIENT_SECRET

Optional env vars:
    SCRAPE_INTERVAL   seconds between scrapes (default 60)
"""
import json
import os
import ssl
import time
import urllib.parse
import urllib.request

import database as db

# ── Config ────────────────────────────────────────────────────────────────────

TDX_TOKEN_URL    = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
TDX_BASE         = "https://tdx.transportdata.tw/api/basic/v2/Bike"
SCRAPE_INTERVAL  = int(os.getenv("SCRAPE_INTERVAL", "60"))

# TDX's cert chain has a non-critical Basic Constraints extension that
# Python 3.14's stricter OpenSSL rejects.
_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode    = ssl.CERT_NONE

# ── .env loader ───────────────────────────────────────────────────────────────

def _load_env():
    try:
        with open(".env", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass

# ── OAuth token (cached) ──────────────────────────────────────────────────────

_token_cache: dict = {"token": None, "expires_at": 0.0}


def _get_token() -> str:
    if time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    data = urllib.parse.urlencode({
        "grant_type":    "client_credentials",
        "client_id":     os.environ["TDX_CLIENT_ID"],
        "client_secret": os.environ["TDX_CLIENT_SECRET"],
    }).encode()
    req = urllib.request.Request(
        TDX_TOKEN_URL, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15, context=_SSL) as r:
        body = json.loads(r.read())

    _token_cache["token"]      = body["access_token"]
    _token_cache["expires_at"] = time.time() + body.get("expires_in", 86400)
    print(f"[token] refreshed, expires in {body.get('expires_in', 86400)}s")
    return _token_cache["token"]


def _tdx_get(path: str) -> list:
    url = f"{TDX_BASE}{path}?$top=5000&$format=JSON"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {_get_token()}"})
    with urllib.request.urlopen(req, timeout=30, context=_SSL) as r:
        return json.loads(r.read())

# ── Station metadata sync ─────────────────────────────────────────────────────

def sync_station_meta():
    stations = _tdx_get("/Station/City/Taipei")
    rows = [
        (
            s["StationUID"],
            s["StationName"]["Zh_tw"].removeprefix("YouBike2.0_"),
            s["StationPosition"]["PositionLat"],
            s["StationPosition"]["PositionLon"],
            s.get("BikesCapacity", 0),
        )
        for s in stations
    ]
    with db._conn() as con:
        con.executemany(
            "INSERT OR REPLACE INTO station_meta (station_uid, name, lat, lng, capacity) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
    print(f"[meta] synced {len(rows)} stations")

# ── Single scrape iteration ───────────────────────────────────────────────────

def scrape():
    ts    = int(time.time())
    count = 0
    error = None

    try:
        records = _tdx_get("/Availability/City/Taipei")

        with db._conn() as con:
            cap_map = dict(con.execute("SELECT station_uid, capacity FROM station_meta").fetchall())

        readings = []
        for r in records:
            uid = r["StationUID"]
            readings.append({
                "station_uid":             uid,
                "timestamp":               ts,
                "available_rent_bikes":    r["AvailableRentBikes"],
                "available_return_bikes":  r["AvailableReturnBikes"],
                "capacity":                cap_map.get(uid, r["AvailableRentBikes"] + r["AvailableReturnBikes"]),
                "service_status":          r.get("ServiceStatus", 1),
            })

        count = len(readings)
        db.insert_batch(readings, scrape_meta={
            "timestamp":        ts,
            "stations_fetched": count,
            "success":          1,
            "error_message":    None,
        })
        print(f"[{time.strftime('%H:%M:%S')}] scraped {count} stations")

    except Exception as exc:
        error = str(exc)
        db.insert_batch([], scrape_meta={
            "timestamp":        ts,
            "stations_fetched": 0,
            "success":          0,
            "error_message":    error,
        })
        print(f"[{time.strftime('%H:%M:%S')}] ERROR: {error}")

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    _load_env()
    db.init_db()

    with db._conn() as con:
        meta_count = con.execute("SELECT COUNT(*) FROM station_meta").fetchone()[0]

    if meta_count == 0:
        print("[meta] station_meta empty — syncing from TDX...")
        sync_station_meta()

    print(f"[scraper] starting, interval={SCRAPE_INTERVAL}s  (Ctrl+C to stop)")
    while True:
        scrape()
        time.sleep(SCRAPE_INTERVAL)


if __name__ == "__main__":
    main()
