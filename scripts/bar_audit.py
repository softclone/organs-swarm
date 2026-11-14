# bar_audit.py -- Tier-1 bar-audit standard distilling the _hot*_hip cold-seat family (107 one-off copies).
# FAMILY: piece + cold-seat auditor -> Line1: VERDICT = ADMIT/ADMIT-WITH-NOTE/HOLD + BAR_MET/BAR_NOT_MET
#         vs the piece's canonical **Bar:**; Line2: one-line ground. (exemplars _hot1451_hip, _hot1501)
# Family habits cured at the organ: max_tokens 2048/128000 -> floor 131072 (keeper law);
#   relative-path weld open('eros/eros-N.md') -> HOME-resolved piece paths (breadcrumb/cwd weld class);
#   bare handle seat -> config-chain seat (door-path law: bare base gets completions path appended);
#   parse gate IN CODE: BAR_MET/BAR_NOT_MET only from exact tokens; UNPARSED named, never tallied (PENDING law).
# Verbs:
#   audit --pieces "name=PATH,name=PATH" [--bar TEXTFILE] [--out PATH] [--dry]
#   --dry: file existence + byte census + bar-override presence, ZERO seat calls, rc0.
#   no verb / bad arg shape: REFUSE rc2 BEFORE any door. live: one door call per piece,
#   named results (door errors ride in the results, rc0), keep-first store, SUMMARY tally.
# Gates in code:
#   parse-verdict: Line1 must carry a BAR_MET/BAR_NOT_MET token (BAR_NOT_MET wins containment)
#     and a verdict token (ADMIT-WITH-NOTE checked BEFORE ADMIT -- containment order law);
#     anything else UNPARSED -- raw always stored, UNPARSED rows never enter the tally.
#   keep-first (GP534): window-stamped store written O_EXCL -- never overwrites the first copy.
#   arg-shape: --pieces entries must be name=PATH with BOTH sides non-empty; missing --pieces,
#     valueless flags, absent piece/bar files REFUSE rc2 before any door.
#   non-JSON door bodies named per CATCHES 302 (ok:false head in result, never json.loads death).
#   max_tokens floor 131072 asserted in ask() (family habit rode 2048/128000 -- cured at the organ).
# CURES over the proven skeleton (named; fired in suite leg bar-audit-gates):
#   verb-gate cure: the skeleton accepted any first token; the audit verb is now required --
#     verbless argv REFUSES rc2 before any door (family verb law, seat_score sibling shape).
#   arg-shape gate cure: empty name or empty PATH entries (=PATH / name=) REFUSE rc2 -- the
#     skeleton let name= through to open(HOME), an unnamed IsADirectoryError death; valueless
#     --pieces is named like --bar/--out (the skeleton fell through to the missing-pieces line).
#   keep-first collision cure: O_EXCL FileExistsError lands as a NAMED KEEP-FIRST line, rc0,
#     first copy intact -- the skeleton died an unnamed FileExistsError traceback on re-fire.
#   door-shell cure: empty choices list / null message named DOOR-SHELL -- the skeleton caught
#     only KeyError/TypeError, so choices:[] died IndexError; content None falls back to
#     reasoning_content then "" (the skeleton stored raw None).
#   piece-decode gate cure: non-UTF-8 piece or --bar file REFUSES rc2 named before any door --
#     the skeleton died an unnamed UnicodeDecodeError mid-read.
#   tally gate cure: SUMMARY line counts PARSED rows only; UNPARSED and door-errors are named
#     and never tallied (the skeleton had no tally, so silence could pass for a clean audit).
#   dispatch-wrap cure: any exception escaping main() prints REFUSE: <Class>: <msg> rc5 --
#     a traceback never escapes the organ (loud-named law).
# DATUMS (deploy lessons kept as prose -- zero estate literals in code):
#   (1) config-chain locality: a runner placed in SCRATCH cannot see the shop's scripts/local.json;
#       seat_url/seat_model pins live BESIDE the rig. The live proof-fire of this skeleton rode the
#       user-config seat (a bare base URL -- the door-path gate appends the completions path) with
#       ORGANS_HOME pinned at scratch so the store never touched an estate tree.
#   (2) family habit maxtok 2048/128000 cured at the 131072 floor, asserted in ask().
# Config chain (portable, zero estate literals, zero secret values):
#   HOME = ORGANS_HOME env > local.json beside > ~/organs.json
#   seat = ORGANS_SEAT_URL env > seat_url config ; model = ORGANS_SEAT_MODEL env > seat_model config > "local-seat"
import json, os, sys, time, urllib.request, urllib.error

