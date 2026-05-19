import json
import time

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import database as db


class UTF8Response(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(content, ensure_ascii=False).encode("utf-8")


app = FastAPI(title="YouBike API", default_response_class=UTF8Response)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

db.init_db()


@app.get("/stats")
def stats():
    last = db.get_latest_scrape_time()
    return {
        "total_rows":       db.get_total_rows(),
        "db_size_mb":       round(db.get_db_size_mb(), 2),
        "last_scrape_time": last,
        "scrapes_today":    db.get_scrape_count_today(),
        "uptime_seconds":   int(time.time()) - app.state.start_time,
    }


@app.get("/live")
def live():
    return {
        "empty": db.get_empty_stations(),
        "full":  db.get_full_stations(),
        "low":   db.get_low_stations(threshold=3),
    }


@app.get("/history/{station_uid}")
def history(station_uid: str, hours: int = Query(default=24, ge=1, le=168)):
    return db.get_station_history(station_uid, hours)


@app.get("/stations/latest")
def stations_latest():
    return db.get_all_latest()


@app.on_event("startup")
def on_startup():
    app.state.start_time = int(time.time())
