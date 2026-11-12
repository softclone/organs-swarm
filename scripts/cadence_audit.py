# Cadence audit v3 (gnomon #4271 law, 2026-11-09; v3 = clean-room audit cure 2026-11-11, deleg_366768ad child C):
# B1 LIVE cure: weekly-by-day-of-week cron detection (parts[4] != '*' -> 604800 BEFORE the daily check;
#   'every tuesday 6am' at iv=86400 was firing false MISS ~4 days/week on truncation-sweep-weekly-SCRIPT).
# Exit discipline cures: defects exit non-zero (was exit-0-always); clean night prints NOTHING
#   (counter/phase legs were chatty every 4h: their unconditional prints violated the empty-stdout quiet law).
# Dead-code cure: hourly exprs ('0 * * * *', '*/7 * * * *') int() crash before the '*' check (blind hourly path).
# Shape/reader cures: dict/list job tolerance (.values() for dicts), non-numeric job_id coercion,
#   guarded load with bounded retry (a reader defect must never alert as a bell defect).
# Clock cure: naive timestamps are LOCALIZED at the profile's zone (-06:00), not assumed UTC (naive-UTC
#   assumption skewed gaps +6h -> false misses <2h intervals). tz-aware inputs unchanged.
# Miss = observed gap > threshold x declared interval for a job that is enabled+scheduled (env lever GP848).
import json, time, datetime, re, os
import os as _os, json as _json
def _jobs_path():
    if _os.environ.get("ORGANS_JOBS"): return _os.environ["ORGANS_JOBS"]
    for _p in (_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "local.json"),
               _os.path.expanduser("~/organs.json")):
        try:
            v = _json.load(open(_p, encoding="utf-8")).get("jobs")
            if v: return v
        except Exception: pass
    hh = _os.environ.get("HERMES_HOME")
    if hh: return _os.path.join(hh, "cron", "jobs.json")
    return _os.path.expanduser("~/.hermes/cron/jobs.json")
JOBS = _jobs_path()

def _envint(name, default):  # wave-5 W08: a config defect is a reader defect; it must NEVER alert as a bell defect (header law)
    try:
        return int(os.environ.get(name, default))
    except (ValueError, TypeError):
        print(f"READER ADVISORY: malformed {name} -- using default {default} (config defect, not a bell defect)")
        try:
            return int(default)
        except (ValueError, TypeError):  # wave-6 W6-12: an unreadable default must never crash the reader
            print(f"READER ADVISORY: default for {name} also unreadable -- using 0")
            return 0
def _cfgkey(key):  # wave-6 W6-10/11: config chain (local.json -> ~/organs.json) for keys the README documents; env wins at each caller
    for _p in (_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "local.json"), _os.path.expanduser("~/organs.json")):
        try:
            v = _json.load(open(_p, encoding="utf-8")).get(key)
            if v: return str(v)
        except Exception: pass
    return None
# wave-6 W6-11: tz_offset rides the config chain; W6-12: an out-of-range offset is a READER ADVISORY, never a crash
_tz6 = _envint("ORGANS_TZ_OFFSET", _cfgkey("tz_offset") or "-6")
if abs(_tz6) >= 24:
    print(f"READER ADVISORY: ORGANS_TZ_OFFSET {_tz6} outside +-24h range -- falling back to -6 (wave-6 W6-12: reader defect, never a bell alert)")
    _tz6 = -6
NAIVE_TZ = datetime.timezone(datetime.timedelta(hours=_tz6))  # profile local zone (default -6 CST, disclosed)

def load_jobs():
    for tries in range(3):
        try:
            jobs = json.load(open(JOBS, encoding="utf-8"))
            jl = jobs.get("jobs", jobs) if isinstance(jobs, dict) else jobs
            if isinstance(jl, dict):
                jl = list(jl.values())
            return [j for j in jl if isinstance(j, dict)]
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            time.sleep(2)  # transient cron-write race: bounded retry
    # reader defect: disclosed quietly -- a READER defect must never fire the keeper's bell alert
    print("CADENCE-READER: jobs.json unreadable after 3 tries (reader defect, not a bell defect)")
    raise SystemExit(0)

def _home_dir():
    if os.environ.get("ORGANS_HOME"): return os.environ["ORGANS_HOME"]
    for _q in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"),
               os.path.expanduser("~/organs.json")):
        try:
            v = json.load(open(_q, encoding="utf-8")).get("home")
            if v: return v
        except Exception: pass
    return os.path.expanduser("~/shop")
jl = load_jobs()
now = datetime.datetime.now(datetime.timezone.utc)

def parse(t):
    if not t: return None
    try:
        dt = datetime.datetime.fromisoformat(t)
    except ValueError:
        return None
    if dt.tzinfo: return dt.astimezone(datetime.timezone.utc)
    return dt.replace(tzinfo=NAIVE_TZ)  # naive = profile local, disclosed; NEVER assume UTC

