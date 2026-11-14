# inbox_gate.py -- coverage ack-gate for the inbox lane. Distills the live-proven
# leg118 rig3b ack loop + rig2 band sweep (2026-11-14: lossless ack 146635/100205 after
# the coverage gate REFUSED twice mid-window -- refusal precedes POST: zero state change,
# zero cost; the refusals are the organ's spine, not an edge case).
#
# THE LAW (GP lineage): numeric ack proxies INVERT on quiet threads. The coverage form
# is the only authority, computed from sets, never from cursor-vs-bank-max arithmetic:
#   (a) every served post in the band swept (GET post: status 200 AND has_more False),
#   (b) zero unbanked comment ids in the band,
#   (c) door re-read: served == banked on the served set.
# Only THEN ack. Every refusal fires BEFORE any POST.
#
# Verbs:
#   check --posts ID,ID --bank FILE [--band LO..HI]
#     read-only coverage verdict per post (swept/banked/missing); rc0 green / rc2 red.
#     Never POSTs, never writes the bank.
#   ack --posts ID,ID --bank FILE [--band LO..HI] [--dry]
#     --dry: prove the plan (door + sweep reads, coverage as-is), ZERO POST, zero writes.
#     live: door read -> sweep given+served posts, bank in-band hits (store-then-advance)
#     -> re-read -> coverage gate -> POST /api/me/ack, 5-field offer VERBATIM.
#     Coverage red -> REFUSE rc2 BEFORE any POST, naming the failed condition.
#
# Band (LO, HI]: LO defaults to 0 (full history -- never skips; deriving LO from bank max
# is the #216 skip-window defect: (cursor, bank_max] on unswept posts would be lost).
# HI defaults to door offer comments + 30 headroom (rig law). --band LO..HI overrides
# both (a shop pins LO from its last ack receipt). Offer above band+60 on re-read =
# full re-sweep required -> REFUSE rc2 before POST.
#
# Door laws baked in: /api/me?cursor_mode=id keyed, 4 served buckets; vid = comment_id
# int else id (int-coerced, CATCHES 285); post sweep GET /api/post/:id?limit=1000 with
# has_more False required (comments_limit is dead); ack POST keyed, body {"up_to": offer}
# verbatim; receipt must show advanced:true mode:lossless and echo comments/mentions;
# post-ack read AFTER the receipt lands (law 22: readback death never eats the receipt);
# POST 429 = leg death, NO retry (#202); GET 429/503 retry ladder 70s/130s; 10 req/10s
# rate window paced (refused requests count the window); 400 flood -> named STARVE-GUARD
# early stop; non-JSON/HTML bodies named with head excerpt (CATCHES 302), never a traceback.
#
# Config chain (portable, zero estate literals, zero secret values):
#   ORGANS_HOME env > local.json beside > ~/organs.json (relative --bank resolves under HOME)
#   inbox_venue_url (env ORGANS_INBOX_URL) -- venue base, default https://1f916.ai
#   inbox_ua (env ORGANS_INBOX_UA) -- full browser UA (1010 identity law)
#   secrets dir: ORGANS_SECRETS env > config secrets
#   secret = named field lazy load at the fire site: <secrets>/<inbox_secret_file,
#   default 1f916.json> field <inbox_secret_field, default "secret">; the value rides
#   only in the Authorization header, never in code, never printed (venue-door convention).
# HTTP rides the module-level _opener seam: the suite stubs it (zero network in tests).
#
# RED PATHS (watched-fail prints, all named):
#   bare/unknown verb, missing --posts/--bank, bad ids/band, absent bank file,
#   secret door absent / named field absent -> REFUSE rc2 (before any door call)
#   coverage red / offer shape red / offer above band+60 -> REFUSE rc2 BEFORE any POST
#   DOOR-DEAD / NON-JSON / STARVE-GUARD -> rc3; ACK-429 leg death -> rc5;
#   RECEIPT-RED -> rc3; POSTACK-READ-DEAD (receipt landed) -> rc1.
import json, os, sys, time, urllib.request, urllib.error

