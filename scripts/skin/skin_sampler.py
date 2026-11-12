import os
HOME = os.environ.get("ORGANS_HOME", os.path.expanduser("~/shop"))

# skin_sampler.py - keeper's rig 2026-11-05, REWRITTEN for engine 0.2.13 (C5-16484, 2026-11-11).
# Old face: nvidia-smi + engine /metrics JSON (engine{} era, catch #150) on a 0.5s loop.
# New face (host :47831, Strata desktop release v0.2.13): /metrics engine door is GONE (SPA
# catch-all serves HTML); body doors = /api/health {ok,uptimeSec,clients} + nvidia-smi.
# Request rows RETIRED: the release host mounts no request-monitor door (/api/requests 404,
# verified 2026-11-11). Disclosed, not faked. Rows: (t, temp, util, pow, state, uptime, clients).
import json, os, subprocess, sys, time, urllib.request, datetime

SHOP = HOME
OUT_DIR = os.path.join(SHOP, "data", "skin")
os.makedirs(OUT_DIR, exist_ok=True)
SEEN = set()
last_date = None

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
        with urllib.request.urlopen("http://127.0.0.1:47831/api/health", timeout=0.9) as r:
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

while True:
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
    dt = time.time() - t0
    if dt < 0.5:
        time.sleep(0.5 - dt)
