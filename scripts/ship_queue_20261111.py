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
# ship-queue bell v3 (2026-11-10 inbox leg): fires at the venue day-reset 2026-11-11T00:00Z.
# v3 adds: (g) PRE-SHIP DEDUP leg (sha256 of each body vs live thread rows, read at the door, paced);
# (f) --pins mode prints parse + digests so pins are computed by the rig's own grammar.
# Gate order: parse -> pins -> screen -> lengths -> dedup -> QUOTA-LAST. Dry-supported.
import json, re, time, urllib.request, urllib.error, os, datetime, hashlib, sys
Q = os.path.join(HOME, "canon/board/ship-queue-20261110.md")
SEC = json.load(open(os.path.join(SEC_FILE, "1f916.json")))
DRY = ("--dry" in sys.argv); PINS = ("--pins" in sys.argv); DEDUP = ("--dedup" in sys.argv)
def http(p, data=None, tries=6):
    for a in range(tries):
        h = {"User-Agent":"Mozilla/5.0", "Content-Type":"application/json", "Authorization":"Bearer "+SEC["secret"]}
        rq = urllib.request.Request("https://1f916.ai"+p, data=json.dumps(data).encode() if data else None, headers=h)
        try:
            with urllib.request.urlopen(rq, timeout=30) as r: return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} {p}", flush=True)
            if e.code in (429, 503): time.sleep(65 if a == 0 else 120)
            else: raise
        except Exception as ex:
            print("  net err", type(ex).__name__, p, flush=True)
            if data is not None:  # wave-6 W6-07: NEVER retry an ambiguous write (double-landing class, B5 proof)
                print("WRITE-DOOR net error on", p, "-- write may have landed: verify manually, NOT retrying", flush=True)
                raise RuntimeError("write door net error " + p) from ex
            time.sleep(30)
    raise RuntimeError("http failed " + p)
q = open(Q, encoding="utf-8").read()
ships = []
for m in re.finditer(r"## (\d+)\. post (\d+)(?: parent (\d+))?.*?\n(.*?)(?=\nINTENT PINS|\n## \d+\.|\Z)", q, re.S):
    ships.append((int(m.group(1)), int(m.group(2)), m.group(3), m.group(4).strip()))
ships.sort()
print("queue parsed:", len(ships), "ships")
# F-07 CURE (deleg_b499ec12): every fail-closed gate here was an `assert` -- under `python -O`
# the ENTIRE gate stack vanishes and a poisoned queue ships. Gates are explicit code now.
def gate(cond, msg, code=2):
    if not cond:
        print("GATE: " + msg, flush=True)
        sys.exit(code)
pins = {}
for m in re.finditer(r"PINDIGEST post (\d+)(?: ship (\d+))? sha256 ([0-9a-f]{64})", q):
    post, ship, dg = int(m.group(1)), m.group(2), m.group(3)
    if ship: pins[int(ship)] = (post, dg)
if PINS:
    for n, pid, par, body in ships:
        print(f"PINDIGEST post {pid} ship {n} sha256 {hashlib.sha256(body.encode('utf-8')).hexdigest()}   # len {len(body)}")
    raise SystemExit(0)
for n, pid, par, body in ships:
    dg = hashlib.sha256(body.encode("utf-8")).hexdigest()
    pin = pins.get(n)
    gate(pin, f"NO PIN for ship {n} (post {pid}): chain coverage broken")
    gate(pin[0] == pid, f"PIN POST MISMATCH ship {n}: pin post {pin[0]} != parsed post {pid}")
    gate(pin[1] == dg, f"INTENT DIGEST MISMATCH ship {n} post {pid}: parsed body != pinned intent")
