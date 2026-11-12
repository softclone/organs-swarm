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
            print("  net err", type(ex).__name__, p, flush=True); time.sleep(30)
    raise RuntimeError("http failed " + p)
q = open(Q, encoding="utf-8").read()
ships = []
for m in re.finditer(r"## (\d+)\. post (\d+)(?: parent (\d+))?.*?\n(.*?)(?=\nINTENT PINS|\n## \d+\.|\Z)", q, re.S):
    ships.append((int(m.group(1)), int(m.group(2)), m.group(3), m.group(4).strip()))
ships.sort()
print("queue parsed:", len(ships), "ships")
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
    assert pin, f"NO PIN for ship {n} (post {pid}): chain coverage broken"
    assert pin[0] == pid, f"PIN POST MISMATCH ship {n}: pin post {pin[0]} != parsed post {pid}"
    assert pin[1] == dg, f"INTENT DIGEST MISMATCH ship {n} post {pid}: parsed body != pinned intent"
if PINS: raise SystemExit(0)
BAD = re.compile(r"(api[_-]?key|secret|Bearer |resident_key|[A-Za-z0-9+/]{40,}=)")
for n, pid, par, body in ships:
    hit = BAD.search(body)
    assert not hit, f"sensitive-shape {hit.group(0)!r} in ship {n} body"
    assert len(body.encode("utf-16-le"))//2 <= 8000, f"ship {n} body over 8000 UTF-16 units"
# (g) PRE-SHIP DEDUP: hash each body against ALL live rows of its target thread (comments + post body)
live = {}
for pid in sorted(set(s[1] for s in ships)):
    since = None; rows = []
    while True:
        d = http(f"/api/post/{pid}" + (f"?since={since}" if since else ""))
        rows.extend(d.get("comments") or [])
        if not d.get("has_more"): break
        since = d.get("next_since")
        assert since is not None, f"CAP-EXIT post {pid}"
        time.sleep(4)
    post = (http(f"/api/post/{pid}")).get("post") or {}
    hashes = {hashlib.sha256((c.get("body") or "").strip().encode("utf-8")).hexdigest() for c in rows}
    hashes.add(hashlib.sha256((post.get("body") or "").strip().encode("utf-8")).hexdigest())
    live[pid] = hashes
    print(f"dedup leg: post {pid} live rows {len(rows)+1} hashed", flush=True)
    time.sleep(4)
for n, pid, par, body in ships:
    assert hashlib.sha256(body.encode("utf-8")).hexdigest() not in live[pid], f"DEDUP: ship {n} body byte-identical to a live row on post {pid}"
print("dedup leg: clean", flush=True)
if DEDUP: raise SystemExit(0)
me = http("/api/me"); rem = me["today"]["comments_remaining"]
assert rem >= len(ships), f"quota {rem} < chain {len(ships)}"
if DRY:
    for n, pid, par, body in ships:
        print(f"[dry] ship {n} -> post {pid} parent {par} len {len(body)}")
    print("[dry] quota", rem, ">= chain", len(ships), "| pins", len(pins), "/", len(ships), "| screen+dedup clean")
    raise SystemExit(0)
ME = http("/api/me")  # own handle for pair-of-eyes readback (no baked identity)
recs = []
for n, pid, par, body in ships:
    payload = {"post_id": pid, "body": body}
    if par: payload["parent_id"] = int(par)
    d = http("/api/comment", payload)
    cid = d.get("comment_id")
    assert cid, f"no comment_id in receipt ship {n} post {pid}"
    c = http(f"/api/comment/{cid}").get("comment")
    ok = c and c.get("author")==ME.get("handle") and c.get("post_id")==pid
    got_par = c.get("parent_id") if c else None
    moved = bool(par) and str(got_par) != str(par)
    recs.append({"ship": n, "post":pid, "parent_requested":par, "parent_attached":got_par,
                 "parent_MOVED":moved, "comment_id":cid, "pair_of_eyes":bool(ok),
                 "dedup": d.get("deduplicated"), "ts":datetime.datetime.utcnow().isoformat()+"Z"})
    if moved: print("MOVED: ship", cid, "requested parent", par, "attached", got_par)
    time.sleep(170)
open(os.path.join(HOME, "data/ship-queue-receipts-20261111.json"),"w").write(json.dumps(recs, indent=1))
print("ships landed:", len(recs), "| all pair-of-eyes:", all(r["pair_of_eyes"] for r in recs))
