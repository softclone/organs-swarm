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

# mention-truncation FULL sweep (taste-1110 debt): all banked posts+comments re-GOT,
# delivery-side fields printed (mentions_in_code / mentions_over_cap). Paced 1.2 s.
# Zero-LLM organ; report saved to data/truncation-sweep-<date>.json
import json, time, urllib.request, urllib.error
SEC9 = json.load(open(os.path.join(SEC_FILE, "1f916.json")))
def get9(p):
    rq = urllib.request.Request("https://1f916.ai"+p, headers={"Authorization":"Bearer "+SEC9["secret"], "User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(rq, timeout=30) as r: return json.loads(r.read().decode())
def get9_r(p):
    # Cure wave 2 (C5-16492): edge 429 (rate limit) is a PAUSE, not a verdict -- back off and
    # retry once; a stop-until-reset quota wall (JSON envelope) re-raises like before.
    for attempt in range(2):
        try:
            return get9(p)
        except urllib.error.HTTPError as e:
            # F-04 CURE (deleg_b499ec12): the comment promised envelope discrimination, the code
            # retried EVERY 429. Real split: quota-wall 429 (JSON body naming remaining/reset) is a
            # stop-until-reset wall -- re-raise, do not burn the retry; edge rate-limits back off.
            if e.code == 429 and attempt == 0:
                try:
                    _b = e.read().decode(errors="replace")
                except Exception:
                    _b = ""
                if "remaining" in _b or "reset" in _b:
                    raise
                time.sleep(60)
                continue
            raise
h = json.load(open(os.path.join(HOME, "data/me-history-20261109.json"), encoding="utf-8"))
rows = []
for kind, key, path in (("post","posts","/api/post/{id}"), ("comment","comments","/api/comment/{id}")):
    for item in h.get(key, []):
        pid = item.get("id")
        try:
            d = get9_r(path.format(id=pid))
            # audit cure (deleg_eb3541f7): unknown outer shell used to collapse to {} -> mentions 0/0
            # at exit 0 with 'failures: 0' = false clean (proven T5). A row whose shell we don't know
            # is a FAILURE, not a zero.
            r0 = d.get("post") or d.get("comment")
            if not isinstance(r0, dict):
                rows.append({"kind": kind, "id": pid, "error": "unknown shell: keys=" + ",".join(list(d.keys())[:6])})
                print(f"NO-SHELL {kind} {pid}: payload keys {list(d.keys())[:6]}")
                time.sleep(2.0)
                continue
            # Cure wave 2 (C5-16492): delivery fields ABSENT is a FAILURE (field drift), not a silent 0/0
            # F-03 CURE (deleg_b499ec12): AND-guard let rows missing ONE field sail through as 0 --
            # per-field absence is the failure (LAWS #9), name the keys seen.
            if "mentions_in_code" not in r0 or "mentions_over_cap" not in r0:
                rows.append({"kind": kind, "id": pid, "error": "delivery-fields-absent"})
                print(f"FIELDS-ABSENT {kind} {pid}: keys={sorted(r0.keys())[:8]}")
                time.sleep(2.0)
                continue
            ic, oc = r0.get("mentions_in_code") or 0, r0.get("mentions_over_cap") or 0
            rows.append({"kind": kind, "id": pid, "in_code": ic, "over_cap": oc})
            if oc: print(f"OVER CAP {kind} {pid}: in={ic} over={oc}")
        except Exception as e:
            rows.append({"kind": kind, "id": pid, "error": str(e)[:60]})
            print(f"FAILED {kind} {pid}: {str(e)[:50]}")
        time.sleep(2.0)  # pace raised 1.2->2.0: 33x HTTP 429 seen when two sweep runs shared the door (2026-11-09)
tot_in = sum(r.get("in_code",0) for r in rows); tot_over = sum(r.get("over_cap",0) for r in rows)
fails = sum(1 for r in rows if r.get("error"))
# Cure wave 2 (C5-16492): zero-work guard -- a shape-dead history file (no posts/comments keys)
# used to write an empty report at exit 0, GREEN-indistinguishable from a clean sweep.
if not rows:
    print("ZERO ROWS: history file has no posts/comments -- sweep did no work (exit 2, no report)", flush=True)
    raise SystemExit(2)
# audit cures: quiet law (weekly bell 9f54a50fed75 is no_agent: GREEN must be silence -- the aggregate
# lines printed every fire); atomic durable write; exit 1 when RED (OVER CAP / failures) -- catch #202
if tot_over or fails:
    print(f"swept: {len(rows)} | posts: {sum(1 for r in rows if r['kind']=='post')} | comments: {sum(1 for r in rows if r['kind']=='comment')}")
    print(f"in_code total: {tot_in} | over_cap total: {tot_over} | failures: {fails}")
import tempfile, os
rep = os.path.join(HOME, f"data/truncation-sweep-{time.strftime('%Y%m%d-%H%M%S')}.json")  # cure: timestamped -- same-day re-runs never overwrite RED evidence
os.makedirs(os.path.join(HOME, "data"), exist_ok=True)  # F-15 cure: fresh home
fd, tmp = tempfile.mkstemp(dir=os.path.join(HOME, "data"))
try:  # F-11 cure: unlink tmp on any failure (LAWS #13)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1); fh.flush(); os.fsync(fh.fileno())
    os.replace(tmp, rep)
except Exception:
    if os.path.exists(tmp): os.remove(tmp)
    raise
if tot_over or fails:
    print("report saved", rep)
    raise SystemExit(1)
