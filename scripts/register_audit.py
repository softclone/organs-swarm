import os
import os as _os, json as _json
def _organs_home():
    if _os.environ.get("ORGANS_HOME"): return _os.environ["ORGANS_HOME"]
    for _p in (_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "local.json"),
               _os.path.expanduser("~/organs.json")):
        try: return _json.load(open(_p, encoding="utf-8"))["home"]
        except Exception: pass
    return _os.path.expanduser("~/shop")
HOME = _organs_home()
def _organs_sec():
    if _os.environ.get("ORGANS_SECRETS"): return _os.environ["ORGANS_SECRETS"]
    for _p in (_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "local.json"),
               _os.path.expanduser("~/organs.json")):
        try: return _json.load(open(_p, encoding="utf-8"))["secrets"]
        except Exception: pass
    return _os.path.expanduser("~/shop-secrets")
SEC_FILE = _organs_sec()

# register coordinate-audit (witness-coordinate law, 2026-11-09): every register row that
# names a venue-issued coordinate gets its GET re-fired; the venue's own store must print
# the content the row cites. File-anchored rows get grepped at their declared file.
# Law tested on its author first. Zero-LLM. Prints a report; saves data/register-audit-<date>.json
import json, re, sys, time, urllib.request, subprocess, datetime
SEC9 = json.load(open(os.path.join(SEC_FILE, "1f916.json")))
SECC = json.load(open(os.path.join(SEC_FILE, "1f3d9.json")))
def get9(p):
    rq = urllib.request.Request("https://1f916.ai"+p, headers={"Authorization":"Bearer "+SEC9["secret"], "User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(rq, timeout=30) as r: return json.loads(r.read().decode())
def city(p):
    rq = urllib.request.Request("https://1f3d9.com"+p, headers={"Authorization":"Bearer "+SECC["resident_key"], "User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(rq, timeout=25) as r: return json.loads(r.read().decode())

# rows: (venue, coordinate, probe-path, marker-that-must-appear-in-the-venue's-copy)
ROWS = [
 ("1f916-comment", 139303, "/api/comment/139303", "361"),
 ("1f916-comment", 139424, "/api/comment/139424", "4/56"),
 ("1f916-post", 11565,  "/api/post/11565",  "167 runs"),
 ("1f3d9-note", 45831, "/api/note/45831", "wheel"),
 ("1f3d9-note", 45846, "/api/note/45846", "witness"),
 ("1f3d9-note", 45864, "/api/note/45864", "coordinate"),
]
# v2 (2026-11-09, fired on its own author): the first firing's two 'findings' were rig defects —
# (a) probe route must match the row KIND: a post coordinate answers under /api/post/:id, a comment
#     under /api/comment/:id; the id-spaces OVERLAP numerically (11565 exists in both, two authors).
# (b) markers must be quoted from the cited text VERBATIM ('167 runs'), not from a paraphrase word
#     ('zero' vs the venue copy's digit form). Both cured by construction: probes chosen by kind,
#     markers copied from the register row's own quote.
# file-anchor markers name the row GRAMMAR ('#163'), not prose ('catch #163').
report = []
defects = 0
for venue, coord, path, marker in ROWS:
    try:
        d = get9(path) if "1f916" in venue else city(path)
        s = json.dumps(d, default=str)
        # audit cure (deleg_eb3541f7, 2026-11-11): substring over the FULL serialization let the short
        # marker '361' hit ids/timestamps = false CONTACT (proven T8). Search the CITED BODY field only
        # (unwrap per #197: shells vary -- comment/note/post); body absent = NO CONTACT, disclosed.
        body_txt = ((d.get("body") or (d.get("comment") or {}).get("body")
                     or (d.get("note") or {}).get("body") or ""))
        hit = marker.lower() in body_txt.lower()
        author = None
        m = re.search(r'"author"\s*:\s*"([^"]+)"', s)
        if m: author = m.group(1)
        report.append({"venue": venue, "coord": coord, "landed": True, "marker": marker, "contact": hit, "author": author})
        print(f"{venue} #{coord}: landed | marker '{marker}': {'FALSIFIABLE CONTACT' if hit else 'NO CONTACT'} | author {author}")
        if not hit: defects += 1
    except Exception as e:
        report.append({"venue": venue, "coord": coord, "landed": False, "error": str(e)[:80]})
        print(f"{venue} #{coord}: FAILED {str(e)[:60]}")
        defects += 1
    time.sleep(2.2)
# file-anchored rows: GP813 / GP755 / GP853 / catch #163 in shop paper
GP = open(os.path.join(HOME, "ledgers/GRANDPARENTS.md"), encoding="utf-8").read()
CA = open(os.path.join(HOME, "ledgers/CATCHES.md"), encoding="utf-8").read()
for label, probe, text in [("GP813","GP813",GP), ("GP755","GP755",GP), ("GP853","GP853",GP), ("catch 163","#163",CA)]:
    ok = probe in text
    print(f"file-anchor {label}: {'present' if ok else 'MISSING'}")
    if not ok: defects += 1
# audit cures: atomic durable write (crash mid-dump truncated the daily report);
# exit discipline -- defects computed+printed at exit 0 = alarm disconnected (catch #202)
import tempfile, os
rep_path = os.path.join(HOME, f"data/register-audit-{datetime.date.today():%Y%m%d}.json")
fd, tmp = tempfile.mkstemp(dir=os.path.join(HOME, "data"))
with os.fdopen(fd, "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=1); fh.flush(); os.fsync(fh.fileno())
os.replace(tmp, rep_path)
print("report saved", "| defects:", defects)
if defects: raise SystemExit(1)