def interval_sec(sched):
    d = (sched.get("display") or "").lower()
    m = re.search(r"every (\d+)([smh])", d)  # wave-7 F20 cure: seconds grammar included -- a dropped 'every 30s' bell was invisible to the census
    if m: return int(m.group(1)) * (3600 if m.group(2) == "h" else 1 if m.group(2) == "s" else 60)
    if "weekly" in d: return 604800
    for wd in ("monday","tuesday","wednesday","thursday","friday","saturday","sunday"):
        if "every " + wd in d: return 604800
    e = sched.get("expr") or ""
    if e:
        parts = e.split()
        if len(parts) == 5:
            try:
                if parts[4] != "*" and parts[2] == "*" and parts[3] == "*":
                    return 604800  # weekly-by-dow FIRST (B1 cure)
                if parts[1] == "*" and parts[2] == "*" and parts[3] == "*" and parts[4] == "*":
                    ms = parts[0]
                    if ms.startswith("*/"):
                        return max(int(ms[2:]), 1) * 60
                    if ms.isdigit():
                        return 3600  # hourly BEFORE int-conversion (dead-code cure)
                    return None  # minute-list forms not scored
                if parts[2] == "*" and parts[3] == "*" and parts[4] == "*" and parts[1].isdigit() and parts[0].isdigit():
                    return 86400
            except ValueError:
                pass
    if "every day" in d: return 86400
    return None

defects = []
misses = []; seen = 0
import math as _m6
thr = 3.0
try:
    thr = float(os.environ.get("CADENCE_THRESHOLD", 3))
    if not _m6.isfinite(thr) or thr <= 0:
        print("READER ADVISORY: CADENCE_THRESHOLD not a positive finite number -- using 3 (wave-6 W6-13: nan/inf silently blinds the misses leg)")
        thr = 3.0
except ValueError:
    print("READER ADVISORY: malformed CADENCE_THRESHOLD -- using 3 (wave-6 W6-21: disclosure, matching the _envint contract)")
for j in jl:
    lr = parse(j.get("last_run_at")); nx = parse(j.get("next_run_at"))
    if not j.get("enabled") or j.get("state") not in ("scheduled",): continue
    s = j.get("schedule") if isinstance(j.get("schedule"), dict) else {}
    iv = interval_sec(s); disp = s.get("display", "")
    if iv: seen += 1
    if iv and lr and (now - lr).total_seconds() > thr * iv:
        misses.append((str(j.get("name")), disp, round((now - lr).total_seconds() / 3600, 1)))
    # wave-7 F8 cure: a PRESENT-but-malformed last_run_at parses to None -- that is an
    # unreadable bookkeeping field (advisory), NOT a manufactured 'never-fired past-due' miss.
    if lr is None and nx and nx <= now:
        _raw_lr = j.get("last_run_at")
        if _raw_lr:
            print("CADENCE-ADVISORY: malformed last_run_at on", str(j.get("name")), "-- cadence state unreadable, not counted as never-fired")
        else:
            misses.append((str(j.get("name")), disp, "never-fired past-due"))

if misses:
    print("CADENCE AUDIT fired at", now.isoformat()[:19], "Z (machine clock)")
    print("recurring jobs checked:", seen, "| cadence misses (>%.1fx declared interval):" % thr, len(misses))
    for mm in misses: print(" MISS:", mm)
    print("AUDIT: a bell dropped its cadence — wake the shop.")

# C5-1997 counter chain-break leg -- ADVISORY; prints ONLY on real breaks/dups (quiet cure)
_cw_raw = (os.environ.get("ORGANS_COUNTER_WINDOW") or _cfgkey("counter_window") or "5000,10000").split(",")  # wave-6 W6-11: rides the config chain
try:
    _cw = (int(_cw_raw[0]), int(_cw_raw[1]))
except (ValueError, IndexError):
    print("READER ADVISORY: malformed ORGANS_COUNTER_WINDOW -- using default (5000,10000) (config defect, not a bell defect)")
    _cw = (5000, 10000)
