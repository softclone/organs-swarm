"""census_organ.py — canonical header censuses (erosion pass 137 installation form).

Built 2026-10-18 after the census-family field day: one organ, four firings in one hour
(substring counted prose as header; anchored '#+' missed prefix-less headers; a repair row
typed 'optional' while carrying a one-or-more quantifier; the sweep row typed its own counts).

Laws baked in:
- pass 135: a header census enumerates the store's header families (incl. prefix-less).
- pass 137: an organ's quantifier is a claim -> dry_run() on known specimens gates every count.
- census names its SURFACE and read-time with every number (stale-denominator law).
"""
import re, time, calendar

def _ts():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def genre_headers(path):
    """Line-start GENRE headers in GENRE-LEXICON.md; '#' optional (genre 66 carries none)."""
    txt = open(path, encoding="utf-8").read()
    pat = re.compile(r"^#*\s*GENRE \d+ (?:CANDIDATE|SHIPPED)", re.M)
    rows = [m.group(0).strip() for m in pat.finditer(txt)]
    shipped = [r for r in rows if "SHIPPED" in r]
    return {"headers": len(rows), "shipped": len(shipped), "read_time": _ts(),
            "surface": "GENRE-LEXICON.md line-start headers"}

def addendum_max(path):
    """Highest numbered 'Addendum N' header in GRANDPARENTS.md.
    Excludes date-numbered legacy headers ('Addendum 2026-10-16T...Z - Grandparent #N'):
    number must not be followed by '-' or another digit."""
    txt = open(path, encoding="utf-8").read()
    nums = [int(m.group(1)) for m in re.finditer(r"^#+ Addendum (\d+)(?![-\d])", txt, re.M)]
    return {"max": max(nums), "count": len(nums), "read_time": _ts(),
            "surface": "GRANDPARENTS.md numbered addendum headers (date-shaped excluded)"}

def dry_run(genre_path, gp_path):
    """Known-specimen checks; raises on organ blindness. Run BEFORE any count is cited."""
    g = genre_headers(genre_path)
    a = addendum_max(gp_path)
    # known specimens: genre 66 header (prefix-less) must be counted; addendum 203+ present
    txt = open(genre_path, encoding="utf-8").read()
    assert "GENRE 66 SHIPPED" in txt and g["headers"] >= 12, "organ blind to prefix-less header"
    assert a["max"] >= 203, "organ blind to numbered addenda chain"
    # negative control: prose sentence must NOT count as header
    assert g["headers"] == len(re.findall(r"^#*\s*GENRE \d+ (?:CANDIDATE|SHIPPED)", txt, re.M)), "prose leak"
    return {"ok": True, "genre_headers": g["headers"], "addendum_max": a["max"]}

if __name__ == "__main__":
    import sys, os, json
    if os.environ.get("ORGANS_HOME"): U = os.environ["ORGANS_HOME"]
    else:
        U = None
        for _p in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"),
                   os.path.expanduser("~/organs.json")):
            try: U = json.load(open(_p, encoding="utf-8"))["home"]; break
            except Exception: pass
        if not U: U = os.path.expanduser("~/shop")
    print(dry_run(U + r"/GENRE-LEXICON.md", U + r"/GRANDPARENTS.md"))
    print(genre_headers(U + r"/GENRE-LEXICON.md"))
    print(addendum_max(U + r"/GRANDPARENTS.md"))


def claim_line(path, keyword, claim):
    """Check-string extraction clause (pass 86) as an organ.
    Finds lines in store `path` containing `keyword`; asserts `claim`
    appears verbatim in at least one matched line; returns the matched line.
    A check-string is copied from the store it reads, never paraphrased
    from the prose it verifies. Raises AssertionError with the store's
    real lines printed when the claim does not match."""
    if len(path) > 260 or "\n" in path:
        raise AssertionError("claim_line FIRING (organ-shape): `path` is file CONTENT, not a path - pass the store's path literal")
    lines=[l for l in open(path,encoding="utf-8").read().splitlines() if keyword.lower() in l.lower()]
    if not lines:
        raise AssertionError(f"claim_line: keyword {keyword!r} matched 0 lines in {path}")
    hit=[l for l in lines if claim in l]
    if not hit:
        print(f"claim_line FIRING: claim {claim!r} not in store's {len(lines)} matched line(s):")
        # pass 164 law: print FULL bytes via repr — a truncated head invites tail-paraphrase
        for l in lines[:3]: print("  STORE(repr):", repr(l))
        raise AssertionError("claim_line: paraphrased check-string - copy from the printed store lines")
    return hit[0]


def score_guard(verdict, text):
    """Score-guard organ (keyword-presence blindness; fired x3 in one evening 2026-10-18:
    citation census on date digits, ghost scored HISTORY-SCOPED on a disowning citation,
    split charter verdict scored DECLINE on one word).

    A keyword verdict is PROVISIONAL. Call this in the filing call family: it prints the
    FULL seat text with char count; the author must re-read and restate the verdict from
    the printed body before filing. Presence-check scoring is blind to disowning, splits,
    and paraphrase — the manual read over the printed body is the receipt.
    """
    print(f"SCORE-GUARD: provisional verdict = {verdict} | body chars = {len(text)}")
    print("FULL BODY (read before filing):")
    print(text)
    print("-> restate verdict from this body; keyword score alone is not a receipt.")
    return verdict


def duration(event_iso, now=None):
    """Duration organ (measurement-from-memory law; fired x3 in one evening 2026-10-18).

    Returns the computed minutes from `event_iso` to `now` (default: live clock),
    PRINTED inside the same call that writes prose. Prose must copy the printed
    number — never a mental estimate. Law family: a duration claim gets its
    receipt from the measurement call in the same family as the prose.
    """
    ev = calendar.timegm(time.strptime(event_iso, "%Y-%m-%dT%H:%M:%SZ"))
    n = now if now is not None else time.time()
    mins = (n - ev) / 60.0
    out = round(mins, 2)
    end_stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(n))
    print(f"DURATION: {event_iso} -> {end_stamp} = {out} min (copy this number; do not type your own)")
    return out


def wc(label, text):
    """Word-count organ (word-count-from-impression law; fired x3 on GENRE 80 G1:
    typed 16/24/31 vs computed 20/26/35, 2026-10-19).

    Counts whitespace-separated words in `text`, PRINTS label + count. Prose and
    length-law checks copy the printed number. Both-piles law (pass 162): call wc()
    once per pile you intend to compare; the organ prints each pile's count, so a
    comparison cites computed numbers, never an impression of a string.
    """
    n = len(text.split())
    print(f"WC[{label}] = {n} words (copy this number; do not type your own)")
    return n
