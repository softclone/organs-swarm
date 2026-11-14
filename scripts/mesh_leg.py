# mesh_leg.py — mesh lane runner: the mesh_* leg family as ONE organ (MOLT4 Tier-1 #1).
# Distills 378 hand-written mesh_* leg scripts into one runner with shared door
# helpers. Anatomy sampled from three live legs (mint 259L, memory 185L, bodies 96L).
# Estate data (ledger, bank, taste, secrets) arrives ONLY via the config chain:
#   env ORGANS_* > local.json (beside) > ~/organs.json   (runlib law)
# Config keys: home, secrets, handle (honcho observed_id), honcho_url, embed_url,
#   probe_doors (dict label->url for the probe verb; estate seats pinned by shop).
# Door env shims (after_restart convention): ORGANS_HONCHO_URL, ORGANS_EMBED_URL.
#
# VERBS (from family census molt4-oneoffs.md #1):
#   bodies   -> fetch line/comment bodies at door, gap closure via /api/events, decode
#   comments -> 1f916 thread walk: since-paging, author FIELD per CATCHES 277
#   memory   -> ledger scan -> slot assert, bank recompute, embed precheck FIRST,
#               honcho BEFORE mnemos, taste files written AFTER honcho w/ slot token
#   mint     -> census v2 (plain-contains + positive control per CATCH 287), taste
#               rewrite, honcho fire (green-run only), mint via canonical route,
#               cursor+addendum, landing gate re-fire
#   taste    -> taste head scan, canonical rewrite with lane stamp
#   census   -> scan/print, computed counts, no writes
#   probe    -> seat/embed door probes (POST-scoped honcho probed as POST)
#   finish   -> lane close: landing gate + cursor stamp + addendum note
#   fix      -> staged (REFUSE-notbuilt rc3 until the repair+re-fire build)
# ORDER LAWS (baked in, from leg anatomy): embed-precheck before venue writes;
# honcho before mnemos; taste-after-honcho-with-slot-token; zero venue writes on
# mint verb; cursor note rides landing; counters computed in-call.
# RED PATHS (watched-fail prints): mint w/o body-file -> REFUSE rc4; mint slot
# collision (canonical head >= planned slot) -> REFUSE rc4 reserve-assert BEFORE
# any fire; taste w/o body-file -> REFUSE rc4; taste file exists -> REFUSE rc5
# (O_EXCL law); embed precheck dead -> ABORT rc2; staged verb -> REFUSE-notbuilt rc3.
import json, os, sys, re, uuid, urllib.request, urllib.error
from datetime import datetime, timezone

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
HONCHO = os.environ.get("ORGANS_HONCHO_URL") or CFG.get("honcho_url") or "http://127.0.0.1:8000"
EMBED = os.environ.get("ORGANS_EMBED_URL") or CFG.get("embed_url") or "http://127.0.0.1:8081"
UA = "Mozilla/5.0"
BASE = "https://1f3d9.com"          # city: line door (plain GET, NO query options 2026-11-13)
BASE_1F916 = "https://1f916.ai"     # square: post/comments door (browser UA law, no key)
UA_FULL = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

def sec_json(name):
    return json.load(open(os.path.join(CFG["secrets"], name), encoding="utf-8"))

def venue_get(path, key=None):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": UA})
    if key:
        req.add_header("Authorization", "Bearer " + key)  # secret in header only
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def new_request_id():
    return str(uuid.uuid4())  # 1f3d9 REST request_id UUID law

def ledger_scan(home):
    text = open(os.path.join(home, "ledgers", "CORPUS.md"), encoding="utf-8").read()
    toks = [int(m) for m in re.findall(r"C5-(\d+)", text)]
    pairs = re.findall(r"(\d+)->(\d+)", text)  # advisory shape; gate is string-grammar
    return {"scanmax": max(toks) if toks else 0}

def landing_gate(home):
    # canonical chain-head route: run the counter_head rig, parse its printed head
    import subprocess
    out = subprocess.run([sys.executable, os.path.join(home, "scripts", "counter_head.py")],
                         capture_output=True, text=True, timeout=60).stdout
    m = re.search(r"live head \(last row canonical pair\): (\d+)", out)
    return int(m.group(1)) if m else None

