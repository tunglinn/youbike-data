import database as db

live = {
    "empty": db.get_empty_stations(),
    "full":  db.get_full_stations(),
    "low":   db.get_low_stations(),
}
for k, v in live.items():
    print(k + ": " + str(len(v)) + " stations")
    for s in v:
        name_repr = ascii(s["name"])   # escapes non-ASCII, safe for cp1252
        print("  uid=" + s["station_uid"]
              + "  bikes=" + str(s["available_rent_bikes"])
              + "  docks=" + str(s["available_return_bikes"])
              + "  name_type=" + type(s["name"]).__name__
              + "  name=" + name_repr)

# Also confirm stations/latest shape
latest = db.get_all_latest()
print("\nstations/latest: " + str(len(latest)) + " stations")
first = latest[0]
print("keys: " + str(list(first.keys())))
print("name type: " + type(first["name"]).__name__)