counter_miss = False
try:
    _lp = os.environ.get("ORGANS_LEDGER")
    if not _lp:
        for _q in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"), os.path.expanduser("~/organs.json")):
            try:
                _lp = json.load(open(_q, encoding="utf-8")).get("ledger")
                if _lp: break
            except Exception: pass
    _d = open(_lp or os.path.expanduser("~/shop/ledgers/CORPUS.md"), encoding="utf-8").read()
    _prefix = os.environ.get("ORGANS_ROW_PREFIX")  # wave-5 W20: NO shop identity in the portable default; unset = inert + disclosed; re.escape keeps it injection-safe
    if not _prefix:  # follows the shop config chain like every other organ value (env -> local.json -> ~/organs.json)
        for _cf in (_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "local.json"), _os.path.expanduser("~/organs.json")):
            try:
                v = _json.load(open(_cf, encoding="utf-8")).get("row_prefix")
                if v: _prefix = v; break
            except Exception: pass
    if not _prefix:
        print("COUNTER LEG INERT (advisory): ORGANS_ROW_PREFIX not configured -- shop ledger grammar is a config value")
        _rows = []
    else:
        # gate law v2 worn by the counter leg (2026-11-12, dup-label '7' false firing):
        # the serial gate counts the LABEL FIELD only -- field 2 of the row (fixed offset,
        # full-match grammar). Body prose quoting "| C5-7 CLOSED" is data, not a booked slot.
        _rows = []
        for _ln in _d.splitlines():
            if not _ln.startswith("| "):
                continue
            _fx = _ln.lstrip("| ").split(" | ")  # label = FIRST field that full-matches C5-N
            for _f in _fx[:3]:  # label lives in field 0 (mint cell) or 1 (stamped preamble)
                _m = re.fullmatch(re.escape(_prefix) + r"-(\d+)", _f.strip())
                if _m:
                    _rows.append(_m.group(1))
                    break
    _pairs = [tuple(map(int, x)) for x in re.findall(r"[Cc]ounter\s+(\d{4,5})->(\d{4,5})", _d) if _cw[0] < int(x[1]) < _cw[1]]  # wave-4 F-09b: counter window config-driven
    _breaks = sum(1 for a, b in zip(_pairs, _pairs[1:]) if a[1] != b[0])
    _dups = sorted({n for n in _rows if _rows.count(n) > 2})  # 2026-11-11 rebalance: label pairs = booked collision class (register-policed, append-only); counts >2 = serial-gate breach
    if _breaks > 80:
        # 2026-11-11 alarm-hygiene cure (self-contradiction caught on its own print: the row says
        # 'advisory drift bound; canonical number remains the re-count' and the OLD exit fired on it
        # -- computed YELLOW wearing a RED exit, the #202 family worn by the alarm rig itself):
        # advisory drift PRINTS, never fires the keeper alert. Multi-lane counters legitimately diverge;
        # the recount (counter_head rig) is the canonical instrument.
        print("COUNTER-CHAIN ADVISORY: rows=%d pairs=%d breaks=%d dup_labels=%s (advisory drift bound; canonical number remains the re-count)" % (len(_rows), len(_pairs), _breaks, _dups))
    if _dups:
        counter_miss = True
        print("COUNTER-CHAIN DUP LABELS:", _dups[:12])
except FileNotFoundError:
    pass  # wave-6 W6-23: a missing ledger is the portable default -- stay quiet (README quiet law), like the INERT prefix
except Exception as _e:
    print("counter leg: reader artifact:", type(_e).__name__)

# phase leg -- prints ONLY on real phase misses (quiet cure)
phase_miss = False
try:
    import statistics as _st
    _seen = {}
    try:
        for _l in open(os.environ.get("ORGANS_BELL_FIRINGS") or _cfgkey("bell_firings") or os.path.join(_home_dir(), "data", "bell-firings.jsonl"), encoding="utf-8"):  # wave-6 W6-10: config key bell_firings now rides the chain
            _r = json.loads(_l)
            if _r.get("last_run"):
                _jn7 = _r.get("job")  # wave-7 F25 cure: a torn record missing 'job' is skipped with an advisory -- it must NOT abort the leg
                if not _jn7:
                    print("CADENCE-ADVISORY: firing record without 'job' key skipped:", str(_r)[:60])
                    continue
                _seen.setdefault(_jn7, set()).add(_r["last_run"])
    except FileNotFoundError:
        pass
    _res_lines = []
    for _j in jl:
        if not _j.get("enabled"): continue
        _iv = interval_sec(_j.get("schedule") or {})
        _nm = str(_j.get("name") or str(_j.get("job_id", "?"))[:12])
        _raw = sorted(_seen.get(_nm, []))[-12:]
        _ts = [parse(x) for x in _raw]
        _ts = [t for t in _ts if t]
        if not _iv or len(_ts) < 3: continue
        _rs = sorted((t.timestamp() % _iv) for t in _ts)
        _rs = [min(r, _iv - r) for r in _rs]
        _spread = round(max(_rs) - min(_rs), 1)
        _med = round(_st.median(_rs), 1)
        _res_lines.append((_nm, _iv, _med, _spread))
    _bad = [x for x in _res_lines if x[3] > 0.45 * x[1]]  # spread >45% of period = drifting slot; rebalance 2026-11-11 (clean-room audit follow-up): the v2 bound (spread>120s & med>60s) fired on EVERY 30m/2h bell — uniform sampling of a busy machine sits near med=period/2; the phase leg reads bell-FIRING stamps (event-driven, not scheduled ticks), so it is DISCLOSORY: its verdict fires the exit only on gross slot-loss
    # 2026-11-11 alarm-hygiene cure, second leg (same family as the counter leg): the comment always
    # said DISCLOSORY; the code fired exit 1 on phase_miss, so a 'keeps cadence, drifting phase'
    # morning woke the keeper. Phase drift now PRINTS only. Gross slot-loss is the 'misses' leg's
    # object (a bell that skipped its period), and it keeps firing the alert.
    if _bad:
        for _n, _iv, _med, _sp in _bad[:8]:
            print("  PHASE ADVISORY: %s period=%ss median-offset=%ss spread=%ss (keeps cadence, drifting phase)" % (_n, _iv, _med, _sp))