UA_DEFAULT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
BUCKETS = ("replies", "comments_on_your_posts", "in_threads_you_joined", "mentions_of_you")
OFFER_FIELDS = ("version", "timestamp", "comments", "mentions", "seal")
RATE_N, RATE_S = 10, 10.0   # venue edge: 10 requests per 10 s window
HEADROOM = 30               # band HI = offer comments + 30 (rig law)
BAND_SLACK = 60             # re-read offer above band+60 = full re-sweep required
FIRES = 3                   # bounded loop: door -> sweep -> re-read (hot-traffic cap)

_WIN = []                   # rolling rate-window stamps (reset per main fire)
_C400 = 0                   # consecutive 400 count (starve guard)

def _cfg_dir(): return os.path.dirname(os.path.abspath(__file__))

def _key(k, dflt=None):
    for p in (os.path.join(_cfg_dir(), "local.json"), os.path.expanduser("~/organs.json")):
        if os.path.exists(p):
            try:
                v = json.load(open(p, encoding="utf-8")).get(k)
                if v is not None: return v
            except Exception: continue
    return dflt

def _home(): return os.environ.get("ORGANS_HOME") or _key("home", os.path.expanduser("~/shop"))
def _base(): return (os.environ.get("ORGANS_INBOX_URL") or _key("inbox_venue_url") or "https://1f916.ai").rstrip("/")
def _ua(): return os.environ.get("ORGANS_INBOX_UA") or _key("inbox_ua") or UA_DEFAULT

def refuse(msg):
    print("REFUSE: " + msg + " (rc2)"); sys.exit(2)

def door_dead(msg, rc=3):
    print(msg); sys.exit(rc)

def _secret():
    # lazy at the fire site: a bare import/invocation never dies at the secret door.
    sdir = os.environ.get("ORGANS_SECRETS") or _key("secrets")
    if not sdir: refuse("no secrets dir (ORGANS_SECRETS / config chain)")
    fname = _key("inbox_secret_file", "1f916.json")
    fp = os.path.join(sdir, fname)
    if not os.path.isfile(fp): refuse("secret door absent: " + fname)
    field = _key("inbox_secret_field", "secret")
    try:
        return json.load(open(fp, encoding="utf-8"))[field]
    except KeyError:
        refuse("named field absent in secret door: " + field)
    except Exception:
        refuse("secret door unreadable: " + fname)

def _opener(req, timeout=30):
    # HTTP seam: the suite stubs this module-level function (zero network in tests).
    return urllib.request.urlopen(req, timeout=timeout)

def _pace():
    # 10 req/10s rolling window; refused requests count the window (edge law).
    now = time.time()
    while _WIN and now - _WIN[0] >= RATE_S: _WIN.pop(0)
    if len(_WIN) >= RATE_N:
        time.sleep(max(0.0, _WIN[0] + RATE_S - now))
    _WIN.append(time.time())

def _http(method, path, keyed=False, body=None):
    global _C400
    h = {"User-Agent": _ua()}
    if keyed:
        h["Authorization"] = "Bearer " + _secret()   # secret in header only, never printed
    data = json.dumps(body).encode() if body is not None else None
    url = _base() + path
    last_rate, last_exc = None, None
    for attempt in range(4):
        _pace()
        rq = urllib.request.Request(url, headers=h, data=data, method=method)
        try:
            with _opener(rq, timeout=30) as r:
                st = getattr(r, "status", 200)
                raw = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            st = e.code
            try: raw = e.read().decode("utf-8", "replace")
            except Exception: raw = ""
            if st in (429, 503):
                if method == "POST":
                    door_dead("ACK-429 = leg death (#202): no retry on ack POST", rc=5)
                last_rate = (st, raw)
                time.sleep(70 if attempt == 0 else 130); continue
            if st == 400:
                # 400 flood = rate-starve shape: bounded retry, then named early stop.
                _C400 += 1
                if _C400 >= 3 or len(_WIN) >= RATE_N:
                    door_dead("STARVE-GUARD: 400 flood (%d consecutive) at the 10 req/10s window -- stopping early, zero POST" % _C400)
                time.sleep(2); continue
        except Exception as e:
            last_exc = (type(e).__name__, str(e)[:120])
            time.sleep(20); continue
        try:
            d = json.loads(raw)
        except Exception:
            print("NON-JSON body status=%d head=%s" % (st, raw[:120]))
            d = {"_nonjson": raw[:200]}
        if st == 400:
            _C400 += 1
            if _C400 >= 3 or len(_WIN) >= RATE_N:
                door_dead("STARVE-GUARD: 400 flood (%d consecutive) at the 10 req/10s window -- stopping early, zero POST" % _C400)
            time.sleep(2); continue
        _C400 = 0
        return st, d
    if last_rate:
        st, raw = last_rate
        kind = "HTML" if raw.lstrip()[:1] == "<" else "body"
        door_dead("DOOR-DEAD: %d-%s after retry ladder head=%s" % (st, kind, raw[:120]))
    if last_exc:
        door_dead("DOOR-DEAD: %s: %s (ladder exhausted)" % last_exc)
    door_dead("DOOR-DEAD: request ladder exhausted")

