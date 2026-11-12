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

#!/usr/bin/env python3
# alienface line request_id generator (steer 36: hard rule as code).
# Strict UUIDv4 shape from secrets.token_hex; the check is SEGMENT LENGTHS, never nibble indices.
# Usage: python rid_line.py            -> prints one fresh valid rid
#        python rid_line.py --check X  -> validates X, exit 0 valid / 1 invalid
import secrets, sys, uuid, re

_STRICT = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

def gen():
    # audit cure 2026-11-11 (child F, deleg_a108cd5e): stdlib uuid4 = full 122-bit independent entropy;
    # the old construction reused H[9:12] in segment 3 (correlated nibbles, ~108 bits).
    R = str(uuid.uuid4())   # lowercase, version-4, variant-8/9/a/b by construction
    assert _STRICT.match(R), "generator broke its own shape"
    return R

def valid(R):
    # audit cure: strict shape+case+version+variant (old length-only valid() accepted UPPERCASE and
    # non-hex skeletons with rc 0 -- it could not enforce the lowercase-uuid4 law)
    return bool(_STRICT.match(R))

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        # N2 cure (child deleg_238c7f9a, 2026-11-11): '--check' with NO operand fell through to gen()
        # and printed a fresh rid at exit 0 -- callers reading exit codes read 'validated OK' on a
        # usage error. A check with nothing to check is a usage error, exit 2.
        if len(sys.argv) < 3:
            print("RID: --check requires an operand"); sys.exit(2)
        ok = valid(sys.argv[2])
        print("RID:", "VALID" if ok else "INVALID", sys.argv[2])
        sys.exit(0 if ok else 1)
    print(gen())
