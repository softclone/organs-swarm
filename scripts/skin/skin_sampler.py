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

# skin_sampler.py - keeper's rig 2026-11-05, REWRITTEN for engine 0.2.13 (C5-16484, 2026-11-11).
# Old face: nvidia-smi + engine /metrics JSON (engine{} era, catch #150) on a 0.5s loop.
# New face (host seat (ORGANS_SEAT_URL), Strata desktop release v0.2.13): /metrics engine door is GONE (SPA
# catch-all serves HTML); body doors = /api/health {ok,uptimeSec,clients} + nvidia-smi.
# Request rows RETIRED: the release host mounts no request-monitor door (/api/requests 404,
# verified 2026-11-11). Disclosed, not faked. Rows: (t, temp, util, pow, state, uptime, clients).
import json, os, subprocess, sys, time, urllib.request, datetime
import json
def _seat_url():
    if os.environ.get("ORGANS_SEAT_URL"): return os.environ["ORGANS_SEAT_URL"]
    for _q in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"), os.path.expanduser("~/organs.json")):
        try:
            v = json.load(open(_q, encoding="utf-8")).get("seat_url")
            if v: return v
        except Exception: pass
    return "http://127.0.0.1:8080"  # portable default: no baked estate port (wave-4 F-12)
_SEAT = _seat_url().rstrip('/')

SHOP = HOME
OUT_DIR = os.path.join(SHOP, "data", "skin")
os.makedirs(OUT_DIR, exist_ok=True)
SEEN = set()
last_date = None
# F-19 cure (deleg_b499ec12): the sampler ran while True with no exit -- an unbounded recorder with
# no stop is a liability in a shared repo (disk fills, no way to bound a run). Bounded by argv
# seconds (default 3600 = one hour); the window law (2-25s observation) rides as before.
RUN_SECS = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
_t_end = time.time() + RUN_SECS

def out_path():
    global last_date, OUT
    d = datetime.date.today().strftime("%Y%m%d")
    if d != last_date:
        last_date = d
        OUT = os.path.join(OUT_DIR, "skin-%s.jsonl" % d)
    return OUT

def metrics():
    # single named door; failures named (silent-None + dead-8080 class, audit C5-16484 B2/W1)
    try:
        with urllib.request.urlopen(_SEAT + "/api/health", timeout=0.9) as r:
            return json.load(r)
    except Exception as e:
        print("METRICS-ERR:", type(e).__name__, flush=True)
        return None

def gpu():
    try:
        q = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,power.draw",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=2)
        t, u, p = [x.strip() for x in q.stdout.strip().split(",")]
        return float(t), float(u), float(p)
    except Exception:
        return None, None, None

_real_rows = 0  # wave-5 W07: rows carrying real metrics (LAWS #23)
while time.time() < _t_end:
    t0 = time.time()
    rec = {"t": round(t0, 2)}
    m = metrics()
    g = gpu()
    if g[0] is not None:
        rec["temp"], rec["util"], rec["pow"] = g
    if m:
        rec["state"] = "ok" if m.get("ok") else "not-ok"
        rec["uptime"] = m.get("uptimeSec")
        rec["clients"] = m.get("clients")
    with open(out_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    if any(v is not None for k, v in rec.items() if k != "t"):  # wave-5 W07 (LAWS #23): timestamp-only rows and all-None-read rows capture nothing
        _real_rows += 1
    dt = time.time() - t0
    if dt < 0.5:
        time.sleep(0.5 - dt)

# wave-5 W07: zero captured is not a green run (LAWS #23 -- window.py's refusal, now its siblings too)
if _real_rows == 0:
    print("ZERO-content samples: recorder captured nothing but timestamps -- exit 1")
    sys.exit(1)
