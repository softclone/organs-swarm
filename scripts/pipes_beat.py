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

# pipes_beat.py — H18 nightly pipe sweep: "the pipe map is true only fresh"
# LIMITS (H19 census 2026-11-07): expected-shape table is a FROZEN MAP — dies at the first estate change (new seat, retired proxy, port move); cure = re-print expectations after any estate edit (H18 law: the map is true only fresh);
# pipe list is 8 hardcoded entries — extra pipes are invisible to the sweep;
# TCP-open proves a listener, not a service (18082 is tcp-checked by design: HTTP shape unpriced);
# kid/venue probes traverse the tailnet — timeouts 15s, DEAD-name printed, no retry (a DEAD row is the datum).
# silent-failure probe fired 2026-11-07: 8/8 hand-flight; divergence path NOT yet exercised (first divergence will be the probe) — named bound.
# Probes the estate pipes (9 today), prints shape per pipe, flags divergences from expected.
# Expected shapes registered at H18 (2026-11-07): 8080 200, 8082 200, 8081 200,
# 8000 404(endpoint-answering), 1234 200, 18080 200, 18082 TCP-open, 7340 401.
import socket, urllib.request, urllib.error, subprocess

def http(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}"
    except Exception as e:
        return f"DEAD {type(e).__name__}"

def tcp(host, port, timeout=5):
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return "TCP-OPEN"
    except Exception as e:
        return f"DEAD {type(e).__name__}"

import json as _json
def _seat_url():
    if os.environ.get("ORGANS_SEAT_URL"): return os.environ["ORGANS_SEAT_URL"]
    for _q in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"), os.path.expanduser("~/organs.json")):
        try:
            v = _json.load(open(_q, encoding="utf-8")).get("seat_url")
            if v: return v
        except Exception: pass
    return "http://127.0.0.1:8080"
_SEAT = _seat_url().rstrip("/")
def _pipes_extra():
    # estate-specific probes (tailnet peers) ride config "pipes_extra": [[name, url, expected], ...] -- never in the repo (wave-4 F-12)
    for _q in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"), os.path.expanduser("~/organs.json")):
        try:
            v = _json.load(open(_q, encoding="utf-8")).get("pipes_extra")
            if v: return [(n, (lambda u=u: http(u, timeout=15)), e) for n, u, e in v]
        except Exception: pass
    return []
PIPES = [
    ("seat (config seat_url)", lambda: http(_SEAT + "/v1/models", timeout=15),                      "HTTP 200"),
    ("seat body /api/health", lambda: http(_SEAT + "/api/health", timeout=15),                      "HTTP 200"),
    ("twin-proxy :8082",      lambda: http("http://127.0.0.1:8082/v1/models"),                     "HTTP 200"),
    ("embed :8081",           lambda: http("http://127.0.0.1:8081/v1/models"),                     "HTTP 200"),
    ("honcho :8000",          lambda: http("http://localhost:8000/"),                              "HTTP 404"),
    ("lmstudio :1234",        lambda: http("http://127.0.0.1:1234/v1/models"),                     "HTTP 200"),
    ("fwd :18080",            lambda: http("http://127.0.0.1:18080/v1/models", timeout=15),       "HTTP 200"),
    ("fwd :18082 (tcp)",      lambda: tcp("127.0.0.1", 18082),                                    "TCP-OPEN"),

] + _pipes_extra()

# audit cure (deleg_eb3541f7, 2026-11-11): 'date -u' is not a Windows exe -- the sweep survived only
# via git's bundled usr/bin on PATH; a PATH change = FileNotFoundError, sweep dies before any probe.
from datetime import datetime, timezone
print("H18 PIPE SWEEP", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
# MONITOR PROPORTIONALITY law: disclosed wounds with NO shop-side action print a NAMED
# advisory line and are EXCLUDED from the exit trigger (spend no alert); unknown failures
# on legs we use keep the teeth. lmstudio :1234 = the keeper's server, not our chain
# (keeper ruling 2026-11-11: not the seat backend; embed door is :8081). Disclosed 2026-11-11.
ADVISORY_NAMES = {"lmstudio :1234"}
div = 0
adv = 0
rows = []
for name, probe, expected in PIPES:
    got = probe()
    ok = (got == expected)
    if not ok and name in ADVISORY_NAMES:
        adv += 1
        print(f"{name:22s} got={got:28s} expected={expected:10s} ADVISORY-Disclosed (keeper's server, no shop action)")
        continue
    if not ok:
        div += 1
    # quiet law cure: per-pipe table printed only on DIVERGENCE rows (clean fire = silence)
    if not ok:
        print(f"{name:22s} got={got:28s} expected={expected:10s} DIVERGENCE")
# exit discipline cure: divergences computed+printed at exit 0 = alarm disconnected (catch #202)
if adv:
    print(f"advisory: {adv} disclosed wound(s) above, cadence kept")
if div:
    print(f"SWEEP: {len(PIPES) - div - adv}/{len(PIPES) - adv} true, {div} divergences")
    raise SystemExit(1)