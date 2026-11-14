# seat_score.py -- Tier-2 standard distilling the scoring family (_pile_score* 54 + _score_batch* 24 = 78 one-off copies).
# FAMILY CENSUS: 78 one-offs distilled into this organ (the estate copies stay READ-ONLY history).
# Multi-seat binary scoring of shop pieces with the parse gate IN CODE (the copies carried firing #75 as a comment).
# Verbs:
#   score --pieces "name=PATH,name=PATH" [--ask TEMPLATE.txt] [--out PATH] [--dry]
#   --dry: file existence + byte census + template shape, ZERO seat calls, rc0.
# Gates in code:
#   parse3: require cond1/cond2/cond3 all present as <digit 0|1>, else PENDING -- raw always stored,
#           PENDING rows never enter triples (firing #75 law).
#   keep-first (GP534): window-stamped store files written with O_EXCL -- a run never overwrites the first copy.
#   max_tokens floor 131072 asserted in ask() (family habit rode 2000 -- cured at the organ).
#   door-path: a bare-base seat_url gets /v1/chat/completions appended (config seats ride bare bases).
#   non-JSON door bodies named per CATCHES 302 law (ok:false head, never json.loads death).
# CURES over the proven skeleton (named; fired in suite leg seat-score-gates):
#   door-answer surfacing cure: ask()'s ok:false head (NON-JSON body / unreadable DOOR-SHELL) lands in
#     the result as a named error -- the skeleton read out["text"] unconditionally and lost the head
#     to KeyError:'text'; a JSON shell without choices died as KeyError:'choices'. Both named at ask().
#   arg-shape gate cure: --pieces entries must be name=PATH; a flag missing its value or a missing
#     --ask template REFUSES rc2 before any door -- the skeleton crashed ValueError/IndexError/
#     FileNotFoundError on those shapes (loud-named law: the run never dies unnamed).
# DATUMS (deploy lessons kept as prose -- zero estate literals in code):
#   (1) config-chain locality: a runner placed in SCRATCH cannot see the shop's scripts/local.json;
#       seat_url/seat_model pins live BESIDE the rig in scripts/. Deploy position matters for config
#       resolution. The old default seat on port 8080 is dead; the estate door that proved this
#       skeleton lived on port 47831 as a bare base URL (the door-path gate above appends the path).
#   (2) family habit maxtok 2000 cured at the 131072 floor.
# Default questionnaire (the shop's three conditions; override with --ask):
#   cond1 concrete scene present / cond2 force: says something you cannot un-hear / cond3 a reader could act on tomorrow.
# Config chain (portable, zero estate literals, zero secret values):
#   HOME = ORGANS_HOME env > local.json beside > ~/organs.json
#   seat = ORGANS_SEAT_URL env > seat_url config (chat-completions door)
#   model = seat_model config > "local-seat"
#   extra seats = score_seats config: [{name, url, model}] (none required locally)
import json, os, sys, re, time, urllib.request

def _cfg_dir(): return os.path.dirname(os.path.abspath(__file__))
def _home():
    if os.environ.get("ORGANS_HOME"): return os.environ["ORGANS_HOME"]
    for p in (os.path.join(_cfg_dir(), "local.json"), os.path.expanduser("~/organs.json")):
        if os.path.exists(p):
            try: return json.load(open(p, encoding="utf-8")).get("home", os.path.expanduser("~/shop"))
            except Exception: continue
    return os.path.expanduser("~/shop")
def _key(k, dflt=None):
    for p in (os.path.join(_cfg_dir(), "local.json"), os.path.expanduser("~/organs.json")):
        if os.path.exists(p):
            try:
                v = json.load(open(p, encoding="utf-8")).get(k)
                if v: return v
            except Exception: continue
    return dflt

HOME = _home()
SEAT = os.environ.get("ORGANS_SEAT_URL") or _key("seat_url", "http://127.0.0.1:8080/v1/chat/completions")
MODEL = _key("seat_model", "local-seat")
MAXTOK = 131072

ASK_HEAD = ("Score this short text on three conditions. For each condition choose the digit 0 or the digit 1 "
 "(1 = condition met, 0 = not met). Do NOT copy the example format; write your own chosen digit after each equals sign.\n"
 "Answer with exactly three lines:\ncond1=<your digit>\ncond2=<your digit>\ncond3=<your digit>\n\n"
 "cond1: a concrete scene is present on the page (not an explanation of a practice).\n"
 "cond2: the text carries force - it says something you cannot un-hear, not a restatement.\n"
 "cond3: a reader could act on it tomorrow (a practice, a check, a rule) without asking the author what they meant.\n\nTEXT:\n")

def _door(url):
    # door-path law: config may carry a bare base (host[:port] with no path) -- append the completions path.
    from urllib.parse import urlsplit
    u = urlsplit(url)
    if not u.path or u.path == "/":
        return url.rstrip("/") + "/v1/chat/completions"
    return url

