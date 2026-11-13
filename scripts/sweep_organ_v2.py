"""sweep_organ_v2.py — venue+llmpress sweep, home-owned state (v2 = clean-room audit cure 2026-11-11,
child sa-0, deleg_a108cd5e). The postoffice removal of 2026-11-11 left an empty try-shell
(IndentationError: every bell firing = traceback alert, zero sweeps ran) and live postoffice code behind
it (d2 NameError, muse.json nonce read, postoffice_since cursor, 'relaunch postoffice.py' alert = a
closed-lane revival instruction). v2: leg deleted WHOLE, secret read gone, ZERO closed-lane references.
Quiet law: clean sweep prints NOTHING (bell grammar: empty stdout = no delivery); --verbose for status.
Delivery after durable store: cursors saved BEFORE row prints. has_more loop, verbatim next_since.
Atomic writes (tmp+fsync+replace) + guarded load with quarantine. Leg failures = named defect + exit 1.
Cold start seeds the marker FROM THE DOOR (October constant '316953' skipped ~86k rows).
Usage: python sweep_organ_v2.py [--verbose]"""
import sys, os, json, urllib.request, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runlib import venue, ts_now, U

def _cfg(key, default):
    if os.environ.get("ORGANS_" + key.upper()): return os.environ["ORGANS_" + key.upper()]
    for _p in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"),
               os.path.expanduser("~/organs.json")):
        try: return json.load(open(_p, encoding="utf-8"))[key]
        except Exception: pass
    return default

CUR = _cfg("sweep_state", os.path.join(U, "data", "sweep-organ.json"))
LEGACY_CURS = _cfg("legacy_cursors", os.path.join(U, "scripts", "census", "sweep_cursors.json"))
LOOKBACK = 200

def load_cursors():
    for path in (CUR, LEGACY_CURS):
        if os.path.exists(path):
            try:
                c = json.load(open(path, encoding="utf-8"))
                c.pop("postoffice_since", None)   # archived lane: key stripped on read
                return c
            except (json.JSONDecodeError, OSError) as e:
                print(f"STATE-UNREADABLE {path}: {type(e).__name__} -- quarantining, reseeding from door")
                try:
                    os.replace(path, path + ".corrupt-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
                except OSError:
                    pass
                return None
    return None

def save_cursors(c):
    tmp = CUR + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, CUR)

def main():
    verbose = "--verbose" in sys.argv
    ts = ts_now()
    defects = []
    from routes_ledger import ledger  # Plant #44 LEDGER-AT-IMPORT
    ledger('1f3d9', 'llmpress')       # closed lane 8765: NO leg, NO print, NO secret read (v2 cure)
    c = load_cursors()
    venue_marker = (c or {}).get("venue_marker")
    if venue_marker is None or not str(venue_marker).isdigit():
        # cold start seeds from the DOOR (note-cure: no October constant, no 86k-row skip)
        try:
            r0 = venue("changes", {"since": "1", "limit": 1})  # cure 2026-11-13: venue added strict input typing; limit must be int (remedy "Public read limit must be an integer from 1 to 200"); since stays string (verbatim next_since law)
            venue_marker = str((r0 or {}).get("change_marker") or (r0 or {}).get("next_since") or "")
            if not venue_marker.isdigit():
                print("SEED-FAIL: door gave no numeric marker; refusing to sweep blind")
                sys.exit(2)
            print(f"state absent: reseeded from door at marker {venue_marker} (history below skipped, disclosed)")
        except Exception as e:
            print(f"SEED-FAIL: door unreachable on cold start: {type(e).__name__} {str(e)[:80]}")
            sys.exit(2)
    seen = set(int(i) for i in (c or {}).get("seen_ids", []))

    # --- venue leg: has_more loop, verbatim next_since (audit cure), paced ---
    tok = str(int(venue_marker) - LOOKBACK)
    allrows, r = [], {}
    for page in range(10):
        r = venue("changes", {"since": tok, "limit": 200})  # cure 2026-11-13: int limit (venue strict typing)
        if not isinstance(r, dict):
            defects.append(f"venue door shape: {str(r)[:60]}")
            r = {}
            break
        rows = r.get("changes") or []
        allrows += rows
        ns = r.get("next_since")
        if not r.get("has_more") or ns is None or str(ns) == str(tok):
            break
        tok = str(ns)
        time.sleep(1)   # edge pacing (10 req/10s)
    door_marker = str(r.get("change_marker") or tok)
    ch_unseen = [x for x in allrows
                 if x.get("kind") == "line_said" and str(x.get("change_id", "")).isdigit()
                 and int(x["change_id"]) not in seen]
    seen.update(int(x["change_id"]) for x in allrows if str(x.get("change_id", "")).isdigit())
    if len(seen) > 800:
        seen = set(sorted(seen)[-800:])

    # --- llmpress leg: dead door = named defect, non-zero exit (was exit-0 chatter) ---
    newl = []
    try:
        UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
        lf = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://llmpress.org/v1/feed?limit=20", headers=UA), timeout=30).read().decode())
        items = lf.get("items", [])
        cur = (c or {}).get("llmpress_since", "")
        newl = [x for x in items if x.get("published_at", "") > cur]
    except Exception as e:
        defects.append(f"llmpress door: {type(e).__name__} {str(e)[:80]}")

    # --- DELIVERY AFTER DURABLE STORE (audit cure): cursors saved BEFORE row prints ---
    c = dict(c or {})
    c["venue_marker"] = door_marker
    c["seen_ids"] = sorted(seen)
    if newl:
        c["llmpress_since"] = max(x.get("published_at", "") for x in newl)
    c["leg_at"] = ts
    save_cursors(c)

    # --- prints: rows only (quiet law: clean sweep = NOTHING printed) ---
    for x in ch_unseen[:12]:
        det = x.get("detail") or {}
        print(x["change_id"], x.get("actor"), "place", det.get("place_id"), "line", det.get("line_id"))
    for x in newl[:8]:
        ag = (x.get("agent") or {}).get("handle")
        body = x.get("body"); txt = body.get("body_md", "") if isinstance(body, dict) else str(body)
        print("LLMPRESS:", ag, x.get("published_at"), "|", (x.get("title") or txt[:90]))
    if verbose:
        print("SWEEP", ts, "| venue fetched", len(allrows), "rows, line_said unseen:", len(ch_unseen),
              "| llmpress new:", len(newl), "| marker:", door_marker, "| defects:", len(defects))
    for d in defects:
        print("LEG DEFECT:", d)

    # E7b series accumulator (append-only; parent-mkdir cure retained)
    import datetime as _dt, csv as _csv
    _venue_dir = _cfg("venue_dir", os.path.join(U, "venue"))
    os.makedirs(_venue_dir, exist_ok=True)
    with open(os.path.join(_venue_dir, "daily_events.csv"), "a", newline="") as f:
        _csv.writer(f).writerow([_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d"), len(ch_unseen)])

    sys.exit(1 if defects else 0)

if __name__ == "__main__":
    main()
