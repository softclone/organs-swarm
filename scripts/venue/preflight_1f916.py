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

#!/usr/bin/env python3
# 1f916 preflight organ (steer 36: hard rules live in code).
# Checks a draft body + ship intent BEFORE any POST:
#   - self-screen: secret-shape / email / ipv4 / home-path / invisible unicode / ANSI
#   - quota: venue's own print (GET /api/me with the stored secret; counts shown, never hard-coded)
#   - ship-once gate: receipts store lookup by gid
# Usage: python preflight_1f916.py <body_file> [gid]
# Verdict is a REPORT + exit code; the shipper consumes the gate.
import sys, os, re, json, urllib.request

SECRET_FILE = os.path.join(SEC_FILE, "1f916.json")
RECEIPTS = os.path.join(HOME, "data/venue-replies-receipts-20261108.jsonl")

SCREENS = [
    ("email", re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')),
    ("ipv4", re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b')),
    # Wave 2 cure (preflight live-fire 2026-11-11): 'https://...' matched as drive-letter path via
    # 's://'. Lookbehind: a drive letter may not be preceded by a letter (kills scheme collision,
    # keeps real home paths).
    ("home-path", re.compile(r'(?<![A-Za-z])[A-Za-z]:[\\/][\w\\/. -]{4,}|/c/Users/[\w-]+/', re.I)),
    ("bearer-secret", re.compile(r'(Bearer\s+[A-Za-z0-9_\-]{12,})|sk-[A-Za-z0-9]{16,}')),
    # Wave 2 nit cure (C5-16492): unprefixed long tokens (raw secret pastes) were unscreened.
    # Known trade: 64-char sha256 pin quotes in bodies fire this screen; the consented path is
    # hygiene-override (disclosed), per the W5 cure's rule that false positives need a named way out.
    ("long-token", re.compile(r'\b[A-Za-z0-9+/_=-]{40,}\b')),
    ("invisible-unicode", re.compile(r'[\u200b-\u200f\u202a-\u202e\ufeff]')),
    ("ansi", re.compile(r'\x1b\[')),
]

def main():
    body = open(sys.argv[1], encoding="utf-8").read()
    gid = sys.argv[2] if len(sys.argv) > 2 else None
    flags = []
    for name, pat in SCREENS:
        m = pat.search(body)
        if m: flags.append((name, repr(m.group(0))[:60]))
    n = len(body.encode("utf-16-le")) // 2   # P7 cure (deleg_4fe7c3ad): the venue cap is 8000 UTF-16 CODE UNITS --
    # emoji count double; len(chars) passed a 4500-emoji body (9000 units) as legal. Unit = the cap's unit.
    print(f"BODY: utf16_units={n} in_1_8000={1 <= n <= 8000}")
    for name, s in flags: print(f"SCREEN: {name} -> {s}")
    dup, gate_open = [], False
    corrupt = 0
    if gid and os.path.exists(RECEIPTS):
        # P3 cure: typed gid compare -- the substring matcher was shape-blind both ways
        # (string-gid rows read as fresh = fail-open; prefix collision 12-matched-123 = false ALREADY-LANDED).
        for l in open(RECEIPTS, encoding="utf-8"):
            try:
                rec = json.loads(l)
            except json.JSONDecodeError:
                # Cure wave 2 (C5-16492): a torn receipts line is NOT skippable -- its gid is
                # unknowable, so the ship-once gate cannot certify freshness. Counted, disclosed,
                # gate CLOSED. (N1 claimed 'crashes CLOSED'; the swallowed continue was fail-open.)
                corrupt += 1
                continue
            g = rec.get("gid")
            # N1 cure (child deleg_238c7f9a, 2026-11-11): try/except pass around the gid compare was
            # a fail-open SHAPE on the ship-once gate (a thrown compare skipped a dup row). No try:
            # the compare is total on JSON-native values; if it ever throws, the preflight crashes
            # CLOSED, which is exactly where a ship gate belongs.
            if g == gid or str(g) == str(gid):
                dup.append(l)
        if corrupt:
            gate_open = True
            print(f"SHIP-ONCE: {corrupt} torn receipt line(s) -- gid space unknowable, gate CLOSED (fail-closed)")
        print(f"SHIP-ONCE: gid={gid} receipts={len(dup)} -> {'ALREADY LANDED, SKIP' if dup else 'fresh'}")
    elif gid:
        # P2 cure: missing/unreadable receipts file disabled the gate SILENTLY (exit 0, no SHIP-ONCE line).
        # The ship-once gate fails CLOSED: no ledger, no pass.
        gate_open = True
        print(f"SHIP-ONCE: gid={gid} receipts UNREADABLE at {RECEIPTS} -> gate CLOSED (fail-closed)")
    quota_ok = True
    try:
        secret = json.load(open(SECRET_FILE, encoding="utf-8"))["secret"]
        req = urllib.request.Request("https://1f916.ai/api/me", headers={f"Authorization": f"Bearer {secret}"})
        me = json.load(urllib.request.urlopen(req, timeout=25))
        me = me.get("me") if isinstance(me.get("me"), dict) else me   # P5 cure: unwrap (phantom-empty class #197)
        today = me.get("today", {})
        print(f"QUOTA (venue print): today={json.dumps(today)}")
    except Exception as e:
        quota_ok = False
        print(f"QUOTA: unread ({type(e).__name__}) - door closed for the quota leg")
    # P1 + P4 cures (PROVEN: landed gid printed ALREADY LANDED then PASS exit 0; door-unread printed
    # 'treat as closed' then PASS exit 0). The ship-once verdict and a closed quota door are HARD.
    # W5 cure (child deleg_238c7f9a, 2026-11-11): the printed verdict ADVERTISED a
    # 'hygiene_override path' that did not exist in the file -- any screen regex false positive
    # (ipv4 screen vs a version string) hard-blocked a ship with no way out. The override is now
    # REAL: third argv 'hygiene-override', shop-side only, and its use prints a named line
    # (disclosure rides the receipts). ship-once / gate-open / quota-door stay NOT overridable.
    hy = len(sys.argv) > 3 and sys.argv[3] == "hygiene-override"
    # Cure wave 2 (C5-16492): the quota door being unreadable is HARD for EVERY ship leg, not
    # only gid-bearing ones -- the old form printed 'door closed' then PASS exit 0 for no-gid calls.
    hard = (not hy and flags) or (not (1 <= n <= 8000)) or bool(dup) or gate_open or (not quota_ok)
    if hy and flags:
        print("HYGIENE-OVERRIDE USED: screen flags demoted to reports by shop-side consent; line above is the disclosure leg")
    print(f"PREFLIGHT: {'BLOCK - ' + ('dup ' if dup else '') + ('gate-open ' if gate_open else '') + ('quota-door ' if not quota_ok else '') + ('cap-out ' if not (1 <= n <= 8000) else '') + ('screens' if flags and not hy else '') if hard else 'PASS'} (screen flags are {'DEMOTED by hygiene-override' if hy and flags else 'HARD-blocking: no override used; consented contact shapes: pass hygiene-override as third argv'})")
    sys.exit(1 if hard else 0)

if __name__ == "__main__":
    main()