except Exception as _e2:
    print("phase leg: reader artifact:", type(_e2).__name__)

# Bell census leg (2026-11-12, dream-lane autopsy C5 lane): the dream lane died for two days,
# emitting red glyphs every 10 minutes INSIDE a cadence the scheduler counted as healthy —
# the scheduler reads exit codes, the rig reads its own door; adjacent blind spots manufactured
# 'lane is fine' while every fire was a refusal. No organ listed the non-green bells.
# The daily audit now lists them. Class law: a RECURRING bell with a non-green last fire is a
# live defect (it will refuse again on its next tick); a ONE-SHOT red is disclosed history —
# advisory count only, never an alert (7 of the 9 reds at autopsy were obituaries).
live_reds = []
hist_reds = 0
carrier_reds = 0
carrier_list = []  # census-carrier self-reference cure (2026-11-12, failure_streak 2 quine):
# cadence-audit-daily RUNS this census. Its last fire is this rig's own exit code: red
# because the census saw red, saw red because of its own last fire. Counting the carrier
# as a lane defect manufactures a self-sustaining alarm -- the alarm that screams for
# two days IS the last organ speaking. Carrier reds become advisory at streak 1; the
# carrier alerts only at failure_streak >= 2, i.e. the census itself died twice running.
for _j in jl:
    _st = str(_j.get("last_status") or "")
    if _st in ("", "ok", "green", "success"):
        continue
    _nm = str(_j.get("name") or str(_j.get("job_id", "?"))[:12])
    _sch6 = _j.get("schedule") if isinstance(_j.get("schedule"), dict) else {}  # wave-6 W6-14: string schedule is store drift; census mirrors the misses-leg guard
    _kind = str(_sch6.get("kind") or "")
    _is_carrier = os.path.basename(str(_j.get("script") or "")).startswith("cadence_audit")  # wave-7 F13 cure: basename stamp -- a substring anywhere in the path misclassified unrelated scripts
    _streak7 = int(_j.get("failure_streak") or 0)  # wave-7 F12 cure: the promised register read in CODE: carrier alerts at streak >= 2 (census died twice running)
    if _kind == "once" or not _j.get("enabled"):  # wave-4 F-08: a DISABLED bell will never fire again: obituary, not alert
        hist_reds += 1
    elif _is_carrier:
        # the census CANNOT distinguish its own echo from its own death: both read as
        # its own last_status. Carrier reds are advisory, named, disclosed -- the
        # witness for census death is the bell-runner log, not the census (named blind spot).
        if _streak7 >= 2:
            live_reds.append((_nm, f"CARRIER DEATH streak {_streak7} (alert, register-read): " + _st[:40]))
        else:
            carrier_reds += 1
            carrier_list.append((_nm, _st[:40]))
    else:
        live_reds.append((_nm, _st[:40]))
if carrier_reds:
    print("BELL CENSUS: %d census-carrier red(s) -- SELF-REFERENCE ADVISORY, not alert:" % carrier_reds)
    for _n, _s in carrier_list[:4]:
        print("  CARRIER-RED (advisory):", _n, "|", _s)
if live_reds:
    print("BELL CENSUS RED: %d recurring bells non-green at last fire:" % len(live_reds))
    for _n, _s in live_reds[:12]:
        print("  LIVE-RED:", _n, "|", _s)
if hist_reds:
    print("BELL CENSUS: %d one-shot/disabled reds (disclosed history, advisory)" % hist_reds)  # wave-5 W15: label names what is counted (kind-once AND disabled)

# exit discipline (cure): non-zero IFF a real defect; clean night = silent exit 0, empty stdout = no delivery
# 2026-11-11: advisory prints (counter-chain drift bound, phase drift) do NOT fire the keeper alert;
# real defects do: slot-loss 'misses', dup-label serial-gate breaches (catch #202 family, worn inward),
# and (2026-11-12) recurring bells red at last fire — a lane in its dying loop is the miss family.
if misses or counter_miss or live_reds:
    raise SystemExit(1)
raise SystemExit(0)
