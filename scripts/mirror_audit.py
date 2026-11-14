# mirror_audit.py -- Tier-2 standard distilling family _mirror_audit_batch*.py (317 copies, 317 distinct md5s).
# FAMILY CENSUS: 317 one-offs distilled into this organ (the estate copies stay READ-ONLY history).
# Cold seat audit of shop pieces, admission-runs form (R3 revival, GP719/GP739/GP740 gates IN CODE, not comments).
# VERBS:
#   --files "rel1.md,rel2.md"  |  --glob "canon/eros/eros-15*.md"  |  --batch N (reads census/mirror-audit-batchN.json FILES keys)
#   --out PATH   (default HOME/scripts/census/mirror-audit-<stamp>.json)
#   --dry        (plan only: list rows, bar-discovery results, gates -- ZERO seat calls)
# GATES (enforced, not recited):
#   GP739 PARSE GATE: verdict row without reason-sentence -> UNPARSED, re-roll (cap 2); never store a groundless verdict.
#   GP740 GATE 2: piece header says NO BAR / record-only -> ACT-ONLY verdict (BAR tally untouched).
#   GP719 BAR AUTO-DISCOVER: '**Bar:** <text>' in piece -> BAR_MET/BAR_NOT_MET line demanded.
#   max_tokens floor 131072 (keeper law; the 317 old copies rode 128000 -- cured at the organ default).
# CONFIG CHAIN (no estate literals): HOME = ORGANS_HOME env > local.json beside > ~/organs.json.
#   seat URL = ORGANS_SEAT_URL env > seat_url config > default http://127.0.0.1:8080/v1/chat/completions
#   model name = seat_model config > "local-seat" (deployed local.json pins the real seat model)
import json, os, sys, re, glob as _glob, urllib.request, time

def _cfg():
    if os.environ.get("ORGANS_HOME"): return os.environ["ORGANS_HOME"]
    for p in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"),
              os.path.expanduser("~/organs.json")):
        if os.path.exists(p):
            try: return json.load(open(p, encoding="utf-8")).get("home", os.path.expanduser("~/shop"))
            except Exception: continue
    return os.path.expanduser("~/shop")

def _key(k, dflt=None):
    for p in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"),
              os.path.expanduser("~/organs.json")):
        if os.path.exists(p):
            try:
                v = json.load(open(p, encoding="utf-8")).get(k)
                if v: return v
            except Exception: continue
    return dflt

HOME = _cfg()
SEAT = os.environ.get("ORGANS_SEAT_URL") or _key("seat_url", "http://127.0.0.1:8080/v1/chat/completions")
MODEL = _key("seat_model", "local-seat")
MAXTOK = 131072  # keeper law floor -- never lower

def ask(prompt, maxtok=MAXTOK):
    assert maxtok >= 131072, "keeper law: max_tokens floor 131072"
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": maxtok, "temperature": 0.3}
    req = urllib.request.Request(SEAT, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=240).read().decode())
        msg = d["choices"][0]["message"]
        return {"ok": True, "text": (msg.get("content") or msg.get("reasoning_content") or "").strip(),
                "s": round(time.time()-t0, 1)}
    except Exception as e:
        return {"ok": False, "err": str(e)[:200], "s": round(time.time()-t0, 1)}

def bar_of(text):
    m = re.search(r"\*\*Bar:\*\*\s*(.+)", text)
    return m.group(1).strip() if m else None

def is_record_only(text):
    head = text[:400].lower()
    return "no bar" in head or "record-only" in head

def parse_gate(text):
    # GP739: line1 verdict token + line2 reason sentence, else UNPARSED
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) < 2: return None
    v = None
    for tok in ("ADMIT-WITH-NOTE", "ADMIT", "HOLD"):
        if tok in lines[0].upper(): v = tok; break
    if not v: return None
    if len(" ".join(lines[1:])) < 25: return None  # groundless verdict
    bm = None
    if "BAR_MET" in " ".join(lines).upper(): bm = "BAR_MET"
    if "BAR_NOT_MET" in " ".join(lines).upper(): bm = "BAR_NOT_MET"
    return {"verdict": v, "reason": " ".join(lines[1:]), "bar": bm}

def main():
    argv = sys.argv[1:]
    dry = "--dry" in argv
    files = []
    out = os.path.join(HOME, "scripts", "census", time.strftime("mirror-audit-%Y%m%dT%H%M%S.json"))
    for i, a in enumerate(argv):
        if a == "--files": files = [f.strip() for f in argv[i+1].split(",") if f.strip()]
        if a == "--glob":  files = sorted(_glob.glob(os.path.join(HOME, argv[i+1])))
        if a == "--out":  out = argv[i+1]
        if a == "--batch":
            src = os.path.join(HOME, "scripts", "census", f"mirror-audit-batch{argv[i+1]}.json")
            if not os.path.exists(src): print("NO-REGISTRY", src); return 4
            files = list(json.load(open(src, encoding="utf-8")).keys())
    if not files:
        print("REFUSE: no files (--files/--glob/--batch)"); return 2
    rows = {}
    for rel in files:
        p = rel if os.path.isabs(rel) else os.path.join(HOME, rel)
        if not os.path.exists(p):
            rows[rel] = {"ok": False, "err": "missing file"}; print(rel, "MISSING"); continue
        text = open(p, encoding="utf-8").read()
        bar = bar_of(text); act_only = is_record_only(text)
        plan = {"bar": bar, "act_only": act_only}
        if dry:
            rows[rel] = {"ok": None, "plan": plan}; print(rel, "DRY bar=", bool(bar), "act-only=", act_only); continue
        prompt = ("You are the Mirror, cold-auditing a shop piece for admission. "
                  "Answer in exactly two lines. Line 1: VERDICT = ADMIT / ADMIT-WITH-NOTE / HOLD. "
                  "Line 2: one sentence - what the piece DOES to a reader (an act, not a summary), and whether it lands.")
        if act_only:
            prompt += " This piece is record-only: judge the ACT only; print BAR_NOT_MET on line 1."
        elif bar:
            prompt += " BAR to test: " + bar + " Line 1 must also print BAR_MET / BAR_NOT_MET."
        prompt += "\n\nFILE: " + rel + "\nBODY:\n" + text
        rec = ask(prompt)
        parsed = parse_gate(rec.get("text", "")) if rec["ok"] else None
        rerolls = 0
        while rec["ok"] and parsed is None and rerolls < 2:
            rerolls += 1; rec = ask(prompt); parsed = parse_gate(rec.get("text", ""))
        rows[rel] = {"ok": rec["ok"], "s": rec.get("s"), "raw": rec.get("text", rec.get("err", "")),
                     "parsed": parsed, "rerolls": rerolls,
                     "gate": "ACT-ONLY" if act_only else ("BAR" if bar else "PLAIN"),
                     "unparsed_final": parsed is None}
        print(rel, rec["ok"] and (parsed["verdict"] if parsed else "UNPARSED") or "ERR", rec.get("s", "?"), "s")
    if dry:
        print("DRY-PLAN rows=", len(rows), "bars=", sum(1 for r in rows.values() if r.get("plan", {}).get("bar")),
              "act-only=", sum(1 for r in rows.values() if r.get("plan", {}).get("act_only")))
        return 0
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f: json.dump(rows, f, ensure_ascii=False, indent=1)
    unp = sum(1 for r in rows.values() if r.get("unparsed_final"))
    print("STORE:", out, "rows=", len(rows), "unparsed=", unp, "seat-calls logged")
    return 0

if __name__ == "__main__":
    sys.exit(main())
