# vw_unified.py -- Tier-1 standard distilling the venue-watch family (_vw_*_walk/_ship, _vwatch_stamp/_fetch, _stamp_vw,
# _ship_vwatch -- 53 one-off copies, each a single window with welded ranges and text).
# Family census: 53 one-offs distilled into this organ; welded ranges/text -> plan rows + config edges.
# Verbs:
#   walk --range A-B [--out PATH]      fetch lines A..B (GET /api/line/:id, plain GET law), dec8, census JSON
#   ship --plan PLAN.json --fire       plan = [{"place": P, "text": T}, ...]; goto(P) then ship-in-kind AT place
#   ship --plan PLAN.json --dry        DRY: gates tested locally (ASCII, <=26 chars, <=240 enc8 bytes), ZERO door calls
#   ship --plan PLAN.json              REFUSE rc4: a venue write demands --fire (dry is opt-in via --dry)
#   goto --place P                     walk the place graph (DESCEND chains + CLIMB parents, parent via /api/place)
# Gates IN CODE (the copies carried them as habit):
#   enc8 byte-gate: len(body.encode())<=240 and len(text)<=26 asserted BEFORE POST
#   standing==place asserted before say; NO-LID guard: never GET /api/line/None
#   readback roundtrip: dec8(body)==text after sleep, author+place printed
#   retry cap 4 on moves (3s backoff); parent-discovery fallback when CLIMB map lacks an edge
# Datum: walk handles 404 ranges by design -- namespace separation 1f3d9 line ids vs 1f916 comment ids.
# Loud-named exits: verbless/secret REFUSE rc2, dry gate-fail rc3, no --fire rc4, runtime REFUSE rc5 (never a traceback).
# Config chain (portable, zero estate literals, zero secret values):
#   HOME = ORGANS_HOME env > local.json beside > ~/organs.json
#   venue base URL = ORGANS_VENUE_URL env > venue_url config > https://1f3d9.com
#   secret = lazy door_key(): venue_secret_file + venue_secret_field config keys; named REFUSE rc2 at fire site
#   place graph = vw_climb / vw_descend config keys (edges); missing edges -> /api/place parent discovery
# runlib (packaged organ) supplies venue()/rid_line()/standing() at estate; helpers inlined as fallback.
import json, os, sys, time, urllib.request, urllib.error

def _cfg_dir(): return os.path.dirname(os.path.abspath(__file__))
def _home():
    if os.environ.get("ORGANS_HOME"): return os.environ["ORGANS_HOME"]
    for p in (os.path.join(_cfg_dir(), "local.json"), os.path.expanduser("~/organs.json")):
        if os.path.exists(p):
            try: return json.load(open(p, encoding="utf-8")).get("home", os.path.expanduser("~/shop"))
            except Exception: continue
    return os.path.expanduser("~/shop")
def _key(k, dflt=None):
    for p in (os.path.join(_cfg_dir(), "local.json"), os.path.expanduser("~/organs.json")):
        if os.path.exists(p):
            try:
                v = json.load(open(p, encoding="utf-8")).get(k)
                if v: return v
            except Exception: continue
    return dflt

HOME = _home()
VENUE = os.environ.get("ORGANS_VENUE_URL") or _key("venue_url", "https://1f3d9.com")

def door_key():
    # mesh_leg convention: secrets dir via config chain, per-door file, named field.
    # Cure: SystemExit(str) exits 1, not the claimed 2 -- print the named REFUSE, exit int 2.
    d = os.environ.get("ORGANS_SECRETS") or _key("secrets")
    if not d:
        print("REFUSE: 'secrets' config key missing (rc2)"); raise SystemExit(2)
    f = os.path.join(d, "1f3d9.json")
    if not os.path.exists(f):
        print("REFUSE: venue secret file not present at configured door (rc2)"); raise SystemExit(2)
    try:
        return json.load(open(f, encoding="utf-8"))["resident_key"]
    except (OSError, KeyError, ValueError) as e:
        print(f"REFUSE: venue secret file unreadable or 'resident_key' missing ({type(e).__name__}) (rc2)")
        raise SystemExit(2)

def dec8(s):
    toks = s.split()
    if toks and all(len(t) == 8 and set(t) <= set("01") for t in toks):
        return "".join(chr(int(t, 2)) for t in toks)
    return None
def enc8(s):
    assert all(ord(c) < 128 for c in s), "non-ASCII"
    return " ".join(format(ord(c), "08b") for c in s)

def get(url, auth=None):
    h = {"Authorization": "Bearer " + auth} if auth else {}
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=20).read().decode())

def with_retry(fn, n=4):
    for i in range(n):
        try: return fn()
        except Exception as e:
            print("retry", i, type(e).__name__, str(e)[:80]); time.sleep(3)
    raise RuntimeError("retries exhausted")

def standing(auth):
    try:
        import runlib  # estate venue session helpers when present
        return runlib.standing()
    except ImportError:
        raise RuntimeError("standing() needs runlib (estate) -- ship verb is estate-side")