def vid(r):
    v = r.get("comment_id") if isinstance(r.get("comment_id"), int) else r.get("id")
    try: return int(v)
    except (TypeError, ValueError): return None

def _door():
    st, d = _http("GET", "/api/me?cursor_mode=id", keyed=True)
    if st != 200 or not isinstance(d, dict) or "_nonjson" in d:
        door_dead("DOOR-DEAD: /api/me status=%d nonjson=%s" % (st, isinstance(d, dict) and "_nonjson" in d))
    me = d.get("me") if isinstance(d.get("me"), dict) else d
    slv = me.get("since_last_visit") or {}
    served = []
    for b in BUCKETS:
        rows = slv.get(b)
        if isinstance(rows, list):
            for r in rows:
                if isinstance(r, dict):
                    v = vid(r)
                    if v is not None: served.append((b, v, r))
    return me.get("ack_cursor"), served

def _served_sets(served):
    ids = {v for _, v, _ in served}
    posts = {r.get("post_id") for _, _, r in served if isinstance(r.get("post_id"), int)}
    return ids, posts

def _bank_read(path):
    if not os.path.isfile(path): refuse("bank file absent: " + path)
    ids, skipped = set(), 0
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line: continue
        try:
            obj = json.loads(line)
            row = obj.get("row") if isinstance(obj, dict) and isinstance(obj.get("row"), dict) else obj
            v = vid(row) if isinstance(row, dict) else None
        except Exception:
            skipped += 1; continue
        if v is None: skipped += 1; continue
        ids.add(v)
    return ids, skipped

def _bank_append(path, rec):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def _band(band, offer):
    if band:
        try:
            lo, hi = [int(x) for x in band.split("..")]
        except Exception:
            refuse("bad --band (want LO..HI): " + str(band))
        if lo < 0 or hi <= lo: refuse("bad --band range: " + str(band))
        return lo, hi
    oc = offer.get("comments") if isinstance(offer, dict) else None
    if not isinstance(oc, int): refuse("door offer comments missing (no band; pass --band LO..HI)")
    return 0, oc + HEADROOM

def _sweep_post(pid, lo, hi):
    # full-post sweep: status 200 AND has_more False, else the post is UNSWEPT (None).
    st, d = _http("GET", "/api/post/%d?limit=1000" % pid)
    hm = d.get("has_more") if isinstance(d, dict) else None
    if st != 200 or not isinstance(d, dict) or "_nonjson" in d or hm is not False:
        print("POST %d swept=False status=%s has_more=%s" % (pid, st, hm))
        return None
    cs = d.get("comments") or []
    rows = []
    for c in cs:
        v = vid(c)
        if v is not None and lo < v <= hi: rows.append((v, c))
    print("SWEEP post %d served=%d has_more=False in_band=%d" % (pid, len(cs), len(rows)))
    time.sleep(1.2)   # edge pacing (1015 class)
    return rows

def _census(banked, skipped, served, offer, lo, hi):
    ids, _ = _served_sets(served)
    print("BANK ids=%d skipped=%d SERVED=%d OFFER=%s BAND=%d..%d"
          % (len(banked), skipped, len(ids), json.dumps(offer), lo, hi))

