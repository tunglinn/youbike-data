"""Run once to inspect TDX response shapes. Reads credentials from .env."""
import json, os, ssl, urllib.parse, urllib.request

# TDX's cert chain has a non-critical Basic Constraints extension that
# Python 3.14's stricter OpenSSL rejects. Disable verification for this
# known government endpoint.
_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE

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

_load_env()

TOKEN_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
BASE      = "https://tdx.transportdata.tw/api/basic/v2/Bike"

data = urllib.parse.urlencode({
    "grant_type":    "client_credentials",
    "client_id":     os.environ["TDX_CLIENT_ID"],
    "client_secret": os.environ["TDX_CLIENT_SECRET"],
}).encode()
req = urllib.request.Request(TOKEN_URL, data=data,
                              headers={"Content-Type": "application/x-www-form-urlencoded"})
with urllib.request.urlopen(req, timeout=15, context=_SSL) as r:
    token = json.loads(r.read())["access_token"]

def tdx_get(path):
    req = urllib.request.Request(
        BASE + path + "?$top=2&$format=JSON",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=15, context=_SSL) as r:
        return json.loads(r.read())

print("=== /Availability/City/Taipei (1 record) ===")
avail = tdx_get("/Availability/City/Taipei")
print(json.dumps(avail[0], ensure_ascii=False, indent=2))

print("\n=== /Station/City/Taipei (1 record) ===")
station = tdx_get("/Station/City/Taipei")
print(json.dumps(station[0], ensure_ascii=False, indent=2))