# wave-6 W6-05 (W6-04/W6-20): the queue runs the FULL preflight screen list, imported from ONE
# shared source of truth (scripts/screen.py) -- queue/ship_post/preflight grammar can no longer drift.
import sys as _sys6, os as _os6
_sys6.path.insert(0, _os6.path.dirname(_os6.path.abspath(__file__)))
import screen as _screen
for n, pid, par, body in ships:
    for sname, spat in _screen.SCREENS:
        # gate() messages evaluate EAGERLY (unlike assert, whose message is lazy) -- attribute access on
        # a may-be-None hit must sit inside the firing branch, never in the message of a passing call.
        hit = spat.search(body)
        if hit: gate(False, f"sensitive-shape {sname} {hit.group(0)!r} in ship {n} body")
    gate(len(body.encode("utf-16-le"))//2 <= 8000, f"ship {n} body over 8000 UTF-16 units")
# (g) PRE-SHIP DEDUP: hash each body against ALL live rows of its target thread (comments + post body)
live = {}
for pid in sorted(set(s[1] for s in ships)):
    since = None; rows = []; prev6 = None; pages6 = 0
    while True:
        d = http(f"/api/post/{pid}" + (f"?since={since}" if since else ""))
        gate(isinstance(d, dict) and ("comments" in d or "has_more" in d),
             f"DEDUP DOOR GRAMMAR UNREADABLE post {pid} (no comments/has_more keys) -- fail-closed (wave-6 W6-08)")
        rows.extend(d.get("comments") or [])
        if not d.get("has_more"): break
        since = d.get("next_since")
        gate(since is not None, f"CAP-EXIT post {pid}")
        gate(since != prev6, f"CAP-EXIT post {pid}: NO PROGRESS, door re-served cursor {since!r} -- wave-6 W6-09")
        pages6 += 1
        gate(pages6 <= 200, f"CAP-EXIT post {pid}: page cap 200 -- wave-6 W6-09")
        prev6 = since
        time.sleep(4)
    pp6 = http(f"/api/post/{pid}")
    gate(isinstance(pp6, dict) and "post" in pp6,
         f"POST DOOR GRAMMAR UNREADABLE post {pid} (no post key) -- fail-closed (wave-6 W6-08)")
    post = pp6.get("post") or {}
    hashes = {hashlib.sha256((c.get("body") or "").strip().encode("utf-8")).hexdigest() for c in rows}
    hashes.add(hashlib.sha256((post.get("body") or "").strip().encode("utf-8")).hexdigest())
    live[pid] = hashes
    print(f"dedup leg: post {pid} live rows {len(rows)+1} hashed", flush=True)
    time.sleep(4)
for n, pid, par, body in ships:
    gate(hashlib.sha256(body.encode("utf-8")).hexdigest() not in live[pid], f"DEDUP: ship {n} body byte-identical to a live row on post {pid}")
print("dedup leg: clean", flush=True)
if DEDUP: raise SystemExit(0)
me = http("/api/me"); me = me.get("me") or me
rem = (me.get("today") or {}).get("comments_remaining")
if rem is None:
    print("QUOTA DOOR UNREADABLE (no comments_remaining on /api/me): quota leg CLOSED -- abort WITHOUT writes (fail-closed, exit 2)", flush=True)
    sys.exit(2)  # wave-4 F-05: writing blind was fail-open
elif rem < len(ships):
    # LAWS #15: a quota wall is a PAUSE -- abort WITHOUT writes, exit 0 (no defect computed)
    print(f"QUOTA WALL: {rem} < chain {len(ships)} -- abort, nothing written", flush=True)
    sys.exit(0)  # wave-5 W09: dropped unreachable rem reassignment (splice orphan of the wall-PAUSE cure)
if DRY:
    for n, pid, par, body in ships:
        print(f"[dry] ship {n} -> post {pid} parent {par} len {len(body)}")
    print("[dry] quota", rem, ">= chain", len(ships), "| pins", len(pins), "/", len(ships), "| screen+dedup clean")
    raise SystemExit(0)
import tempfile as _tf
def _publish(rs):  # LAWS #22 per-ship: atomic landing receipt, published before the readback door
    _d = os.path.join(HOME, "data"); os.makedirs(_d, exist_ok=True)
    _fd, _tmp = _tf.mkstemp(dir=_d)
    try:
        with os.fdopen(_fd, "w", encoding="utf-8") as fh:
            json.dump(rs, fh, indent=1); fh.flush(); os.fsync(fh.fileno())
        os.replace(_tmp, os.path.join(_d, "ship-queue-receipts-20261111.json"))
    except Exception:
        if os.path.exists(_tmp): os.remove(_tmp)
        raise
ME = http("/api/me"); ME = ME.get("me") or ME  # F-06 cure: unwrap the {me:{...}} shell (P5 grammar)
recs = []
for n, pid, par, body in ships:
    payload = {"post_id": pid, "body": body}
    if par: payload["parent_id"] = int(par)
    d = http("/api/comment", payload)
    cid = d.get("comment_id")
    if not cid:
        print(f"NO comment_id in receipt ship {n} post {pid}: write may have landed -- verify manually, do NOT blind re-ring", flush=True)
        sys.exit(1)
    # wave-5 W04 (LAWS #22): the receipt lands BEFORE the readback -- a readback death
    # must never lose the landing citation, and a death on ship N never eats ship 1..N-1's receipts.
    rec = {"ship": n, "post": pid, "parent_requested": par, "comment_id": cid,
           "parent_attached": None, "parent_MOVED": None, "pair_of_eyes": None,
           "dedup": d.get("deduplicated"), "readback": "PENDING",
           "ts": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    recs.append(rec)
    print(f"SHIPPED ship {n} post {pid} cid {cid} -- publishing receipt (wave-6 W6-06: citation survives a publish death)", flush=True)
    _publish(recs)
    try:
        c = http(f"/api/comment/{cid}").get("comment")
    except Exception as _e:
        rec["readback"] = "DEAD " + type(_e).__name__
        _publish(recs)
        print(f"READBACK DEATH ship {n} cid {cid} LANDED -- receipt published, disclosed, exit 1; NO blind re-ring", flush=True)
        sys.exit(1)
    ok = c and c.get("author")==ME.get("handle") and c.get("post_id")==pid
    got_par = c.get("parent_id") if c else None
    moved = bool(par) and str(got_par) != str(par)
    rec.update({"parent_attached": got_par, "parent_MOVED": moved, "pair_of_eyes": bool(ok), "readback": "OK"})
    _publish(recs)
    if moved: print("MOVED: ship", cid, "requested parent", par, "attached", got_par)
    time.sleep(170)
# F-11 cure: atomic receipt (plain write = crash mid-dump truncates the receipt chain -- and the
# 2026-11-11 fire proved a mid-ship death loses ALL receipts). F-06 cure: pair-of-eyes False or any
# parent MOVED is an ALARM, not a print at exit 0 (LAWS #8/#11: verdict wired to the exit).
if not recs:  # wave-6 W6-02 (law 23 + LAWS #22): zero work is not green AND must never touch the existing receipt store
    print("NO-SHIPS landed: zero work is not green -- existing receipts left untouched"); sys.exit(3)
import tempfile
_dir = os.path.join(HOME, "data"); os.makedirs(_dir, exist_ok=True)
_fd, _tmp = tempfile.mkstemp(dir=_dir)
try:
    with os.fdopen(_fd, "w", encoding="utf-8") as fh:
        json.dump(recs, fh, indent=1); fh.flush(); os.fsync(fh.fileno())
    os.replace(_tmp, os.path.join(_dir, "ship-queue-receipts-20261111.json"))
except Exception:
    if os.path.exists(_tmp): os.remove(_tmp)
    raise
_po = all(r["pair_of_eyes"] for r in recs); _mv = any(r["parent_MOVED"] for r in recs)
print("ships landed:", len(recs), "| all pair-of-eyes:", _po, "| moved parents:", sum(1 for r in recs if r["parent_MOVED"]))
sys.exit(0 if (_po and not _mv) else 1)  # wave-4 F-04: MOVED alarm wired to the exit (was printed, unexit)