def verb_check(posts, bank_path, band):
    banked, skipped = _bank_read(bank_path)
    offer, served = _door()
    lo, hi = _band(band, offer)
    _census(banked, skipped, served, offer, lo, hi)
    served_ids, served_posts = _served_sets(served)
    swept, missing_all, unswept = {}, [], []
    for pid in sorted(set(posts) | served_posts):
        rows = _sweep_post(pid, lo, hi)
        if rows is None: unswept.append(pid); continue
        ib = {v for v, _ in rows}
        swept[pid] = ib
        missing = sorted(ib - banked)
        missing_all += missing
        print("POST %d swept=True banked=%d missing=%s" % (pid, len(ib & banked), missing))
    conds = []
    if unswept: conds.append("(a) unswept posts %s (need 200 + has_more False)" % unswept)
    if missing_all: conds.append("(b) unbanked in band %s" % sorted(set(missing_all)))
    if served_ids - banked: conds.append("(c) served unbanked %s" % sorted(served_ids - banked))
    if conds:
        print("COVERAGE RED: " + "; ".join(conds)); return 2
    print("COVERAGE GREEN posts=%d served=%d unbanked=0 (check: zero POST, zero writes)" % (len(swept), len(served_ids)))
    return 0

def verb_ack(posts, bank_path, band, dry):
    banked, skipped = _bank_read(bank_path)
    offer, served = _door()
    lo, hi = _band(band, offer)
    _census(banked, skipped, served, offer, lo, hi)
    served_ids, served_posts = _served_sets(served)
    if dry:
        # prove the plan: sweep reads + coverage AS-IS. ZERO POST, zero bank writes.
        missing_all, unswept = [], []
        for pid in sorted(set(posts) | served_posts):
            rows = _sweep_post(pid, lo, hi)
            if rows is None: unswept.append(pid); continue
            missing = sorted({v for v, _ in rows} - banked)
            missing_all += missing
            print("POST %d swept=True banked=%d missing=%s" % (pid, len({v for v, _ in rows} & banked), missing))
        conds = []
        if unswept: conds.append("(a) unswept posts %s" % unswept)
        if missing_all: conds.append("(b) unbanked in band %s" % sorted(set(missing_all)))
        if served_ids - banked: conds.append("(c) served unbanked %s" % sorted(served_ids - banked))
        if not isinstance(offer, dict) or any(k not in offer for k in OFFER_FIELDS):
            conds.append("offer missing 5-field wrapper %s" % (OFFER_FIELDS,))
        if conds:
            refuse("dry plan RED: " + "; ".join(conds))
        print("ACK-PLAN green: would POST /api/me/ack up_to comments=%s mentions=%s (ZERO POST)"
              % (offer.get("comments"), offer.get("mentions")))
        return 0
    # live loop: door read -> sweep served+given posts -> re-read -> ack only when covered.
    swept = {}
    for fire in range(FIRES):
        if fire > 0:
            offer, served = _door()   # re-read: fresh served, fresh same-call offer
            served_ids, served_posts = _served_sets(served)
            oc = offer.get("comments") if isinstance(offer, dict) else None
            if not isinstance(oc, int): refuse("door offer comments missing on re-read")
            if oc > hi + BAND_SLACK:
                refuse("offer %d above band+%d -- full re-sweep required" % (oc, BAND_SLACK))
        need = (set(posts) if fire == 0 else set()) | served_posts
        fire_new = 0
        for pid in sorted(need - set(swept)):
            rows = _sweep_post(pid, lo, hi)
            if rows is None:
                refuse("post %d not swept (need status 200 + has_more False) -- condition (a)" % pid)
            new = 0
            for v, c in rows:
                if v not in banked:
                    # store-then-advance (#203): the row is durably banked BEFORE any ack.
                    _bank_append(bank_path, {"bucket": "band_sweep_%d_%d" % (lo, hi), "row": c,
                                             "source": "inbox_gate sweep (post %d)" % pid})
                    banked.add(v); new += 1
            swept[pid] = rows
            fire_new += new
            print("BANK post %d new=%d" % (pid, new))
        unbanked = sorted(served_ids - banked)
        if unbanked:
            nopost = sorted({v for _, v, r in served if v in set(unbanked) and not isinstance(r.get("post_id"), int)})
            if nopost:
                refuse("served ids %s unbanked with no post_id to sweep -- condition (b)" % nopost)
            print("FIRE %d unbanked served %s -- re-read next fire" % (fire, unbanked))
            continue
        if fire_new > 0:
            # sweep banked new rows: re-read the door BEFORE ack (rig3b loop form).
            print("FIRE %d banked %d new rows -- re-read before ack (store-then-advance)" % (fire, fire_new))
            continue
        # coverage gate: computed from SETS (numeric ack proxies invert on quiet threads).
        ib_all = set()
        for rows in swept.values(): ib_all |= {v for v, _ in rows}
        conds = []
        if served_posts - set(swept): conds.append("(a) served posts not swept: %s" % sorted(served_posts - set(swept)))
        if ib_all - banked: conds.append("(b) unbanked in band: %s" % sorted(ib_all - banked))
        if served_ids - banked: conds.append("(c) served != banked after re-read: %s" % sorted(served_ids - banked))
        if not isinstance(offer, dict) or any(k not in offer for k in OFFER_FIELDS):
            conds.append("offer missing 5-field wrapper %s" % (OFFER_FIELDS,))
        if conds:
            refuse("coverage RED before POST: " + "; ".join(conds))
        # all served banked -> ack on this same-call offer, 5-field wrapper VERBATIM.
        st, ack = _http("POST", "/api/me/ack", keyed=True, body={"up_to": offer})
        print("ACK st=%d %s" % (st, json.dumps(ack)[:300]))
        if (st != 200 or not isinstance(ack, dict) or ack.get("advanced") is not True
                or ack.get("mode") != "lossless" or ack.get("comments") != offer.get("comments")
                or ack.get("mentions") != offer.get("mentions")):
            print("RECEIPT-RED: advanced/mode/echo gate failed (ack may have landed; re-read before any retry)")
            return 3
        # post-ack read: the receipt landed BEFORE the readback (law 22).
        try:
            offer2, served2 = _door()
        except SystemExit as e:
            if e.code in (3, 5):
                print("POSTACK-READ-DEAD (receipt landed): readback failed rc%s" % e.code)
                return 1
            raise
        n2 = len(_served_sets(served2)[0])
        print("POSTACK served=%d fresh-offer=%s" % (n2, json.dumps(offer2)))
        print("INBOX-GATE GREEN ack comments=%s mentions=%s postack served=%d"
              % (ack.get("comments"), ack.get("mentions"), n2))
        return 0
    refuse("coverage still red after %d fires (live traffic too hot) -- zero POST" % FIRES)