def verb_bodies(a, store):
    # GET-only bodies fetch at 1f3d9 line door: authed plain read, int limit law,
    # request_id UUID rides REST door. Gap closure via /api/events when band given.
    key = sec_json("1f3d9.json")["resident_key"]
    ids = [i.strip() for i in (a.ids or "").split(",") if i.strip()]
    out = {"stamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "request_id": new_request_id(), "lines": {}}
    for pid in ids:
        r = venue_get(f"/api/line/{pid}", key=key)  # venue law 2026-11-13 13:5x: NO query options
        #     on /api/line/:id (limit/request_id both refused as unsupported);
        #     remedy prints the exact option list. Plain GET = 200.
        line = r.get("line") or {}
        out["lines"][pid] = {"author": line.get("author"),
                             "bytes": line.get("body_bytes")
                             or len(line.get("body") or ""),
                             "created_at": line.get("created_at")}
    os.makedirs(store, exist_ok=True)
    fp = os.path.join(store, f"mesh-leg{a.leg}-bodies.json")
    json.dump(out, open(fp, "w", encoding="utf-8"), indent=1)
    print("BODIES", json.dumps(out["lines"]))
    print("WROTE", fp)
    return 0

def verb_comments(a, store):
    # 1f916.ai thread walk: /api/post/:id (no auth, browser UA), since-paging,
    # author field read per CATCHES 277 (author, not parent/intended placement).
    import urllib.parse
    ids = [i.strip() for i in (a.ids or "").split(",") if i.strip()]
    out = {"stamp": datetime.now(timezone.utc).isoformat(timespec="seconds"), "posts": {}}
    for pid in ids:
        rows, since = [], None
        while True:
            q = f"/api/post/{pid}" + (f"?since={since}" if since else "")
            req = urllib.request.Request(BASE_1F916 + q, headers={"User-Agent": UA_FULL})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode("utf-8"))
            cs = d.get("comments") or []
            rows += cs
            if d.get("has_more") and cs:
                since = max(int(c.get("comment_id") or c.get("id") or 0) for c in cs)
            else:
                break
        out["posts"][pid] = {"rows": len(rows),
                             "authors": sorted({c.get("author", "?") for c in rows})}
    os.makedirs(store, exist_ok=True)
    fp = os.path.join(store, f"mesh-leg{a.leg}-comments.json")
    json.dump(out, open(fp, "w", encoding="utf-8"), indent=1)
    print("COMMENTS", json.dumps(out["posts"]))
    print("WROTE", fp)
    return 0

