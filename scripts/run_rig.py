# run_rig.py — registry dispatcher: the _run_<rig><n> one-shot wrapper family as
# ONE organ (MOLT4 Tier-1 #4). Collapses 74 wrappers (6-78L each: ts_now + runlib
# door call + inline payload) into one registry dispatcher. The per-n copies
# retire to archive/oneoffs; n rides as --n. Anatomy source: a 12L live-head wrapper.
# Config chain (runlib law): env ORGANS_* > local.json (beside) > repo-root
# local.json > ~/organs.json; keys: home, secrets.
# REGISTRY = SHOP config, never shipped (this repo ships zero venue data): point
# ORGANS_RIGS at the shop registry, or keep rigs.json at HOME/scripts/rigs.json.
# REGISTRY SEED (documented example — write this beside YOUR shop rigs):
#   {
#     "w": {"door": "say",
#           "args": {"place_id": 1367, "mode": "line", "body": "N"}}
#   }
# Shape: name -> {door, args template}; more rigs follow the same shape.
# Uppercase N in args is replaced by --n; --payload file content rides as
# args["body"]. Default is PLAN (no door touch); --fire executes through the
# packaged runlib venue door.
# RED PATHS (watched-fail prints): registry absent -> NO-REGISTRY rc4; unknown
# rig name -> REFUSE rc5 (known names printed); plan prints RIG line + rc0.
import json, os, sys

def cfg():
    # config chain: env > local.json (beside) > repo-root local.json > ~/organs.json
    c = {}
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(here, "local.json"),
              os.path.join(os.path.dirname(here), "local.json"),
              os.path.expanduser("~/organs.json")):
        if os.path.isfile(p):
            for k, v in json.load(open(p, encoding="utf-8")).items():
                c.setdefault(k, v)
    c["home"] = os.environ.get("ORGANS_HOME") or c.get("home")
    c["secrets"] = os.environ.get("ORGANS_SECRETS") or c.get("secrets")
    return c

CFG = cfg()
REG_PATH = os.environ.get("ORGANS_RIGS") or (
    os.path.join(CFG["home"], "scripts", "rigs.json") if CFG.get("home") else None)

def main():
    import argparse
    ap = argparse.ArgumentParser(prog="run-rig")
    ap.add_argument("--rig", required=True, help="registry name (w/g/sweep/tools/...)")
    ap.add_argument("--n", type=int)
    ap.add_argument("--payload", help="data file for payload-driven rigs")
    ap.add_argument("--fire", action="store_true", help="execute (default: plan)")
    a = ap.parse_args()
    if not REG_PATH or not os.path.isfile(REG_PATH):
        print("NO-REGISTRY:", REG_PATH, "-- registry is SHOP config; write it beside rigs")
        return 4
    reg = json.load(open(REG_PATH, encoding="utf-8"))
    if a.rig not in reg:
        print("REFUSE: rig", a.rig, "not in registry (known:", sorted(reg)[:12], "...)"); return 5
    spec = reg[a.rig]
    args = dict(spec.get("args", {}))
    if a.n is not None:
        args = json.loads(json.dumps(args).replace("N", str(a.n)))
    if a.payload:
        args["body"] = open(a.payload, encoding="utf-8").read()
    print(f"RIG {a.rig} door={spec['door']} args={json.dumps(args)[:160]} fire={a.fire}")
    if not a.fire:
        print("RUN-RIG-DONE (plan)"); return 0
    sys.path.insert(0, os.path.join(CFG["home"], "scripts"))
    from runlib import venue, ts_now  # packaged door
    print("ts:", ts_now())
    out = venue(spec["door"], args)
    print("OUT:", json.dumps(out, ensure_ascii=False)[:300])
    return 0

if __name__ == "__main__":
    sys.exit(main())
