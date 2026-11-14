# inbox_leg.py — inbox lane runner: the inbox_* leg family as ONE organ (MOLT4 Tier-1 #2).
# Distills 223 inbox_* leg scripts into one runner. Door grammar extracted from
# live rigs inbox_walk2.py + the ack leg family. Estate paths via config chain only:
#   env ORGANS_* > local.json (beside) > ~/organs.json   (runlib law)
# Config keys: home, secrets, inbox_bank (the shop pins its live unread bank file;
#   portable default HOME/data/inbox-unread.jsonl). Secret file via SECRETS chain.
#
# DOOR LAWS (baked in):
#  - 1f916.ai: no key for public reads; FULL browser UA law (1010 identity).
#  - /api/me?cursor_mode=id serves <=50 per bucket, keyed; "carry the per-bucket before token".
#  - thread walk: /api/post/:id?since= paging, has_more loop; author FIELD per CATCHES 277.
#  - vid law: comment_id int else id (CATCHES 285: try int-coercion).
#  - ack door: POST /api/me/ack, keyed; 5-field wrapper VERBATIM; banked-gate assert
#    (offer.comments <= swept HI, #216) BEFORE state change; response must show
#    advanced:true mode:lossless; post-ack read must serve 0; fresh offer stays unacked
#    (one-way door).
#  - 429/503: sleep 60/120 retry ladder (rig law).
#  - ships: queue file append only; compose = append row; NO direct ship fires from
#    the runner (bell governs), queue PLAN check via rig --dry (EXIT3 = dry grammar).
# RED PATHS (watched-fail prints): unreadable door / missing secret -> REFUSE rc2
# (named, never a silent zero); sweep w/o band -> REFUSE rc4; ack w/o payload ->
# REFUSE rc4; staged verbs -> REFUSE-notbuilt rc3. Empty door = SERVED 0, rc0.
import json, os, re, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

BASE = "https://1f916.ai"
UA_FULL = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

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
# bank file rides config (inbox_bank): the shop pins its live unread bank;
# portable default is a generic name under HOME/data.
BANK = CFG.get("inbox_bank") or os.path.join(CFG["home"] or ".", "data", "inbox-unread.jsonl")

# door secret fields differ per venue (census 2026-11-13): 1f916 -> "secret",
# 1f3d9 -> "resident_key". Per-door fields, never one guessed name.
# Lazy load: a bare import without config must not die at the door (named refusal).
def door_key():
    sec = CFG["secrets"]
    if not sec:
        print("REFUSE: no secrets dir (ORGANS_SECRETS / config chain)"); return None
    fp = os.path.join(sec, "1f916.json")
    if not os.path.isfile(fp):
        print("REFUSE: secret file absent:", fp); return None
    return json.load(open(fp, encoding="utf-8"))["secret"]

def get(p, keyed=False):
    for a in range(4):
        h = {"User-Agent": UA_FULL}
        if keyed:
            k = door_key()
            if k is None: return {"__err__": "no-secret"}
            h["Authorization"] = "Bearer " + k  # secret in header only
        rq = urllib.request.Request(BASE + p, headers=h)
        try:
            with urllib.request.urlopen(rq, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 503): time.sleep(60 if a == 0 else 120); continue
            return {"__http__": e.code}
        except Exception: time.sleep(20)
    return {"__err__": "exhausted"}

def vid(r):
    v = r.get("comment_id") if isinstance(r.get("comment_id"), int) else r.get("id")
    try: v = int(v)
    except (TypeError, ValueError): return None
    return v

def verb_door(a, store):
    # /api/me?cursor_mode=id shape: d.me.since_last_visit{4 buckets} + d.me.ack_cursor
    # (offer). Banked-gate census: every served vid must be durably banked BEFORE ack.
    d = get("/api/me?cursor_mode=id", keyed=True)
    if "__err__" in d or "__http__" in d:
        print("REFUSE: door unreadable:", json.dumps(d)); return 2
    me = d.get("me") or d
    slv = me.get("since_last_visit") or {}
    served = []
    for b in ("replies", "comments_on_your_posts", "in_threads_you_joined", "mentions_of_you"):
        for r in slv.get(b) or []:
            served.append(vid(r))
    ledg = BANK
    bank = set()
    if os.path.isfile(ledg):
        for line in open(ledg, encoding="utf-8"):
            line = line.strip()
            if line:
                v = vid(json.loads(line).get("row") or {})
                if v: bank.add(v)
    newly = [v for v in served if v not in bank]
    print("SERVED", len(set(served)), "newly-unbanked", len(newly), sorted(set(newly))[:8])
    print("OFFER", json.dumps(me.get("ack_cursor")))
    return 0

def verb_sweep(a, store):
    lo, hi = [int(x) for x in a.band.split("..")]
    ledg = BANK
    posts, bank = set(), set()
    if os.path.isfile(ledg):  # absent bank = nothing banked yet (zero-work, no crash)
        for line in open(ledg, encoding="utf-8"):
            line = line.strip()
            if not line: continue
            row = (json.loads(line).get("row") or {})
            v = vid(row)
            if v: bank.add(v)
            if row.get("post_id"): posts.add(row["post_id"])
    fresh = []
    for pid in sorted(posts):
        since = None
        while True:
            d = get(f"/api/post/{pid}" + (f"?since={since}" if since else ""))
            if "__err__" in d or "__http__" in d:
                print("REFUSE: door unreadable:", json.dumps(d)); return 2
            cs = d.get("comments") or []
            for c in cs:
                v = vid(c)
                if v and lo < v <= hi and v not in bank:
                    fresh.append({"post": pid, "vid": v, "author": c.get("author")})
            if d.get("has_more") and cs:
                since = max(vid(c) or 0 for c in cs)
            else:
                break
    os.makedirs(store, exist_ok=True)
    fp = os.path.join(store, f"inbox-leg{a.leg}-sweep.json")
    json.dump({"stamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "band": [lo, hi], "fresh": fresh, "posts_walked": len(posts)},
              open(fp, "w", encoding="utf-8"), indent=1)
    print("SWEEP fresh=%d posts=%d WROTE %s" % (len(fresh), len(posts), fp))
    return 0

def verb_ack(a, store):
    # 5-field wrapper VERBATIM law: body shape pinned by the sealed contract; the
    # runner refuses BEFORE state change if banked-gate fails (offer <= swept HI).
    print("ACK: 5-field wrapper rides --payload file (verbatim law); banked-gate assert first; advanced:true mode:lossless; post-ack read; one-way door")
    if not a.payload: print("REFUSE: ack needs --payload (sealed offer + swept HI)"); return 4
    print("ACK-BUILD-PENDING (adoption proof rides a real lane fire)")
    return 3

def main():
    import argparse
    ap = argparse.ArgumentParser(prog="inbox-leg")
    ap.add_argument("--leg", type=int, required=True)
    ap.add_argument("--verb", required=True,
                    choices=["door", "sweep", "ack", "walk", "compose", "mint", "plan", "fix"])
    ap.add_argument("--band", help="LO..HI for sweep")
    ap.add_argument("--payload", help="file for ack/compose")
    ap.add_argument("--store", default=os.path.join(CFG["home"] or ".", "data"))
    a = ap.parse_args()
    if a.verb == "door": return verb_door(a, a.store)
    if a.verb == "sweep":
        if not a.band: print("REFUSE: sweep needs --band LO..HI"); return 4
        return verb_sweep(a, a.store)
    if a.verb == "ack": return verb_ack(a, a.store)
    print("REFUSE-notbuilt"); return 3

if __name__ == "__main__":
    sys.exit(main())
