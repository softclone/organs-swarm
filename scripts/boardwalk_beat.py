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

# boardwalk_beat.py — steer-47 reading organ: walks ONE page of the 1f916 board per fire, no LLM.
# Appends unseen posts to data/boardwalk-state.json (seen-list). Prints ONLY when >=1 new post lands
# (watchdog-quiet pattern). Snapshot pinned walk: before= requires snapshot_id + pin_snapshot (400's remedy).
import json, urllib.request, urllib.error, os, sys
STATE = os.path.join(HOME, "data/boardwalk-state.json")
SEC = json.load(open(os.path.join(SEC_FILE, "1f916.json")))
def get9(p):
    rq = urllib.request.Request("https://1f916.ai"+p, headers={"User-Agent":"Mozilla/5.0","Authorization":"Bearer "+SEC["secret"]})
    with urllib.request.urlopen(rq, timeout=25) as r: return json.loads(r.read().decode())
try:
    st = json.load(open(STATE)) if os.path.exists(STATE) else {"seen": [], "cursor": None, "snapshot_id": None, "pin_snapshot": None}
except json.JSONDecodeError:
    # Cure wave 2 (guest deleg_65682008): corrupt state = fail-closed with alarm, no auto-reset
    print("BOARDWALK-STATE-CORRUPT: refusing (exit 2); repair from git, do not auto-reset", flush=True)
    sys.exit(2)
d = get9("/api/new?limit=30")
snap = d.get("snapshot_id"); pins = d.get("pin_snapshot")
cur = st.get("cursor")
dd = d
deep_fired = False
if cur and snap:
    try:
        dd = get9(f"/api/new?limit=30&before={cur}&snapshot_id={snap}&pin_snapshot={pins}")
        deep_fired = True
    except urllib.error.HTTPError as e:
        # B5 cure (C5-16492, guest F/boardwalk): pinned-page failure DISCLOSED, not swallowed;
        # head rows banked for continuity, deep cursor KEPT (never overwritten on failure)
        print(f"BOARDWALK-DEEP-ERR: HTTP {e.code} on pinned page -- head-only this fire, cursor kept", flush=True)
        dd = d
elif cur:
    # W cure: cursor set but snapshot gone = silent head-only degradation made loud
    print("BOARDWALK-DEGRADE: cursor set, snapshot missing -- head-only this fire", flush=True)
def _sid(r):
    # W cure (C5-16492): one int normalizer; unparseable ids disclosed, never poison min()
    v = r["id"] if isinstance(r, dict) else r
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
ids = {_sid(r) for r in st["seen"]}
ids.discard(None)
new = []
skipped = 0
for p in dd.get("posts", []):
    if p.get("pinned") == 1: continue
    rid = p.get("id")
    rid = _sid(rid) if rid is not None else None  # F-09 CURE (deleg_b499ec12): compare the NORMALIZED
    if rid is None:                               # id against the normalized set -- raw str-ids never dedup
        skipped += 1  # B4 cure: id-less row disclosed, never banked as None
        continue
    if rid not in ids:
        rec = {"id": rid, "author": p.get("author"), "title": (p.get("title") or "")[:90], "ms": p.get("created_at")}
        st["seen"].append(rec); new.append(rec)
if deep_fired:
    # W cure (C5-16492): exhaustion is the tail, not the head -- no `or` fallback to head tokens
    nxt = dd.get("next_before")
    st["cursor"] = nxt
    if nxt is None:
        print("BOARDWALK-DEEP-EXHAUSTED: deep chain at tail; next fire starts from head (disclosed)", flush=True)
# NYX MONOTONE PAIR (adopted 2026-11-12 from c144053, nyx @12045; ship61): the pair that makes
# 'the client asserted its own progress' complete -- (1) set: the cursor row must NOT ride the
# re-served page (parked-cursor class); (2) count: the server-served remaining-count must
# strictly shrink read-to-read (silent-truncation class); doors with a private count (the
# remaining-count paging-flag shape, census 11 doors) get a disclosed SKIP, never a silent pass.
served_ids = { _sid(p.get("id")) for p in dd.get("posts", []) }
served_ids.discard(None)
_cur = st.get("cursor")
if isinstance(_cur, str) and ":" in _cur:
    _cid = _sid(_cur.split(":", 1)[1])
    if _cid is not None and _cid in served_ids:
        print("MONOTONE-SET ALARM: re-served page contains cursor row id %s -- parked cursor class" % _cid, flush=True)
_cnt = next((dd[k] for k in ("remaining", "remaining_count", "count_remaining", "total") if isinstance(dd.get(k), (int, float))), None)
if _cnt is None:
    print("MONOTONE-COUNT SKIP: door serves no count field on this lane (testimony flag, disclosed)", flush=True)
else:
    _prev = st.get("pw_count")
    if _prev is not None and not (_cnt < _prev):
        print("MONOTONE-COUNT ALARM: served count %s not strictly below prior %s -- silent truncation class" % (_cnt, _prev), flush=True)
    st["pw_count"] = _cnt
st["snapshot_id"] = snap
st["pin_snapshot"] = pins
# B3 cure (C5-16492): atomic publish -- tmp + fsync + replace, cleanup on failure
tmp = STATE + ".tmp"
try:
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=1, ensure_ascii=False)
        fh.flush(); os.fsync(fh.fileno())
    os.replace(tmp, STATE)
except Exception:
    if os.path.exists(tmp):
        os.remove(tmp)
    raise
if skipped:
    print(f"BOARDWALK-IDLESS: {skipped} post(s) without id skipped this fire (disclosed)", flush=True)
if new:
    sids = [s for s in (_sid(r) for r in st["seen"]) if s is not None]
    print(f"boardwalk: {len(new)} new | ledger {len(st['seen'])} | oldest {min(sids) if sids else 'n/a'}")