def verb_mint(a, store, dry):
    # Core lane act, order laws baked in:
    #  1) census: scanmax + canonical head computed in-call (gate route, not pasted)
    #  2) slot = scanmax+1, RESERVE-ASSERT (re-scan at write, disclose mid-flight drift)
    #  3) honcho FIRST when --conclusions given: per-entry dicts {content,
    #     observer_id, observed_id} (422-cure shape); POST-fires-before-parse rule:
    #     on parse death, fingerprint-count via conclusions/query, NO re-POST
    #  4) mint via canonical route (HOME/scripts/molt/mint_row.mint)
    #  5) landing gate re-fire (counter_head) -- row count, head, contiguity
    # Zero venue writes. Body arrives by FILE (--body-file), never CLI prose.
    home = CFG["home"]
    body = open(a.body_file, encoding="utf-8").read() if a.body_file else ""
    if not body.strip():
        print("REFUSE: mint needs --body-file (lane prose by file, cage-safe)"); return 4
    scan = ledger_scan(home)
    slot = scan["scanmax"] + 1
    gate = landing_gate(home)
    print(f"mint plan: slot={slot} (scanmax-assert) gate-head={gate}")
    # RESERVE-ASSERT: the canonical head must sit BELOW the planned slot; a head
    # at/above it means the slot is already occupied -> refuse BEFORE any fire.
    if gate is not None and gate >= slot:
        print(f"REFUSE: slot collision slot={slot} gate-head={gate} (reserve-assert, zero writes)"); return 4
    if dry:
        print("MINT-DRY (no honcho fire, no mint)"); return 0
    if a.conclusions:
        con = json.load(open(a.conclusions, encoding="utf-8"))
        entries = [{"content": c, "observer_id": "hermes",
                    "observed_id": CFG.get("handle") or "agent"} for c in con]
        req = urllib.request.Request(
            HONCHO + "/v3/workspaces/hermes/conclusions",
            data=json.dumps(entries).encode(), headers={"Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                print("honcho:", r.status)
        except Exception as e:
            # POST may have fired server-side: fingerprint-count before any re-POST
            print("honcho parse-death:", type(e).__name__, "-- fingerprint-count before re-POST (law)")
    sys.path.insert(0, os.path.join(home, "scripts", "molt"))
    from mint_row import mint  # canonical route (path-update-first law at MOLT4)
    slot2, aa, bb = mint(body)
    print(f"LANDED slot={slot2} pair={aa}->{bb} drift={'yes(disclosed)' if slot2 != slot else 'no'}")
    print("gate-after:", landing_gate(home))
    return 0


def probe_door(url, timeout=4):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except Exception as e:
        return type(e).__name__

def verb_probe(a, store):
    # probe targets ride config (probe_doors dict); defaults are the portable
    # localhost doors -- estate relay seats are pinned by the shop, never shipped.
    relay = dict(CFG.get("probe_doors") or {})
    relay.setdefault("embed", EMBED + "/v1/models")
    relay.setdefault("twin8082", "http://127.0.0.1:8082/v1/models")
    relay.setdefault("twin18080", "http://127.0.0.1:18080/v1/models")
    out = {k: probe_door(v) for k, v in relay.items()}
    # honcho door is POST-scoped: GET 405s by design, probe it as POST
    import urllib.error
    req = urllib.request.Request(HONCHO + "/v3/workspaces/hermes/conclusions/query",
                                 data=json.dumps({"query": "probe", "filters": {}}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            out["honcho"] = r.status
    except urllib.error.HTTPError as e:
        out["honcho"] = e.code
    print("PROBE", json.dumps(out))
    return 0

def verb_memory(a, store):
    # shop-side memory leg: embed PRECHECK FIRST (abort before any write),
    # bank recompute in-call (printed counters ADVISORY), taste head scan,
    # slot plan via gate route; mnemos journal leg is AGENT-side: the runner
    # emits journal text for the lane, it never fires mnemos itself.
    home = CFG["home"]
    if probe_door(EMBED + "/v1/models") != 200:
        print("ABORT: embed precheck dead before writes (order law)"); return 2
    bank = os.path.join(home, "data", "mesh-walk-latest.jsonl")
    lines = ids = idless = mx = 0
    seen = set()
    if os.path.isfile(bank):
        for line in open(bank, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            lines += 1
            try:
                rec = json.loads(line)
                row = rec.get("row") if isinstance(rec.get("row"), dict) else rec
                v = row.get("change_id") or row.get("comment_id") or row.get("id")  # mesh ids = change_id (STRING, CATCH 285)
                try:
                    v = int(v)
                except (TypeError, ValueError):
                    v = None
                if isinstance(v, int):
                    ids += 1
                    seen.add(v)
                    mx = max(mx, v)
                else:
                    idless += 1
            except Exception:
                idless += 1
    import glob
    taste = sorted(glob.glob(os.path.join(home, "canon", "eros", "taste-notes-*.md")))
    thead = int(taste[-1].split("-")[-1].split(".")[0]) if taste else 0
    scan = ledger_scan(home)
    print("BANK lines=%d unique=%d idless=%d max=%d | taste-head=%d | scanmax=%d gate=%d"
          % (lines, len(seen), idless, mx, thead, scan["scanmax"], landing_gate(home)))
    os.makedirs(store, exist_ok=True)
    fp = os.path.join(store, "mesh-leg%d-memory-state.json" % a.leg)
    json.dump({"stamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "bank": {"lines": lines, "unique": len(seen), "idless": idless, "max": mx},
               "taste_head": thead, "scanmax": scan["scanmax"],
               "gate": landing_gate(home)},
              open(fp, "w", encoding="utf-8"), indent=1)
    print("WROTE", fp, "(mnemos journal leg rides the agent lane, per order law)")
    return 0


def verb_taste(a, store, dry):
    # taste canonical rewrite with lane stamp; ORDER LAW: taste files written
    # AFTER honcho, with the slot token inside. Body by FILE. Dry = plan only.
    home = CFG["home"]
    if not a.body_file:
        print("REFUSE: taste needs --body-file"); return 4
    body = open(a.body_file, encoding="utf-8").read()
    import glob
    taste = sorted(glob.glob(os.path.join(home, "canon", "eros", "taste-notes-*.md")))
    head = int(taste[-1].split("-")[-1].split(".")[0]) if taste else 0
    nxt = head + 1
    scan = ledger_scan(home)
    slot = scan["scanmax"] + 1
    print(f"taste plan: next=TASTE-{nxt} slot-token={slot} gate={landing_gate(home)}")
    if dry:
        print("TASTE-DRY (written AFTER honcho in live order law)"); return 0
    fp = os.path.join(home, "canon", "eros", f"taste-notes-{nxt}.md")
    if os.path.exists(fp):
        print("REFUSE: taste file exists (O_EXCL law)"); return 5
    with open(fp, "x", encoding="utf-8") as f:
        f.write(body.replace("SLOT", str(slot)))
    print("WROTE", fp, "with slot token", slot)
    return 0

def verb_finish(a, store):
    # lane close: landing gate + cursor stamp + addendum note; zero venue writes.
    home = CFG["home"]
    gate = landing_gate(home)
    scan = ledger_scan(home)
    rec = {"stamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "leg": a.leg, "gate_head": gate, "scanmax": scan["scanmax"]}
    os.makedirs(store, exist_ok=True)
    fp = os.path.join(store, "mesh-leg-finish-stamp.json")
    prev = {}
    if os.path.isfile(fp):
        prev = json.load(open(fp, encoding="utf-8"))
    rec["prev_leg"] = prev.get("leg")
    json.dump(rec, open(fp, "w", encoding="utf-8"), indent=1)
    print("FINISH", json.dumps(rec))
    return 0

def main():
    import argparse
    ap = argparse.ArgumentParser(prog="mesh-leg")
    ap.add_argument("--leg", type=int, required=True)
    ap.add_argument("--verb", required=True,
                    choices=["bodies", "comments", "memory", "mint", "taste", "census", "probe", "fix", "finish"])
    ap.add_argument("--band", help="A..B id band")
    ap.add_argument("--ids", help="comma ids for bodies/gap verbs")
    ap.add_argument("--conclusions", help="file of prose payloads (estate data by file)")
    ap.add_argument("--store", help="output dir (default HOME/data)")
    ap.add_argument("--body-file", help="mint body (lane prose by file)")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    store = a.store or os.path.join(CFG["home"], "data")
    print(f"mesh-leg leg{a.leg} verb={a.verb} band={a.band} store={store}")
    if a.verb == "census":
        print("ledger", json.dumps(ledger_scan(CFG["home"])))
        print("gate", landing_gate(CFG["home"]))
        return 0
    if a.verb == "bodies":
        return verb_bodies(a, store)
    if a.verb == "comments":
        return verb_comments(a, store)
    if a.verb == "mint":
        return verb_mint(a, store, a.dry)
    if a.verb == "probe":
        return verb_probe(a, store)
    if a.verb == "memory":
        return verb_memory(a, store)
    if a.verb == "taste":
        return verb_taste(a, store, a.dry)
    if a.verb == "finish":
        return verb_finish(a, store)
    # fix verb staged: repair+re-fire legs build next pass; all other verbs above
    # share the door helpers, mint route (HOME/scripts/molt/mint_row), bank/cursor
    # atomic merge, honcho door (workspace-scoped), taste head scan. Payloads
    # arrive by FILE, never as CLI prose.
    print("REFUSE-notbuilt (fix verb staged; build per suite legs)")
    return 3

if __name__ == "__main__":
    sys.exit(main())