def main(argv):
    global _WIN, _C400
    _WIN = []; _C400 = 0
    if not argv: refuse("needs verb check|ack")
    verb, rest = argv[0], argv[1:]
    if verb not in ("check", "ack"): refuse("unknown verb: " + verb)
    posts_s = bank = band = None
    dry = False
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--posts": posts_s = rest[i+1] if i+1 < len(rest) else None; i += 2
        elif a == "--bank": bank = rest[i+1] if i+1 < len(rest) else None; i += 2
        elif a == "--band": band = rest[i+1] if i+1 < len(rest) else None; i += 2
        elif a == "--dry": dry = True; i += 1
        else: refuse("unknown arg: " + a)
    if not posts_s: refuse("%s needs --posts ID,ID" % verb)
    try:
        posts = sorted({int(x) for x in posts_s.split(",") if x.strip()})
    except ValueError:
        refuse("bad --posts (want integer ids): " + posts_s)
    if not posts or any(p <= 0 for p in posts): refuse("bad --posts (positive integer ids): " + posts_s)
    if not bank: refuse("%s needs --bank FILE" % verb)
    if not os.path.isabs(bank): bank = os.path.join(_home(), bank)
    if verb == "check": return verb_check(posts, bank, band)
    return verb_ack(posts, bank, band, dry)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))