def _cfg_dir(): return os.path.dirname(os.path.abspath(__file__))
def _key(k, dflt=None):
    for p in (os.path.join(_cfg_dir(), "local.json"), os.path.expanduser("~/organs.json")):
        if os.path.exists(p):
            try:
                v = json.load(open(p, encoding="utf-8")).get(k)
                if v: return v
            except Exception: continue
    return dflt
def _home(): return os.environ.get("ORGANS_HOME") or _key("home", os.path.expanduser("~/shop"))

HOME = _home()
SEAT = os.environ.get("ORGANS_SEAT_URL") or _key("seat_url", "http://127.0.0.1:8080/v1/chat/completions")
MODEL = os.environ.get("ORGANS_SEAT_MODEL") or _key("seat_model", "local-seat")
MAXTOK = 131072

def _door(url):
    # door-path law: config may carry a bare base (host[:port] with no path) -- append the completions path.
    from urllib.parse import urlsplit, urlunsplit
    p = urlsplit(url)
    if not p.path or p.path == "/":
        p = p._replace(path="/v1/chat/completions")
    return urlunsplit(p)

ASK = ("Cold auditor. The piece below carries its canonical Bar (its own stated standard). "
       "Judge the piece against that Bar. Answer with exactly two lines:\n"
       "Line1: VERDICT = ADMIT or ADMIT-WITH-NOTE or HOLD, BAR_MET or BAR_NOT_MET\n"
       "Line2: one-line ground.\n\nTHE PIECE:\n")

