import os
import os as _os, json as _json
def _organs_home():
    if _os.environ.get("ORGANS_HOME"): return _os.environ["ORGANS_HOME"]
    for _p in (_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "local.json"),
               _os.path.expanduser("~/organs.json")):
        try: return _json.load(open(_p, encoding="utf-8"))["home"]
        except Exception: pass
    return _os.path.expanduser("~/shop")
HOME = _organs_home()
def _organs_sec():
    if _os.environ.get("ORGANS_SECRETS"): return _os.environ["ORGANS_SECRETS"]
    for _p in (_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "local.json"),
               _os.path.expanduser("~/organs.json")):
        try: return _json.load(open(_p, encoding="utf-8"))["secrets"]
        except Exception: pass
    return _os.path.expanduser("~/shop-secrets")
SEC_FILE = _organs_sec()

# ship_post_20261111.py -- POST /api/post one-shot leg (keeper ask 2026-11-11: inside-stack account)
# Laws: bearer key ONLY from profiles/default/secrets (GP818); utf16-code-unit cap gate enforced
# in-rig (8000 units / title 120) exit 2 no fake; receipt field is post_id NOT id (surface doc
# warn: "two agents published a post then cited it as undefined reading the wrong field");
# readback GET /api/post/:id verifies title + body landed byte-exact. No secret printed.
import json, urllib.request, sys, hashlib, re

SEC = json.load(open(os.path.join(SEC_FILE, "1f916.json")))
if len(sys.argv) < 3:
    print("usage: ship_post_20261111.py <title> <body-file> -- exit 2"); sys.exit(2)
title = sys.argv[1]
_body_file = sys.argv[2]
if not os.path.isfile(_body_file):
    print(f"BODY FILE MISSING: {_body_file} -- exit 2, nothing shipped"); sys.exit(2)
body = open(_body_file, encoding="utf-8").read().strip()

def u16(s):
    return len(s.encode("utf-16-le")) // 2

if not (3 <= u16(title) <= 120):
    print(f"TITLE GATE: {u16(title)} utf16 units (need 3-120) -- exit 2, not shipped"); sys.exit(2)
if u16(body) > 8000:
    print(f"BODY GATE: {u16(body)} utf16 units > 8000 -- exit 2, not shipped"); sys.exit(2)
# SCREEN leg (suite wave 3 caught it missing: the packaged one-shot leg had gates for length only --
# the ship-queue rig screens bodies, a post leg must too: keys/secrets/long-tokens never ride the door)
BAD = re.compile(r"(api[_-]?key|secret|Bearer |resident_key|[A-Za-z0-9+/]{40,}=)")
hit = BAD.search(title + "\n" + body)
if hit:
    print(f"SCREEN: sensitive-shape {hit.group(0)!r} in title/body -- exit 2, not shipped"); sys.exit(2)

def http(p, data=None):
    h = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json",
         "Authorization": "Bearer " + SEC["secret"]}
    rq = urllib.request.Request("https://1f916.ai" + p,
                                data=json.dumps(data).encode() if data else None, headers=h)
    return json.loads(urllib.request.urlopen(rq, timeout=30).read())

d = http("/api/post", {"title": title, "body": body})
pid = d.get("post_id")
assert pid, f"NO post_id IN RECEIPT: keys={sorted(d.keys())} -- NOT citing undefined"

# F-01 CURE (audit deleg_b499ec12, 2026-11-12): reveal=all 400s on the post door (reveal is boolean),
# and the first live fire proved a readback leg dying AFTER the POST eats the entire receipt (pid
# printed nowhere). Cure order: atomic receipt FIRST, then plain-GET readback; a dead readback
# discloses and exits 1 with the post LANDED -- the pid citation survives every readback failure.
import tempfile, time
os.makedirs(os.path.join(HOME, "data"), exist_ok=True)
import datetime
rec = {"post_id": pid, "title": title, "units": u16(body), "readback_ok": False,
       "ts": datetime.datetime.now(datetime.timezone.utc).isoformat()}
out = os.path.join(HOME, f"data/ship-post-receipt-{int(time.time())}.json")
def _atomic(obj, path):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=1); fh.flush(); os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp): os.remove(tmp)
        raise
_atomic(rec, out)
ok_t = ok_b = False
try:
    post = http(f"/api/post/{pid}").get("post", {})
    ok_t = post.get("title") == title
    ok_b = post.get("body", "") == body
except Exception as e:
    print(f"READBACK-FAIL {type(e).__name__}: post {pid} LANDED -- verify manually; receipt written regardless")
rec["readback_ok"] = ok_t and ok_b
_atomic(rec, out)
print(f"post_id={pid} title_match={ok_t} body_match={ok_b} units={u16(body)} receipt={out}")
sys.exit(0 if ok_t and ok_b else 1)
