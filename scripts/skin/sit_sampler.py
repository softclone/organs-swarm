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

#!/usr/bin/env python
# sit_sampler.py - sustained combined-source body sit (keeper steer 2026-11-05)
# usage: python sit_sampler.py <seconds> <label>
# sources: nvidia-smi + strata /metrics + llama-server process memory
# writes JSONL rows (flush each row); observation rig, no scoring.
import sys, time, json, subprocess, urllib.request, datetime, os

secs = int(sys.argv[1]) if len(sys.argv) > 1 else 900
label = sys.argv[2] if len(sys.argv) > 2 else "sit"
outdir = os.path.join(HOME, "data", "skin")
os.makedirs(outdir, exist_ok=True)  # F-15 cure (deleg_b499ec12): fresh-home first-write class
out = os.path.join(outdir, f"sit-{label}.jsonl")

# F-22 cure (deleg_b499ec12): KEYS was dead code (referenced only in the header prose, never in
# logic) and documented retired 0.1.x /metrics keys -- removed; header carries the current grammar.

def nvidia():
    # F-22 cure (deleg_b499ec12): nvidia() was the ONLY unguarded call site in the rig -- an
    # OSError/missing-binary killed the whole sampler mid-run. Fail named, row carries N/A.
    try:
        return _nvidia_raw()
    except Exception as e:
        return {"N/A": type(e).__name__}

def _nvidia_raw():
    r = subprocess.run(["nvidia-smi","--query-gpu=timestamp,temperature.gpu,"
        "utilization.gpu,power.draw,clocks.sm","--format=csv,noheader,nounits"],
        capture_output=True, text=True).stdout.strip().split(",")
    r = [x.strip() for x in r]
    return {"ts": r[0], "tC": float(r[1]), "util": float(r[2]),
            "watt": float(r[3]), "sm_clk": r[4]}

def metrics():
    # 0.2.13 body door: /api/health JSON (engine{} /metrics era retired, C5-16484)
    try:
        h = json.loads(urllib.request.urlopen("http://127.0.0.1:47831/api/health", timeout=3).read().decode())
        eng = (h.get("engine") or {})
        return ["ok=%s" % h.get("ok"), "uptime=%s" % h.get("uptimeSec"),
                "clients=%s" % h.get("clients"), "engine_slot=%s" % eng.get("status")]
    except Exception as e:
        return ["ERR:" + str(e)[:60]]

def proc():
    try:
        r = subprocess.run(["tasklist","/FI","IMAGENAME eq llama-server.exe","/FO","CSV","/NH"],
            capture_output=True, text=True).stdout
        rows = [ln.split(",") for ln in r.splitlines() if "llama" in ln.lower()]
        return [[c.strip('"') for c in (row[0], row[3] if len(row)>3 else "?")] for row in rows]
    except Exception as e:
        return [["ERR", str(e)[:40]]]

with open(out, "a", encoding="utf-8") as f:
    t_end = time.time() + secs
    n = 0
    while time.time() < t_end:
        row = {"wall": datetime.datetime.now().strftime("%H:%M:%S"),
               "nv": nvidia(), "metrics": metrics(), "proc": proc()}
        f.write(json.dumps(row) + "\n"); f.flush(); n += 1
        time.sleep(2)
    print(f"SIT COMPLETE {label}: {n} rows -> {out}")
