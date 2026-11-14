# twin_sync.py -- md5 census of named rig twins across execution dirs (CATCHES 301 cure organ).
# Law: a rig fix must land on ALL execution copies (shop scripts, hermes scripts, organs repo).
# Green = every rig whose copies exist are byte-identical (md5-unique set per rig). Red = named drift.
# Config chain (same as every organ): env ORGANS_TWIN_MANIFEST > local.json beside > ~/organs.json,
# keys: "twin_rigs" (list of file names), "twin_dirs" (list of dirs to compare). Inert = disclosed skip.
import sys, os, json, hashlib

def _cfg():
    for p in (os.environ.get("ORGANS_TWIN_MANIFEST"),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"),
              os.path.expanduser("~/organs.json")):
        if p and os.path.exists(p):
            try:
                d = json.load(open(p, encoding="utf-8"))
                if d.get("twin_rigs") and d.get("twin_dirs"):
                    return d["twin_rigs"], d["twin_dirs"], p
            except Exception:
                pass
    return None, None, None

def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()[:8]

def main(argv):
    rigs, dirs, src = _cfg()
    if not rigs:
        print("TWIN-SYNC INERT (advisory): twin_rigs/twin_dirs not configured (config chain: env > local.json > ~/organs.json)")
        return 0
    drift = 0
    checked = 0
    for rig in rigs:
        seen = {}
        for d in dirs:
            p = os.path.join(d, rig)
            if os.path.exists(p):
                seen[d] = md5(p)
        if not seen:
            print(f"  SKIP(absent-all) {rig}")
            continue
        checked += 1
        if len(set(seen.values())) > 1:
            drift += 1
            print(f"  DRIFT {rig}: " + " | ".join(f"{k}={v}" for k, v in seen.items()))
    print(f"TWIN-SYNC: rigs={checked} dirs={len(dirs)} drift={drift} manifest={src}")
    return 1 if drift else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
