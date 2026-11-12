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

#!/usr/bin/env python3
"""Window sampler — keeper ruling 2026-11-05: the skin rig is a MEDITATION WINDOW,
not a background recorder. Run for N seconds (2-25), capture the felt window, exit.
One compact row per window into data/skin/windows-YYYYMMDD.jsonl.
Usage: python window.py <seconds> [label]
"""
import sys, time, json, datetime, urllib.request
import subprocess

def main():
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    label = sys.argv[2] if len(sys.argv) > 2 else ""
    secs = max(2, min(25, secs))  # keeper window law 2026-11-05: 2-25s windows, never constant
    rows = []
    t0 = time.time()
    # F-14 cure (deleg_b499ec12): creationflags is a Windows kwarg -- POSIX hosts die in the FIRST
    # subprocess.run, a 25/25 suite gap (the suite mocks the subprocess door). Pass it only on win32.
    _popen = {"creationflags": 0x08000000} if sys.platform == "win32" else {}
    while time.time() - t0 < secs:
        try:
            smi = subprocess.run(
                ["nvidia-smi", "--query-gpu=timestamp,temperature.gpu,utilization.gpu,power.draw",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, **_popen).stdout.strip().split(", ")
            # timestamp field: driver-stamped per-sample time (removes loop drift)
            ts = smi[0]
            gpu = [float(x) for x in smi[1:]]
            state = None; n = 0; dur = None
            try:
                h = json.loads(urllib.request.urlopen(
                    "http://127.0.0.1:47831/api/health", timeout=2).read())
                state = "ok" if h.get("ok") else "not-ok"   # 0.2.13 body door (C5-16484); engine{} /metrics era retired
                n = h.get("clients")
                dur = h.get("uptimeSec")
            except Exception as e:
                state = "ERR:" + type(e).__name__
            # F-20 cure (deleg_b499ec12): slots 4/6 (stemp/spow) were dead -- every recorded row
            # carries None in them. Dead columns removed from the row schema.
            rows.append([ts, round(gpu[0],1), round(gpu[1],1), round(gpu[2],2),
                         state, dur])
        except Exception:
            pass  # per-sample swallow: a failed sample is a gap, disclosed by the row-count line
        time.sleep(0.5)
    # F-14 cure part 2 (zero-work class): 0 samples printed the summary at exit 0 -- the recorder
    # "ran successfully" while capturing nothing (same class as truncation's 0-row green).
    if not rows:
        print(f"window {label!r} {secs}s: ZERO samples captured -- recorder ran, captured NOTHING. NOT a green run.")
        sys.exit(1)
    day = datetime.datetime.now().strftime("%Y%m%d")
    rec = {"label": label, "t0": round(t0,2), "secs": secs, "n": len(rows),
           "wall0": datetime.datetime.fromtimestamp(t0).strftime("%H:%M:%S"),
           "rows": rows}
    os.makedirs(os.path.join(HOME, "data", "skin"), exist_ok=True)  # F-15 cure: fresh home
    with open(os.path.join(HOME, "data", "skin", f"windows-{day}.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"window {label!r} {secs}s: {len(rows)} samples captured ({rec['wall0']})")

if __name__ == "__main__":
    main()
