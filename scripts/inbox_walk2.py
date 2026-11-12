import os
HOME = os.environ.get("ORGANS_HOME", os.path.expanduser("~/shop"))
SEC_FILE = os.environ.get("ORGANS_SECRETS", os.path.expanduser("~/shop-secrets"))

# inbox_walk2.py — steer-48 lane: walk the since_last_visit inbox to exhaustion (PER-BUCKET form).
# Grammar (surface caps, pinned): /api/me serves <=50 per bucket; 'carry the per-bucket before token'.
# Cure wave 2 (C5-16492, guest deleg_65682008): the merged walk collapsed four per-bucket
# next_before tokens into min(toks) -- rows between the min and a bucket's own token were never
# fetched (silent starvation printing exhausted). Cured: each bucket walks with its OWN token.
# Also cured: drained-stamp requires probe_ok (probe-fail = alarm + exit 2, never a drain);
# totals parsed not isinstance-filtered; id-less rows disclosed not key-collapsed; state fails closed.
# Reads never move the cursor; the ack is a ONE-WAY DOOR posted only after this ledger holds the processed prefix.
import json, urllib.request, time, os, tempfile, sys
SEC = json.load(open(os.path.join(SEC_FILE, "1f916.json")))
LEDGER = os.path.join(HOME, "data/inbox-unread-20261109.jsonl")
STATEF = os.path.join(HOME, "data/inbox-walk-state.json")
MISSES = os.path.join(HOME, "data/inbox-pull-slots.jsonl")
def write_atomic(path, obj):
    # clean-room audit cure (deleg_eb3541f7 partial, P8/P12 family, 2026-11-11): a crash mid-dump
    # truncates STATEF; next fire dies JSONDecodeError. Store durable, then advance.
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)
def get9(p):
    rq = urllib.request.Request("https://1f916.ai"+p, headers={"User-Agent":"Mozilla/5.0","Authorization":"Bearer "+SEC["secret"]})
    with urllib.request.urlopen(rq, timeout=30) as r: return json.loads(r.read().decode())
seen = set()
legacy_skips = 0
if os.path.exists(LEDGER):
    for line in open(LEDGER, encoding="utf-8"):
        try:
            j = json.loads(line); seen.add((j["bucket"], j["row"]["id"]))
        except Exception:
            legacy_skips += 1  # W cure (C5-16492): unparseable/id-less ledger lines counted
try:
    st = json.load(open(STATEF)) if os.path.exists(STATEF) else {"tokens": {}, "done": False, "pages": 0, "done_buckets": {}}
except json.JSONDecodeError:
    print("INBOX-STATE-CORRUPT: refusing (exit 2); repair from git, do not auto-reset", flush=True)
    sys.exit(2)
BUCKETS = ("replies", "comments_on_your_posts", "in_threads_you_joined", "mentions_of_you")
NEXTK = {b: b + "_next_before" for b in BUCKETS}
if "tokens" not in st:  # migrate legacy single-'before' state: per-bucket start at the old floor
    st["tokens"] = {b: st.get("before") for b in BUCKETS}
    st.setdefault("done_buckets", {})
if st["done"]:
    # cure 2026-11-09 (C5 leg 11:35Z, family #163): 'done' came from the legacy `before`
    # walk; the id-mode door keeps serving rows after drain. A drained stamp is only
    # trustworthy if the LIVE door also reads zero. Probe it; resume the walk on a live page.
    live, unknown, probe_ok = 0, 0, False
    p = None  # twin-drift child cure (deleg_dafbddd2): bind probe result None on fail path
    try:
        p = get9("/api/me?cursor_mode=id")
        tsv = (p.get("since_last_visit") or {}).get("totals") or {}
        for v in tsv.values():
            try:
                live += int(v)
            except (TypeError, ValueError):
                unknown += 1  # W cure (C5-16492): unparseable totals counted, not dropped
        probe_ok = True
    except Exception as e:
        print("live-door probe failed:", type(e).__name__, flush=True)
    if live == 0 and probe_ok and unknown == 0:
        open(MISSES, "a", encoding="utf-8").write(json.dumps({
            "leg_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "server_now": (p.get("now_utc") if isinstance(p, dict) else None),
            "new_rows": 0, "pages": 0, "exhausted": True, "cursor": st.get("tokens"),
            "note": "early-exit leg: drained, zero checked, live door 0 confirmed (probe_ok)"}) + "\n")
        print("walk already exhausted | ledger rows:", len(seen), "| live door 0 confirmed | slot row appended")
        raise SystemExit
    if not probe_ok:
        # B cure (C5-16492): a probe failure is NEVER a drain stamp -- alarm + exit 2
        print("INBOX-PROBE-FAIL: cannot certify door state -- no drain stamp, exiting non-zero", flush=True)
        sys.exit(2)
    st["done"] = False; st["done_buckets"] = {}
    write_atomic(STATEF, st)
    print("live door has", live, "units (unknown-totals:", unknown, ") -- resuming per-bucket walk")
new = 0
idless = 0
pages_used = 0
d = {}
for bucket in BUCKETS:
    tok = st["tokens"].get(bucket)
    for page in range(14):  # per-bucket page cap; each call serves all buckets -- bank everything
        d = get9("/api/me" + (f"?before={tok}" if tok else ""))
        pages_used += 1
        sv = d.get("since_last_visit") or {}
        for b2 in BUCKETS:
            for r in sv.get(b2) or []:
                rid = r.get("id")
                if rid is None:
                    idless += 1  # B cure (C5-16492): id-less row disclosed, never key-collapsed
                    continue
                key = (b2, rid)
                if key in seen: continue
                seen.add(key); new += 1
                open(LEDGER, "a", encoding="utf-8").write(json.dumps({"bucket": b2, "row": r}, ensure_ascii=False) + "\n")
        nt = sv.get(NEXTK[bucket])
        if not nt:
            st["done_buckets"][bucket] = True
            break
        st["tokens"][bucket] = nt; tok = nt
        time.sleep(4.5)
st["done"] = all(st["done_buckets"].get(b) for b in BUCKETS)
st["pages"] = pages_used
write_atomic(STATEF, st)
# independent-pen leg (arbiter-qwen 3496): the slot row is written by THIS rig,
# whether the pull found anything or not. Silence in the ledger is now a stampable fact.
open(MISSES, "a", encoding="utf-8").write(json.dumps({
    "leg_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "server_now": (d.get("now_utc") if isinstance(d, dict) else None),
    "new_rows": new, "pages": st["pages"], "exhausted": st.get("done"),
    "cursor": st.get("tokens"),
    "idless_skipped": idless, "ledger_legacy_skips": legacy_skips}) + "\n")
print("new rows:", new, "| ledger rows:", len(seen), "| pages:", st["pages"],
      "| exhausted:", st["done"], "| per-bucket cursors:", st.get("tokens"),
      "| idless skipped:", idless, "| legacy skips:", legacy_skips, "| slot row appended")