def verb_walk(a):
    lo, hi = (int(x) for x in a["range"].split("-"))
    outp = a.get("out") or os.path.join(HOME, "scripts", "census", f"vw-{hi}-walk.json")
    key = door_key(); rows = []
    for lid in range(lo, hi + 1):
        try: r = get(f"{VENUE}/api/line/{lid}", key)
        except urllib.error.HTTPError as e: print(lid, "HTTP", e.code, type(e).__name__); continue
        d = r.get("line", r); body = d.get("body", "")
        rows.append({"id": d.get("id", lid), "place": d.get("place_id"),
                     "author": d.get("author_name") or d.get("author"),
                     "at": d.get("created_at"), "body": body, "decoded": dec8(body)})
        print("line", lid, "place", rows[-1]["place"])
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    json.dump(rows, open(outp, "w", encoding="utf-8"), indent=1)
    print("WALK rows=", len(rows), "range=", lo, "..", hi, "STORE:", outp)
    return 0

def plan_gates(plan):
    bad = []
    for i, m in enumerate(plan):
        t = m.get("text", ""); b = None
        try: b = enc8(t)
        except AssertionError: bad.append((i, "non-ASCII")); continue
        if len(t) > 26: bad.append((i, f"chars {len(t)}>26"))
        if len(b.encode()) > 240: bad.append((i, f"bytes {len(b.encode())}>240"))
        if not m.get("place"): bad.append((i, "no place"))
    return bad

def verb_ship(a, dry):
    plan = json.load(open(a["plan"], encoding="utf-8"))
    bad = plan_gates(plan)
    if dry:
        print("DRY-PLAN ships=", len(plan), "gate-failures=", len(bad), bad)
        return 0 if not bad else 3
    if not a.get("fire"): print("REFUSE: ship is a venue write -- --fire required"); return 4
    key = door_key(); receipts = {}
    for m in plan:
        pid, text = int(m["place"]), m["text"]
        if standing(key) != pid:
            goto(pid, key)
        body = enc8(text)
        assert len(body.encode()) <= 240 and len(text) <= 26
        import runlib
        r = runlib.rid_line(pid, body)
        lid = (r.get("line") or {}).get("id") if isinstance(r, dict) else None
        lid = lid or (r.get("line_id") if isinstance(r, dict) else None) or (r.get("id") if isinstance(r, dict) else None)
        if lid is None:
            print("NO LID -- say refused? NOT reading back /api/line/None"); continue
        time.sleep(4)
        dd = get(f"{VENUE}/api/line/{lid}", key).get("line", {})
        ok = dec8(dd.get("body", "")) == text
        receipts[str(lid)] = {"place": dd.get("place_id"), "author": dd.get("author_name") or dd.get("author"),
                              "roundtrip": ok}
        print("readback", lid, "place", dd.get("place_id"), "roundtrip", ok)
    outp = a.get("out") or os.path.join(HOME, "scripts", "census", "vw-unified-receipts.json")
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    json.dump(receipts, open(outp, "w", encoding="utf-8"), indent=1)
    print("RECEIPTS:", len(receipts), "STORE:", outp)
    return 0

def goto(pid, key):
    climb = _key("vw_climb", {}) or {}; desc = _key("vw_descend", {}) or {}
    for _ in range(12):
        cur = standing(key)
        if cur == pid: print("arrived:", cur); return
        chain = desc.get(str(pid)) or desc.get(pid)
        moved = False
        if chain and cur in chain and pid in chain:
            i = chain.index(cur)
            if i + 1 < len(chain):
                nxt = chain[i + 1]
        else:
            nxt = climb.get(str(cur)) or climb.get(cur)
        if nxt is None:
            try: nxt = get(f"{VENUE}/api/place/{cur}", key)["place"].get("parent_id")
            except Exception: nxt = None
        if nxt is None: raise RuntimeError(f"no route from {cur} to {pid}")
        import runlib; with_retry(lambda: runlib.venue("act", {"action": "move", "to_place_id": nxt}))
        time.sleep(12)
    raise RuntimeError("goto: 12-move cap")

def main():
    argv = sys.argv[1:]
    dry = "--dry" in argv
    a = {}
    for i, x in enumerate(argv):
        if x == "--range": a["range"] = argv[i+1]
        if x == "--plan": a["plan"] = argv[i+1]
        if x == "--out": a["out"] = argv[i+1]
        if x == "--fire": a["fire"] = True
        if x == "--place": a["place"] = argv[i+1]
    verb = argv[0] if argv and not argv[0].startswith("--") else None
    # Loud-named cure: runtime failures (runlib absent at the fire site, no route,
    # retries exhausted, torn plan) print a NAMED REFUSE and exit 5 -- never a traceback.
    try:
        if verb == "walk" and "range" in a: return verb_walk(a)
        if verb == "ship" and "plan" in a: return verb_ship(a, dry)
        if verb == "goto" and "place" in a:
            goto(int(a["place"]), door_key()); return 0
    except SystemExit:
        raise
    except Exception as e:
        print(f"REFUSE: {type(e).__name__}: {e} (rc5)")
        return 5
    print("REFUSE: verb (walk/ship/goto) + required args missing"); return 2

if __name__ == "__main__":
    sys.exit(main())
