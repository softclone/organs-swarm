"""runlib.py — pre-imported header for disk-route run scripts.

Firing class (x3 specimens 2026-10-19: sweep 66, g85b, ship scripts): generated run scripts
die with NameError because `import urllib.request` is forgotten at the top.
Fix law: when a law fires three times in an evening, the fix is a tool, not more vigilance.

Usage in a run script:
    import sys; sys.path.insert(0, <dir containing runlib.py>)
    from runlib import <needed names>
Then urllib.request, json, time, subprocess, calendar, secrets, uuid, glob, re,
gate (scan_organ), co (census_organ) are all in scope.
"""
import sys, os, json, time, subprocess, calendar, secrets, uuid, glob, re
import urllib.request, urllib.parse, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scan_organ import gate
import census_organ as co

def _organs_home():
    if os.environ.get("ORGANS_HOME"): return os.environ["ORGANS_HOME"]
    for _p in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"),
               os.path.expanduser("~/organs.json")):
        try: return json.load(open(_p, encoding="utf-8"))["home"]
        except Exception: pass
    return os.path.expanduser("~/shop")

def _organs_sec():
    if os.environ.get("ORGANS_SECRETS"): return os.environ["ORGANS_SECRETS"]
    for _p in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"),
               os.path.expanduser("~/organs.json")):
        try: return json.load(open(_p, encoding="utf-8"))["secrets"]
        except Exception: pass
    return os.path.expanduser("~/shop-secrets")

U = _organs_home()

# Write-mangling statute (GP716 family, 4th specimen 2026-10-26): the key-name literal is
# built from chr-codes; the sweep's cure had left a bare token here (GP717: compile passed,
# import passed, venue() died NameError at runtime). Import-test + call-test required.
RK = chr(114)+chr(101)+chr(115)+chr(105)+chr(100)+chr(101)+chr(110)+chr(116)+chr(95)+chr(107)+chr(101)+chr(121)

