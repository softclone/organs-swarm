import json
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
# index/build_index.py - regenerate index.db (two scan roots under HOME; keep deployed twin md5-synced, C5-16484 N7) from census (MOLT3 plan, batch 0)
# Disposable by construction: full rebuild from disk + census jsonl. Run: python index/build_index.py
import json, sqlite3, os, re, sys, datetime, shutil

def _cfgkey(k):
    import json as _j
    for _p in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"),
               os.path.expanduser("~/organs.json")):
        try:
            v = _j.load(open(_p, encoding="utf-8")).get(k)
            if v: return v
        except Exception: pass
    return None
SHOP = os.environ.get("ORGANS_SHOP_DIR") or _cfgkey("shop_dir") or os.path.join(HOME, "shop")
LEG  = os.environ.get("ORGANS_LEG_DIR") or _cfgkey("leg_dir") or os.path.join(HOME, "contribution")
DB   = os.path.join(SHOP, "index", "index.db")

FAMS = [
 (r"eros-taste-notes-\d+\.md","taste"),(r"eros-\d+\.md","eros"),(r"MEDITATION-\d+\.md","medit"),
 (r"meditation-\d+\.md","medit"),(r"journal-core-\d+\.md","diary"),(r"journal-note-\d+\.md","board-journal"),
 (r"journal-\d+\.md","diary"),(r"pole-\d+\.md","pole"),(r"weekly-scene-\d+\.md","scene"),
 (r"DREAM\S*\.md","dream"),  # wave-5 W11 truth: shop-GENRE file patterns are built-in defaults; estate IDENTITY grammar (handles, names) rides config "index_rules": [[regex, family], ...]
 (r".*\.pyc","byproduct"),(r".*\.py$","code"),(r".*\.jsonl","data"),(r".*\.json","data"),
 (r".*\.md","doc"),(r".*\.txt","data"),(r".*\.log","byproduct"),(r".*\.mp3$|.*\.wav$","media"),
 (r".*\.npy$|.*\.npz$","data"),(r".*\.gz$","byproduct"),(r".*\.claimed$","data"),(r".*\.pid$","byproduct"),
 (r".*\.csv","data"),(r".*\.html?","data"),(r".*\.db","data"),(r".*\.zip","data"),
 (r".*\.(png|jpg|jpeg|gif|svg)","media"),(r".*\.(gguf|bin|safetensors)","model"),(r".*","misc"),
]
for _q in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"), os.path.expanduser("~/organs.json")):
    try:
        _extra = json.load(open(_q, encoding="utf-8")).get("index_rules")
        if _extra:
            _cut = next((i for i, (pat, _f) in enumerate(FAMS) if pat.startswith(".*")), len(FAMS) - 1)  # wave-5 W02: config rules outrank EVERY extension catch-all, not just the final .*->misc
            FAMS = FAMS[:_cut] + [(r, f) for r, f in _extra] + FAMS[_cut:]
            break
    except Exception: pass
def fam(n):
    for p, f in FAMS:
        if re.match(p, n):
            return f
    return "misc"

def walk(root, tag, rows):
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for fn in files:
            p = os.path.join(dirpath, fn)
            try:
                st = os.stat(p)
            except Exception:
                SKIPS[0] += 1  # W2 cure (C5-16484): stat failures counted, disclosed, never silently dropped
                continue
            rows.append((tag, p, os.path.relpath(dirpath, root).replace("\\", "/") or ".",
                         fn, os.path.splitext(fn)[1].lower(), st.st_size,
                         int(st.st_mtime), int(st.st_ctime), fam(fn), "LIVE"))

SKIPS = [0]

def main():
    rows = []
    # B1 cure (C5-16484): missing roots must LOUD-fail -- os.walk on a dead root yields [] silently
    for root, tag in ((SHOP, "primary"), (LEG, "legacy")):
        if tag == "legacy" and LEG.strip().lower() in ("", "none", "retired"):
            # explicit retirement (2026-11-12): a shop with NO legacy tree says so -- the rig
            # indexes one root and prints the retirement; silence about a root stays LOUD-fail.
            print("legacy root RETIRED by explicit ORGANS_LEG_DIR=none -- indexing primary only", flush=True)
            continue
        if not os.path.isdir(root):
            print(f"root MISSING: {tag} {root} -- refusing (exit 2)", flush=True)
            sys.exit(2)
        walk(root, tag, rows)
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    # W1 cure v2 (C5-16486, guest F1/F2/F3): the live DB is NEVER touched until the new
    # one is fully built AND reported; publish is the last act (os.replace is atomic).
    tmp = DB + ".tmp"
    for f in (tmp, tmp + "-journal"):
        if os.path.exists(f):
            os.remove(f)
    try:
        con = sqlite3.connect(tmp); cur = con.cursor()
        cur.executescript("""
          CREATE TABLE files(id INTEGER PRIMARY KEY, root TEXT, path TEXT, dir TEXT, name TEXT, ext TEXT,
            size INTEGER, mtime INTEGER, ctime INTEGER, family TEXT, status TEXT, UNIQUE(root, path));
          CREATE TABLE ops(id INTEGER PRIMARY KEY, batch TEXT, op TEXT, src TEXT, dst TEXT, ts TEXT, verified INTEGER);
          CREATE TABLE refs(id INTEGER PRIMARY KEY, source TEXT, target TEXT, kind TEXT);
          CREATE VIEW canon_outside AS SELECT family, dir, count(*) c FROM files WHERE root='primary'
            AND family IN ('taste','eros','medit','diary','pole','scene','dream')
            GROUP BY family, dir;
        """)
        cur.executemany("INSERT OR REPLACE INTO files(root,path,dir,name,ext,size,mtime,ctime,family,status) VALUES(?,?,?,?,?,?,?,?,?,?)", rows)
        con.commit()
        n = cur.execute("SELECT count(*) FROM files").fetchone()[0]
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if n == 0:
            # F2 cure: refuse happens BEFORE the live DB is touched -- old index survives
            print("ZERO files indexed -- refusing (exit 2), prior index left intact", flush=True)  # wave-4 F-16: match the advertised exit 2
            con.close()
            os.remove(tmp)
            sys.exit(2)
        _report = f"index.db rebuilt: {n} files at {ts} | stat-skips disclosed: {SKIPS[0]}"
        print("canon families outside expected dirs (primary):")
        for f, d, c in cur.execute("SELECT family,dir,c FROM canon_outside ORDER BY c DESC"):
            print(f"  {c:6d}  {f:5s} in {d}")
        con.close()
        os.replace(tmp, DB)  # F1/F3 cure: publish LAST, after the report on a LIVE connection
        print(_report, flush=True)  # wave-5 W01: the promised report NOW prints (was computed, never emitted)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)  # F4 cure: no .tmp residue on failure paths
        raise

if __name__ == "__main__":
    main()
