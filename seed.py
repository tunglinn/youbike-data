"""Run once to populate youbike.db with realistic dummy data."""
import math
import random
import time

from database import init_db, insert_batch, _conn

STATIONS = [
    ("500101001", "捷運市政府站(3號出口)",    25.0408, 121.5647, 22),
    ("500101002", "捷運國父紀念館站(2號出口)", 25.0401, 121.5573, 14),
    ("500101003", "忠孝敦化站",               25.0416, 121.5504, 12),
    ("500101004", "忠孝復興站",               25.0417, 121.5439, 14),
    ("500101005", "大安公園站",               25.0336, 121.5348, 16),
    ("500101006", "台北101/世貿站",           25.0338, 121.5645, 16),
    ("500101007", "信義安和站",               25.0335, 121.5541, 16),
    ("500101008", "科技大樓站",               25.0264, 121.5436, 16),
    ("500101009", "六張犁站",                 25.0227, 121.5511, 14),
    ("500101010", "麟光站",                   25.0215, 121.5593, 12),
    ("500101011", "台電大樓站",               25.0276, 121.5335, 14),
    ("500101012", "公館站",                   25.0144, 121.5339, 14),
    ("500101013", "萬隆站",                   25.0077, 121.5365, 12),
    ("500101014", "景美站",                   24.9990, 121.5428, 12),
    ("500101015", "中山國中站",               25.0570, 121.5453, 12),
    ("500101016", "松山機場站",               25.0630, 121.5520, 18),
    ("500101017", "南京復興站",               25.0527, 121.5436, 16),
    ("500101018", "行天宮站",                 25.0627, 121.5336, 12),
    ("500101019", "中山站",                   25.0523, 121.5225, 14),
    ("500101020", "市民廣場",                 25.0447, 121.5219, 18),
    ("500101031", "仁愛光復路口",             25.0380, 121.5520, 10),
    ("500101032", "大安森林公園",             25.0291, 121.5310, 16),
]

NOW = int(time.time())
READINGS_PER_DAY = 144   # every 10 minutes
SCRAPES_PER_DAY  = 288   # every 5 minutes

# Guaranteed states at the latest timestamp so /live always has results
FORCED_LAST = {
    "500101001": 0,   # empty
    "500101002": 0,   # empty
    "500101020": 18,  # full  (capacity 18 → 0 docks)
    "500101031": 2,   # low
    "500101032": 1,   # low
}


def _bike_count(i: int, capacity: int, phase_offset: float) -> int:
    mid   = capacity / 2
    amp   = capacity * 0.45
    wave  = amp * math.sin(i / READINGS_PER_DAY * math.pi * 4 + phase_offset)
    noise = random.uniform(-1, 1)
    return max(0, min(capacity, round(mid + wave + noise)))


def main():
    init_db()

    # ── station_meta ──────────────────────────────────────────────────────────
    with _conn() as con:
        con.executemany(
            "INSERT OR REPLACE INTO station_meta (station_uid, name, lat, lng, capacity) "
            "VALUES (?, ?, ?, ?, ?)",
            STATIONS,
        )
    print(f"Inserted {len(STATIONS)} station_meta rows")

    # ── availability (24h, every 10 min, all stations) ────────────────────────
    readings = []
    for uid, _, _, _, cap in STATIONS:
        phase = random.uniform(0, math.pi)
        for i in range(READINGS_PER_DAY):
            ts = NOW - (READINGS_PER_DAY - 1 - i) * 600
            if i == READINGS_PER_DAY - 1 and uid in FORCED_LAST:
                bikes = FORCED_LAST[uid]
            else:
                bikes = _bike_count(i, cap, phase)
            readings.append({
                "station_uid":           uid,
                "timestamp":             ts,
                "available_rent_bikes":  bikes,
                "available_return_bikes": cap - bikes,
                "capacity":              cap,
                "service_status":        1,
            })

    # ── scrape_log (24h, every 5 min) ─────────────────────────────────────────
    scrape_rows = []
    for j in range(SCRAPES_PER_DAY):
        scrape_rows.append({
            "timestamp":        NOW - (SCRAPES_PER_DAY - 1 - j) * 300,
            "stations_fetched": len(STATIONS),
            "success":          1,
            "error_message":    None,
        })

    # Insert availability in chunks with scrape_log attached to first chunk
    chunk = readings[:len(STATIONS)]
    insert_batch(chunk, scrape_meta=scrape_rows[0])
    for k in range(1, SCRAPES_PER_DAY):
        start = k * len(STATIONS)
        end   = start + len(STATIONS)
        meta  = scrape_rows[k] if k < len(scrape_rows) else None
        insert_batch(readings[start:end], scrape_meta=meta)

    with _conn() as con:
        avail_count  = con.execute("SELECT COUNT(*) FROM availability").fetchone()[0]
        scrape_count = con.execute("SELECT COUNT(*) FROM scrape_log").fetchone()[0]
        meta_count   = con.execute("SELECT COUNT(*) FROM station_meta").fetchone()[0]

    print(f"availability rows : {avail_count:,}")
    print(f"scrape_log rows   : {scrape_count:,}")
    print(f"station_meta rows : {meta_count:,}")


if __name__ == "__main__":
    main()
