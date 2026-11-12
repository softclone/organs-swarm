
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
"""scripts/molt/pointers.py - build pointers.json: file-number -> current-path map for the shop.
The audit/build rigs construct paths as f"POLES/pole-{N}.md"; this file lets them resolve N
to the post-molt location. Regenerate after every molt batch: python index/build_index.py
then python scripts/molt/pointers.py
"""
import os, re, json, sqlite3, sys

SHOP = os.environ.get("ORGANS_SHOP_DIR", os.path.join(HOME, "shop"))
DB = os.path.join(SHOP, "index", "index.db")
OUT = os.path.join(SHOP, "index", "pointers.json")

FAMS = [
    (r"^eros-(\d+)\.md$", "eros", "eros"),
    (r"^taste-(\d+)\.md$", "taste", "eros-taste-notes"),
    (r"^medit-(\d+)\.md$", "medit", "MEDITATION"),
    (r"^diary-(\d+)\.md$", "diary", "journal-core"),
    (r"^journal-note-(\d+)\.md$", "board", "journal-note"),
    (r"^pole-(\d+)\.md$", "pole", "pole"),
    (r"^scene-(\d+)\.md$", "scene", "weekly-scene"),
    (r"^dream-(\d+)\.md$", "dream", "dream"),
]

def main():
    # B2 cure (C5-16484): sqlite CREATES a missing DB; a mid-rebuild kill used to yield
    # an empty pointers.json at exit 0. Fail closed: exists-check + ro URI + zero-rows refuse.
    if not os.path.exists(DB):
        print("index.db MISSING -- run index/build_index.py first; refusing (exit 1)", flush=True)
        sys.exit(1)
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute("SELECT root, path, name, family FROM files WHERE root='primary'").fetchall()
    con.close()
    if not rows:
        print("ZERO rows in index.db -- refusing (exit 1)", flush=True)
        sys.exit(1)
    idx = {}
    for root, path, name, family in rows:
        for pat, fam, alias in FAMS:
            m = re.match(pat, name)
            if not m:
                continue
            n = int(m.group(1))
            rel = os.path.relpath(path, SHOP).replace("\\", "/")
            key = f"{fam}:{n}"
            rec = idx.setdefault(key, {"paths": [], "citations": {}})
            rec["paths"].append(rel)
            # citation numbers the ledgers actually use for this file
            if fam == "diary":
                cite = n - 1000 if n >= 1000 else n
                rec["citations"][f"journal-core-{cite}"] = rel
                if n < 1000:
                    rec["citations"][f"journal-{n}"] = rel
            elif fam == "taste":
                rec["citations"][f"eros-taste-notes-{n}"] = rel
            elif fam == "medit":
                rec["citations"][f"MEDITATION-{n}"] = rel
            else:
                rec["citations"][f"{alias}-{n}"] = rel
    # B3 cure (C5-16484): tmp + fsync + replace -- a crash mid-dump used to leave a torn
    # pointers.json for every json.load reader, handle unclosed
    tmp = OUT + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(idx, fh, indent=1, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, OUT)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)  # F5 cure (C5-16486): no .tmp residue on failure
        raise
    print("pointers.json entries:", len(idx), "| paths indexed:", sum(len(v["paths"]) for v in idx.values()))

if __name__ == "__main__":
    main()
