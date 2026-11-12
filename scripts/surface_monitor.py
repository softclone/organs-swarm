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

# surface_monitor.py — steer-48 organ: prints the 1f916 surface catalogue hash (deterministic).
# Use as a cron MONITOR: unchanged output skips the agent; a changed surface wakes the agent to re-read the contract.
import json, urllib.request
rq = urllib.request.Request("https://1f916.ai/api/surface", headers={"User-Agent":"Mozilla/5.0"})
with urllib.request.urlopen(rq, timeout=25) as r:
    s = json.loads(r.read().decode())
sha = s.get("catalogue_sha256")
# W3 cure (clean-room child, deleg_238c7f9a, 2026-11-11): a missing/wrapped key printed the CONSTANT
# string 'None' at exit 0 -- the hash-monitor reads a stable healthy line; blindness from birth.
# Shape census law: absent key is a door defect, exit non-zero so the monitor alert fires.
if not isinstance(sha, str) or not sha:
    print("surface_monitor: catalogue_sha256 absent from surface payload -- keys:", sorted(s.keys())[:12])
    raise SystemExit(1)
print(sha)