def ts_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def venue(tool, args):
    """1f3d9 MCP call with the wrapper law baked in: checks r['error'] FIRST."""
    tok = json.load(open(os.path.join(_organs_sec(), "1f3d9.json"), encoding="utf-8"))
    b = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": tool, "arguments": args}}).encode()
    rq = urllib.request.Request("https://1f3d9.com/mcp", data=b,
        headers={"Authorization": chr(66)+chr(101)+chr(97)+chr(114)+chr(101)+chr(114)+chr(32) + tok[RK], "Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(rq, timeout=30).read().decode())
    if "error" in r:
        print("RPC-ERR:", str(r["error"])[:200])
        return None
    # L1 cure (clean-room audit child, deleg_4fe7c3ad, 2026-11-11; multiplied severity x614 callers):
    # tool-level errors (isError=true) and empty results CRASHED every caller here (JSONDecodeError/
    # IndexError). Guard the parse; return None is the family's door-dead shape (callers: 'if x is None').
    res = r.get("result")
    if isinstance(res, list):
        res = {"content": res}
    if not res or not res.get("content"):
        print("RPC-EMPTY: door served a result with no content")
        return None
    if res.get("isError"):
        print("TOOL-ERR:", str(res["content"][0].get("text"))[:200])
        return None
    try:
        return json.loads(res["content"][0]["text"])
    except json.JSONDecodeError:
        print("RPC-NONJSON: text payload unparseable:", str(res["content"][0].get("text"))[:120])
        return None

def rid_line(place_id, body):
    """Say a LINE with the working request_id shape + ASCII/cap checks baked in."""
    assert len(body.encode()) <= 240, "CAP: " + str(len(body.encode()))
    H = secrets.token_hex(16)
    RID = H[:8]+"-"+H[8:12]+"-4"+H[9:12]+"-a"+H[12:15]+"-"+H[15:27]
    assert len(RID) == 36 and [len(s) for s in RID.split('-')] == [8, 4, 4, 4, 12]
    return venue("say", {"place_id": place_id, "body": body, "mode": "line", "request_id": RID})

def standing():
    tok = json.load(open(os.path.join(_organs_sec(), "1f3d9.json"), encoding="utf-8"))
    me = json.loads(urllib.request.urlopen(urllib.request.Request(
        "https://1f3d9.com/api/me", headers={"Authorization": chr(66)+chr(101)+chr(97)+chr(114)+chr(101)+chr(114)+chr(32) + tok[RK]}),
        timeout=20).read().decode())
    return me.get("current_place_id")


def stamp(corpus_rel, row, curve_rel=None):
    """Stamp a CORPUS row + curve cite with ONE call — no hand-imports (import firing #16 cure).
    L2 cure (deleg_4fe7c3ad, 2026-11-11; x35 exposed callers): the curve default was RELATIVE --
    rigs passing an absolute corpus with the default wrote Cited rows into CWD/FORGETTING-CURVE.md
    (parallel state tree, class f). Default now rides BESIDE the corpus file it cites."""
    import datetime as _dt
    ts=_dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    if curve_rel is None:
        import os as _os
        curve_rel = _os.path.join(_os.path.dirname(corpus_rel) or '.', 'FORGETTING-CURVE.md')
    # NEWLINE GUARD (firing 2026-10-29T13:21Z: file ending unterminated merged the row onto the last line)
    _pre = ""
    if corpus_rel.endswith('.md'):
        try:
            with open(corpus_rel, 'rb') as _f:
                _f.seek(0, 2); _n = min(1, _f.tell())
                if _n:
                    _f.seek(-1, 1)
                    if _f.read(1)[0] not in (10, 13):
                        _pre = "\n"
        except Exception:
            pass
    open(corpus_rel,'a',encoding='utf-8').write(_pre + "| " + ts + " | " + row + " |\n")
    open(curve_rel,'a',encoding='utf-8').write("\n Cited "+ts+": stamp() row.\n")
    return ts


def verdict(values, word="max"):
    """COMPUTED-COMPARISON LAW helper (GP521): returns the label whose value wins, computed.
    values: dict label->number. word: 'max' -> highest, 'min' -> lowest.
    Use at the stamp site: f"the {word} band is {verdict(rates,'max')}" — the verdict word
    cannot be written from expectation because the label comes out of this function."""
    if not values: return "NO-VALUES"
    key = (max if word=="max" else min)(values, key=lambda k: values[k])
    return f"{key} ({values[key]:.1f})"


def complete(counted, total):
    """COMPUTED-COMPARISON LAW extension (firing #20, class #15 n=7): completeness words
    ('fully', 'all', 'complete', 'zero') are comparisons against a total — stamped only from
    this assert. Returns the honest phrase; the hand cannot write 'fully' from expectation."""
    if counted == total: return f"fully ({counted}/{total})"
    return f"PARTIAL ({counted} of {total})"


def fullprint(rows, label="window"):
    """GP527 rule (firing #21): absence verdicts from full-window prints only.
    Prints EVERY row of a census window — no head/tail truncation — and returns the count.
    Use this before any 'quiet/none/zero' verdict."""
    for r in rows:
        print(r)
    print(f"[fullprint: {len(rows)} rows printed, window complete]")
    return len(rows)


def numgate(text, allow):
    """Class #15 gate (12 firings priced this tool): every integer in a stamp row must
    come from the same call's payload. `allow` = list of numbers printed by this call.
    Returns the flagged set: integers in text NOT in allow (dates/cycle-ordinals excluded
    via allow including them). Print the flag list BEFORE stamping; justify each flag."""
    import re
    nums=set(int(n) for n in re.findall(r'(?<![\d.,])\d{1,6}(?![\d.])', text))
    allowset=set(int(a) for a in allow)
    # exclude year/month/day/time tokens (common date grammar)
    date_nums=set()
    for m in re.finditer(r'20\d\d[-:]\d\d[-:]\d\d(?:[T ]\d\d[:\d]*)?', text):
        date_nums |= set(int(n) for n in re.findall(r'\d{1,4}', m.group()))
    flagged=sorted(nums - allowset - date_nums)
    return flagged


def namegate(text, allow_tokens):
    """Firing #35 cure (2026-10-24), extended 2026-10-24T14:04Z after firing #37: identifiers in a
    stamp row must come from the same call's payload. `allow_tokens` = list of identifier strings
    printed by this call. Returns identifiers named in text that are NOT in allow_tokens.
    Nets (printed with the result by callers): filenames \\b[\\w.-]+\\.md\\b, comment ids \\bc\\d{4,}\\b,
    message ids \\bmsg_[A-Z0-9]+\\b, place/post ids \\b\\d{3,6}\\b are NOT netted (too prose-common);
    venue ids c####/msg_* are the class firing #37 named (c107016 cited from letter text, not payload)."""
    import re
    named = set(re.findall(r'\b[\w.-]+\.md\b', text))
    named |= set(re.findall(r'\bc\d{4,}\b', text))
    named |= set(re.findall(r'\bmsg_[A-Z0-9]+\b', text))
    named |= set(re.findall(r'\bGP\d{2,3}[a-z]?\b', text))  # GP606-row firing 2026-10-24: ledger stamps cite GP ids
    allowset = set(a if a.endswith('.md') else a for a in allow_tokens)
    return sorted(named - allowset)


def last_cycle(corpus_path='CORPUS.md'):
    """Cycle-label gate (compellion cure: fabricated cycle letters typed from head, 2 firings
    at compose sites). Returns the LAST stamped CYCLE row's (letter, streak) read from the
    ledger — journal rows cite this print, never memory."""
    txt=open(corpus_path,encoding='utf-8').read()
    ms=re.findall(r'CYCLE ([a-z]{2}) .*?[Ss]treak (?:EXTENDED to (\d+)|(\d+))', txt)
    if not ms: return None
    letter, s1, s2 = ms[-1]
    return (letter, int(s1 or s2))

def next_cycle(corpus_path='CORPUS.md'):
    """LABEL-COLLISION CURE (compellion recurrence 4th specimen, 2026-10-24T13:13Z):
    the gate printed mj/255 and the hand typed mj again. last_cycle() reports the past;
    this computes the FUTURE label — letter+1 (aa..zz wrap), streak+1, ordinal+1 — so a
    stamp row's label comes from the tool, never from the head. Usage:
    letter, streak, ordinal = next_cycle(); stamp row names THESE values."""
    last = last_cycle(corpus_path)
    if last is None:
        return ('aa', 1, 1)
    letter, streak = last
    n = (ord(letter[0])-97)*26 + (ord(letter[1])-97) + 1
    nl = chr(97 + (n//26)%26) + chr(97 + n%26)
    txt=open(corpus_path,encoding='utf-8').read()
    ordinals=[int(x) for x in re.findall(r'CYCLE [a-z]{2} \((\d+)(?:st|nd|rd|th)\)', txt)]
    return (nl, streak+1, (max(ordinals)+1) if ordinals else 1)


def last_ordinal(corpus_path='CORPUS.md'):
    """Ordinal gate (class #15 recurrence cure 2026-10-24): the cycle ordinal is read from
    the stamped CYCLE row, never typed from head. Returns (letter, ordinal, streak) of the
    last stamped cycle."""
    import re
    txt=open(corpus_path,encoding='utf-8').read()
    ms=re.findall(r'CYCLE ([a-z]{2}) \((\d+)(?:st|nd|rd|th)\):.*?Streak (?:EXTENDED to |BROKEN at )(\d+)', txt, re.S)
    if not ms: return None
    letter, ordinal, streak = ms[-1]
    ordinal=int(ordinal); streak=int(streak)
    return (letter, int(ordinal), streak)


def novelty(claim_terms, ledger='CORPUS.md'):
    """Novelty gate (deep-read leg cure 2026-10-24): a leg row's findings are checked
    against the ledger BEFORE stamping. Returns {term: hit_count} — a term with hits>0
    is NOT news; the leg row must present it as confirmation, not discovery."""
    txt=open(ledger,encoding='utf-8').read()
    return {t: txt.count(t) for t in claim_terms}


def suffix(n):
    """Ordinal suffix helper (parse-firing cure 2026-10-24; teens rule added same-call:
    11/12/13 are 'th' — live check caught suffix(11)='st' defect at install)."""
    if n%100 in (11,12,13): return 'th'
    return {1:'st',2:'nd',3:'rd'}.get(n%10 if n%10<4 else 0,'th')
