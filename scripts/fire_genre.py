# fire_genre.py — genre fire runner: the _fire_g<N> wrapper family as ONE organ
# (MOLT4 Tier-1 #3). Collapses 169 wrappers into one runner + DATA ROWS.
# Anatomy (from the live head wrapper): body string + byte-count assert +
# runlib.venue("say", {place_id, mode line, body, request_id UUID}).
# The 169 scripts become 169 DATA ROWS (JSONL: {n, bytes, body, [place], [mode]}).
# Rows file is SHOP data (--rows); the runlib venue door is already portable.
# Config chain (runlib law): env ORGANS_* > local.json (beside) > ~/organs.json;
# keys: home, secrets, genre_place (default place id for rows without one).
# VENUE WRITE LAW: firing is a venue act — runner fires only when --fire given;
# dry (default, or explicit --dry) prints the plan. Byte-count assert is
# NON-NEGOTIABLE (inherited from every wrapper:
# `assert len(body.encode("utf-8")) == B`). request_id = fresh uuid per fire.
# RED PATHS (watched-fail prints): byte drift in any row -> PLAN names the dead
# rows, REFUSE rc2 BEFORE any door touch; dry plan prints computed counts rc0.
import json, os, sys, uuid

def cfg():
    # config chain: env > local.json (beside) > ~/organs.json  (runlib law)
    c = {}
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(here, "local.json"), os.path.expanduser("~/organs.json")):
        if os.path.isfile(p):
            for k, v in json.load(open(p, encoding="utf-8")).items():
                c.setdefault(k, v)
    c["home"] = os.environ.get("ORGANS_HOME") or c.get("home")
    c["secrets"] = os.environ.get("ORGANS_SECRETS") or c.get("secrets")
    return c

CFG = cfg()

def load_rows(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows

def main():
    import argparse
    ap = argparse.ArgumentParser(prog="fire-genre")
    ap.add_argument("--rows", required=True, help="JSONL data rows {n, bytes, body, [place], [mode]}")
    ap.add_argument("--n", type=int, help="fire only genre n")
    ap.add_argument("--fire", action="store_true", help="venue write (default dry)")
    ap.add_argument("--dry", action="store_true", help="plan only (the default; --fire overrides)")
    ap.add_argument("--place", type=int, default=int(CFG.get("genre_place", 1367)))
    a = ap.parse_args()
    rows = [r for r in load_rows(a.rows) if a.n is None or r["n"] == a.n]
    # byte asserts FIRST (plan green before any door touch)
    bad = [r["n"] for r in rows if len(r["body"].encode("utf-8")) != r["bytes"]]
    print(f"PLAN genres={len(rows)} byte-assert-deaths={len(bad)} {bad[:5]}")
    if bad:
        print("REFUSE: byte drift in data rows"); return 2
    if not a.fire:
        for r in rows[:5]:
            print(f"  [dry] GENRE {r['n']} bytes={r['bytes']} place={r.get('place', a.place)}")
        print("FIRE-GENRE-DONE (dry)"); return 0
    sys.path.insert(0, os.path.join(CFG["home"], "scripts"))
    from runlib import venue  # packaged venue door (config chain, ORGANS_ROUTES shim)
    fired = 0
    for r in rows:
        out = venue("say", {"place_id": r.get("place", a.place), "mode": r.get("mode", "line"),
                            "body": r["body"], "request_id": str(uuid.uuid4())})
        fired += 1
        print(f"GENRE {r['n']} fired:", json.dumps(out, ensure_ascii=False)[:120])
    print(f"FIRE-GENRE-DONE fired={fired}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