def ask(piece, bar_text=None, maxtok=MAXTOK):
    assert maxtok >= 131072, "keeper law: max_tokens floor 131072"
    prompt = ASK
    if bar_text: prompt = ASK + "\n(EXPLICIT BAR OVERRIDE: " + bar_text.strip() + ")\n"
    body = {"model": MODEL, "max_tokens": maxtok, "temperature": 1.0,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "system", "content": prompt},
                         {"role": "user", "content": piece}]}
    req = urllib.request.Request(_door(SEAT), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        raw = urllib.request.urlopen(req, timeout=300).read().decode()
    except urllib.error.HTTPError as e:
        head = e.read().decode(errors="replace")[:300]
        return {"ok": False, "err": "HTTPError %d: %s" % (e.code, head)}
    except Exception as e:
        return {"ok": False, "err": "DOOR-DEAD %s: %s" % (type(e).__name__, str(e)[:200])}
    try:
        d = json.loads(raw)
    except Exception:
        # CATCHES 302 law: doors may serve non-JSON (rate walls) -- name it, never die in json.loads
        return {"ok": False, "err": "NON-JSON head: " + raw[:200]}
    try:
        msg = d["choices"][0]["message"]
        text = (msg.get("content") or msg.get("reasoning_content") or "").strip()
    except Exception:
        # door-shell cure: empty choices / null message named, never IndexError/AttributeError
        return {"ok": False, "err": "DOOR-SHELL (JSON without choices): " + raw[:200]}
    return {"ok": True, "text": text}

def parse_verdict(text):
    t = text or ""
    line1 = t.splitlines()[0] if t.splitlines() else t
    # containment order law: BAR_NOT_MET contains BAR_MET -- check the longer token first.
    bar = "BAR_NOT_MET" if "BAR_NOT_MET" in line1 else ("BAR_MET" if "BAR_MET" in line1 else "UNPARSED")
    verdict = "UNPARSED"
    for v in ("ADMIT-WITH-NOTE", "ADMIT", "HOLD"):  # ADMIT-WITH-NOTE contains ADMIT -- order matters
        if v in line1: verdict = v; break
    return bar, verdict

def main(argv):
    if not argv or argv[0] != "audit":
        print("REFUSE: verb audit required (rc2)"); return 2  # verb-gate cure
    dry = "--dry" in argv
    pieces = None
    bar_text = None
    out = None
    for i, a in enumerate(argv):
        if a in ("--pieces", "--bar", "--out") and i + 1 >= len(argv):
            print("REFUSE: %s without value (rc2)" % a); return 2  # arg-shape gate cure: never IndexError
        if a == "--pieces":
            pieces = argv[i + 1]
        elif a == "--bar":
            bp = argv[i + 1]
            if not os.path.exists(bp): print("REFUSE: --bar file absent %s (rc2)" % bp); return 2
            try:
                bar_text = open(bp, encoding="utf-8").read()
            except UnicodeDecodeError:
                print("REFUSE: --bar file not UTF-8: %s (rc2)" % bp); return 2  # piece-decode gate cure
        elif a == "--out":
            out = argv[i + 1]
    if not pieces:
        print("REFUSE: audit needs --pieces \"name=PATH,...\" (rc2)"); return 2
    rows = []
    for ent in pieces.split(","):
        if "=" not in ent:
            print("REFUSE: --pieces entry not name=PATH: %s (rc2)" % ent); return 2
        name, path = ent.split("=", 1)
        if not name or not path:
            print("REFUSE: --pieces entry needs non-empty name and PATH: %s (rc2)" % ent); return 2  # arg-shape gate cure
        if not os.path.isabs(path): path = os.path.join(HOME, path)
        if not os.path.exists(path):
            print("REFUSE: piece file absent: %s (rc2)" % path); return 2
        rows.append((name, path))
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if dry:
        for name, path in rows:
            print("[dry] audit %s bytes=%d bar-override=%s" % (name, os.path.getsize(path), bool(bar_text)))
        print("[dry] seat=%s model=%s ZERO door calls" % (_door(SEAT), MODEL))
        return 0
    res = {}
    for name, path in rows:
        try:
            piece = open(path, encoding="utf-8").read()
        except UnicodeDecodeError:
            print("REFUSE: piece not UTF-8: %s (rc2)" % path); return 2  # piece-decode gate cure
        a = ask(piece, bar_text)
        if not a["ok"]:
            res[name] = {"ok": False, "err": a["err"]}
            print("named door result: %s -> %s" % (name, a["err"][:120])); continue
        bar, verdict = parse_verdict(a["text"])
        res[name] = {"ok": True, "bar": bar, "verdict": verdict, "raw": a["text"]}
        print("audit %s -> %s %s" % (name, verdict, bar))
    # tally gate cure: UNPARSED and door-errors are named, never tallied; raw always stored above.
    parsed = [r for r in res.values() if r.get("ok") and r["bar"] != "UNPARSED" and r["verdict"] != "UNPARSED"]
    unparsed = sum(1 for r in res.values() if r.get("ok") and (r["bar"] == "UNPARSED" or r["verdict"] == "UNPARSED"))
    errs = sum(1 for r in res.values() if not r.get("ok"))
    def _cnt(k, v): return sum(1 for r in parsed if r[k] == v)
    print("SUMMARY pieces=%d parsed=%d unparsed=%d door-errors=%d admit=%d admit-with-note=%d hold=%d bar_met=%d bar_not_met=%d" % (
        len(res), len(parsed), unparsed, errs,
        _cnt("verdict", "ADMIT"), _cnt("verdict", "ADMIT-WITH-NOTE"), _cnt("verdict", "HOLD"),
        _cnt("bar", "BAR_MET"), _cnt("bar", "BAR_NOT_MET")))
    if not out:
        out = os.path.join(HOME, "scripts", "census", "bar-audit-%s.json" % stamp.replace(":", "").replace("-", ""))
    d = os.path.dirname(out)
    if d: os.makedirs(d, exist_ok=True)
    try:
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        # keep-first collision cure: named result, first copy intact, never a traceback
        print("KEEP-FIRST collision: %s -- first copy intact, not overwritten (rc0)" % out)
        return 0
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"stamp": stamp, "seat": _door(SEAT), "model": MODEL, "results": res}, f, indent=1)
    print("store (keep-first):", out)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:
        # dispatch-wrap cure: a traceback never escapes the organ
        print("REFUSE: %s: %s (rc5)" % (type(e).__name__, str(e)[:200]))
        sys.exit(5)