def ask(prompt, url=None, model=None, maxtok=MAXTOK):
    assert maxtok >= 131072, "keeper law: max_tokens floor 131072"
    body = {"model": model or MODEL, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": maxtok, "temperature": 0.3}
    req = urllib.request.Request(_door(url or SEAT), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    raw = urllib.request.urlopen(req, timeout=240).read()
    try:
        d = json.loads(raw.decode())
    except Exception:
        # CATCHES 302 law: doors may serve non-JSON (Cloudflare/rate walls) -- name it, never die in json.loads
        return {"ok": False, "err": "NON-JSON body head=" + raw[:120].decode("utf-8", "replace"),
                "s": round(time.time() - t0, 1)}
    try:
        msg = d["choices"][0]["message"]
        text = (msg.get("content") or msg.get("reasoning_content") or "").strip()
    except Exception:
        # door-answer surfacing cure: a JSON shell without a readable choices/message is named, not KeyError
        return {"ok": False, "err": "DOOR-SHELL head=" + raw[:120].decode("utf-8", "replace"),
                "s": round(time.time() - t0, 1)}
    return {"ok": True, "text": text, "s": round(time.time() - t0, 1)}

def parse3(txt):
    m = re.findall(r"cond(\d)\s*=\s*([01])", txt)
    d = {int(a): int(b) for a, b in m}
    if all(k in d for k in (1, 2, 3)):
        return (d[1], d[2], d[3]), True
    return None, False

def keep_first(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    return True

def main():
    argv = sys.argv[1:]
    dry = "--dry" in argv
    if not argv or argv[0] != "score":
        print("REFUSE: verb score required"); return 2
    pieces, askf, outp = [], None, None
    for i, x in enumerate(argv):
        if x in ("--pieces", "--ask", "--out") and i + 1 >= len(argv):
            print("REFUSE:", x, "needs a value"); return 2  # arg-shape gate cure: never IndexError
        if x == "--pieces":
            pieces = [tuple(p.split("=", 1)) for p in argv[i + 1].split(",")]
        if x == "--ask": askf = argv[i + 1]
        if x == "--out": outp = argv[i + 1]
    for spec in pieces:
        if len(spec) != 2 or not spec[0] or not spec[1]:
            print("REFUSE: --pieces entries must be name=PATH"); return 2  # arg-shape gate cure: never ValueError
    if askf and not os.path.exists(askf):
        print("REFUSE: --ask template missing:", askf); return 2  # arg-shape gate cure: never FileNotFoundError
    head = open(askf, encoding="utf-8").read() if askf else ASK_HEAD
    seats = [("local", SEAT, MODEL)] + [(s["name"], s["url"], s.get("model"))
                                         for s in (_key("score_seats", []) or [])]
    allr = {}
    for name, path in pieces:
        if not os.path.exists(path):
            print("MISSING", path); allr[name] = {"error": "missing file"}; continue
        body = open(path, encoding="utf-8").read()
        if dry:
            allr[name] = {"bytes": len(body.encode()), "seats": len(seats)}
            print(name, "DRY bytes=", len(body.encode()), "seats=", len(seats)); continue
        res = {}
        for sname, surl, smod in seats:
            try:
                out = ask(head + body, url=surl, model=smod)
                if not out.get("ok"):
                    # door-answer surfacing cure: the named head lands in the result, never KeyError:'text'
                    res[sname] = {"error": out.get("err", "door unreadable")}
                    print(name, sname, "ERR", str(out.get("err", ""))[:120]); continue
                txt = out["text"]
                triple, ok = parse3(txt)
                res[sname] = {"triple": triple, "complete": ok}
                wtag = time.strftime("%Y%m%dT%H%M%S")
                keep_first(os.path.join(HOME, "scripts", "census",
                                        f"score-{name}-{sname}-{wtag}.json"),
                           {"piece": name, "seat": sname, "raw": txt, "triple": triple,
                            "complete": ok, "measured_bytes": len(body.encode()), "s": out["s"]})
                print(name, sname, triple, "COMPLETE" if ok else "PENDING")
            except Exception as e:
                res[sname] = {"error": type(e).__name__ + ":" + str(e)[:120]}
                print(name, sname, "ERR", type(e).__name__)
        allr[name] = res
    if dry:
        print("DRY-PLAN pieces=", len(pieces), "seats=", len(seats), "zero seat calls")
        return 0
    outp = outp or os.path.join(HOME, "scripts", "census", "seat-score-run.json")
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    json.dump(allr, open(outp, "w", encoding="utf-8"), indent=1)
    pend = sum(1 for r in allr.values() for v in r.values()
               if isinstance(v, dict) and v.get("complete") is False)
    missing = sum(1 for r in allr.values() for v in r.values()
                  if isinstance(v, str) or "error" in v)
    print("STORE:", outp, "pieces=", len(allr), "pending=", pend, "missing/errors=", missing)
    return 0

if __name__ == "__main__":
    sys.exit(main())
