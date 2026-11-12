
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
# scripts/molt/b4_taste.py — MOLT3 batch B4: eros/eros-taste-notes-NNNN.md -> canon/taste/taste-NNNN.md
# Protocol: map before move; git mv; ref-scan (the PATCH is a follow-up leg, per F11 cure); ledger row; verify off-rig.
import os, re, subprocess, json, sqlite3, datetime, sys

SHOP = os.environ.get("ORGANS_SHOP_DIR", os.path.join(HOME, "shop"))
SRC_DIR = os.path.join(SHOP, "eros")
DST_DIR = os.path.join(SHOP, "canon", "taste")
LEDGER = os.path.join(SHOP, "MOLT3-LEDGER.md")
BATCH = "B4-taste"

def ts(): return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def main():
    pat = re.compile(r"^eros-taste-notes-(\d+)\.md$")
    srcs = sorted((int(m.group(1)), f) for f in os.listdir(SRC_DIR) if (m := pat.match(f)))
    # N3 cure (C5-16484): the vacuous `or True` filter line deleted -- dead code posing as a gate
    # MAP
    plan = [(os.path.join(SRC_DIR, f), os.path.join(DST_DIR, f"taste-{n:04d}.md")) for n, f in srcs]
    # B5 cure (C5-16484): an empty/no-match plan used to print "mapped: 0" and append a
    # 0/0 ledger row at exit 0. Refuse before any write.
    if not plan:
        print("EMPTY PLAN -- refusing (exit 2)", flush=True)
        sys.exit(2)
    os.makedirs(DST_DIR, exist_ok=True)  # F10 cure (C5-16486): side effect AFTER the refuse gate
    os.makedirs(os.path.join(SHOP, "index", "maps"), exist_ok=True)
    # W6 cure (C5-16484): atomic + utf-8
    mp = os.path.join(SHOP, "index", "maps", f"{BATCH}.map.json")
    try:
        with open(mp + ".tmp", "w", encoding="utf-8") as fh:
            json.dump([{"src": s, "dst": d} for s, d in plan], fh, indent=1)
            fh.flush(); os.fsync(fh.fileno())
        os.replace(mp + ".tmp", mp)
    except Exception:
        if os.path.exists(mp + ".tmp"):
            os.remove(mp + ".tmp")  # F8 cure (C5-16486): no .tmp residue on failure
        raise
    print("mapped:", len(plan))
    # APPLY (git mv)
    ok = 0
    for s, d in plan:
        r = subprocess.run(["git", "-C", SHOP, "mv", s, d], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")  # F9 cure (C5-16486): cp1252 decode class
        if r.returncode == 0:
            ok += 1
        else:
            print("FAIL:", s, r.stderr.strip()[:100])
    print("moved:", ok)
    # REF SCAN: code files naming the old path family (path context only; ledger-text regexes stay)
    hits = []
    unreadable = 0
    self_path = os.path.abspath(__file__)
    for dp, dns, fns in os.walk(os.path.join(SHOP, "scripts")):
        dns[:] = [d for d in dns if d != "__pycache__"]
        for fn in fns:
            if fn.endswith(".py"):
                p = os.path.join(dp, fn)
                # N4 cure (C5-16484): never count the rig's own prose (line-2 header self-match,
                # probe-confirmed) -- and skip the md5-identical twin copy by same-basename rule
                if os.path.abspath(p) == self_path or fn == "b4_taste.py":
                    continue
                # W8 cure (C5-16484): unguarded read used to kill the rig AFTER moves,
                # BEFORE the ledger -- counted skip keeps the ledger leg reachable
                try:
                    with open(p, encoding="utf-8", errors="replace") as fh:
                        t = fh.read()
                except Exception:
                    unreadable += 1
                    continue
                if re.search(r"eros[/\\]eros-taste-notes|eros-taste-notes-\{", t):
                    hits.append(p)
    print("code refs to old taste paths:", len(hits), "| unreadable:", unreadable)
    for p in hits: print("   ", p)
    # LEDGER
    # W9 cure (C5-16484): the old row claimed "verified: see below" while no verify leg
    # existed in the rig -- claims are requirements; the claim now names the real follow-up.
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(f"\n| {BATCH} | {ts()} | move eros-taste-notes->canon/taste/taste-NNNN | {ok}/{len(plan)} | code-refs-pending: {len(hits)} | unreadable-scanned: {unreadable} | verify leg NOT run in this rig: rerun index/build_index.py + molt/pointers.py, then patch code paths, per header |\n")
    print("ledger appended")
    if ok < len(plan):
        sys.exit(1)  # W7 cure (C5-16484): total/partial move failure exits 1 AFTER the ledger record

if __name__ == "__main__":
    main()
