
import os
import os
HOME = os.environ.get("ORGANS_HOME", os.path.expanduser("~/shop"))

#!/usr/bin/env python
# scripts/molt/batch.py - generalized MOLT3 canon batch runner
# usage: python batch.py <batch-id> <family-regex> <src-dir(s) sep by ,> <dst-dir> <dst-name-template {n:04d}>
# protocol: map -> git mv -> ref-scan (code paths) -> ledger row. Verify via build_index + counts.
import os, re, subprocess, json, datetime, sys

SHOP = os.environ.get("ORGANS_SHOP_DIR", os.path.join(HOME, "shop"))
LEDGER = os.path.join(SHOP, "MOLT3-LEDGER.md")

def ts(): return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def main(batch_id, pat_s, src_dirs, dst_dir, name_tmpl):
    pat = re.compile(pat_s)
    plan = []
    for sd in src_dirs.split(","):
        sd = os.path.join(SHOP, sd)
        # B4 cure (C5-16484): a missing src dir used to be skipped silently -> plan=[]
        # -> "0/0" ledger row recorded as a completed batch at exit 0. Loud refuse.
        if not os.path.isdir(sd):
            print(f"SRC DIR MISSING: {sd} -- refusing (exit 2)", flush=True)
            sys.exit(2)
        for fn in os.listdir(sd):
            m = pat.match(fn)
            if m:
                n = int(m.group(1))
                plan.append((os.path.join(sd, fn), os.path.join(SHOP, dst_dir, name_tmpl.format(n=n))))
    if not plan:
        print("EMPTY PLAN -- refusing (exit 2)", flush=True)
        sys.exit(2)
    dst = os.path.join(SHOP, dst_dir); os.makedirs(dst, exist_ok=True)
    # name-collision check
    names = [os.path.basename(d) for _, d in plan]
    dup = {x for x in names if names.count(x) > 1}
    if dup:
        print("COLLISIONS (batch refuses, needs mapping law):", list(dup)[:10]); sys.exit(2)
    os.makedirs(os.path.join(SHOP, "index", "maps"), exist_ok=True)
    # W3 cure (C5-16484): atomic + utf-8 -- the map IS the rollback contract; the old
    # non-atomic cp1252-default dump could tear or mangle non-ASCII names
    mp = os.path.join(SHOP, "index", "maps", f"{batch_id}.map.json")
    try:
        with open(mp + ".tmp", "w", encoding="utf-8") as fh:
            json.dump([{"src": s, "dst": d} for s, d in plan], fh, indent=1)
            fh.flush(); os.fsync(fh.fileno())
        os.replace(mp + ".tmp", mp)
    except Exception:
        if os.path.exists(mp + ".tmp"):
            os.remove(mp + ".tmp")  # F6 cure (C5-16486): no .tmp residue on failure
        raise
    ok = 0
    for s, d in plan:
        r = subprocess.run(["git", "-C", SHOP, "mv", s, d], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")  # N1: cp1252 decode cure
        ok += (r.returncode == 0)
        if r.returncode: print("FAIL:", s, r.stderr.strip()[:90])
    hits = []
    unreadable = 0
    for dp, dns, fns in os.walk(os.path.join(SHOP, "scripts")):
        dns[:] = [d for d in dns if d != "__pycache__"]
        for fn in fns:
            if fn.endswith(".py"):
                p = os.path.join(dp, fn)
                try:
                    with open(p, encoding="utf-8", errors="replace") as fh:
                        t = fh.read()
                except Exception:
                    unreadable += 1  # W4 cure (C5-16484): dropped files counted -- "refs found: 0"
                    continue         # must not be a false clean when code went unread
                for sd in src_dirs.split(","):
                    # F7 cure (C5-16486, guest): strip filename anchors -- re.search of an
                    # anchored pattern over whole-file text matches NOTHING (false-clean);
                    # and allow BOTH separators at every path component (git-dirs vary)
                    parts = sd.replace("\\", "/").split("/")
                    sd_re = r"[/\\]".join(re.escape(x) for x in parts if x)
                    stem = pat_s
                    if stem.startswith("^"): stem = stem[1:]
                    if stem.endswith("$"): stem = stem[:-1]
                    stem = stem.replace(r"(\d+)", r"\d+")
                    if re.search(sd_re + r"[/\\]" + stem, t):
                        hits.append((p, sd)); break
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(f"\n| {batch_id} | {ts()} | move {pat_s} {src_dirs} -> {dst_dir}/{name_tmpl} | {ok}/{len(plan)} | code-path refs found: {len(hits)} (listed) | unreadable-scanned: {unreadable} |\n")
    print(f"{batch_id}: moved {ok}/{len(plan)}; code refs: {hits[:8]} | unreadable: {unreadable}")
    if ok < len(plan):
        sys.exit(1)  # W5 cure (C5-16484): partial move failure is NOT a clean batch

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
