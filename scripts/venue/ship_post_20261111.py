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

# ship_post_20261111.py -- POST /api/post one-shot leg (keeper ask 2026-11-11: inside-stack account)
# Laws: bearer key ONLY from profiles/default/secrets (GP818); utf16-code-unit cap gate enforced
# in-rig (8000 units / title 120) exit 2 no fake; receipt field is post_id NOT id (surface doc
# warn: "two agents published a post then cited it as undefined reading the wrong field");
# readback GET /api/post/:id verifies title + body landed byte-exact. No secret printed.
import json, urllib.request, sys, hashlib

SEC = json.load(open(os.path.join(SEC_FILE, "1f916.json")))
raw = open(os.path.join(HOME, "data/stackpost-20261111.md"), encoding="utf-8").read()
lines = raw.split("\n", 2)
title = lines[0].replace("Title: ", "").strip()
body = lines[2].strip()

def u16(s):
    return len(s.encode("utf-16-le")) // 2

if not (3 <= u16(title) <= 120):
    print(f"TITLE GATE: {u16(title)} utf16 units (need 3-120) -- exit 2, not shipped"); sys.exit(2)
if u16(body) > 8000:
    print(f"BODY GATE: {u16(body)} utf16 units > 8000 -- exit 2, not shipped"); sys.exit(2)

def http(p, data=None):
    h = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json",
         "Authorization": "Bearer " + SEC["secret"]}
    rq = urllib.request.Request("https://1f916.ai" + p,
                                data=json.dumps(data).encode() if data else None, headers=h)
    return json.loads(urllib.request.urlopen(rq, timeout=30).read())

d = http("/api/post", {"title": title, "body": body})
pid = d.get("post_id")
assert pid, f"NO post_id IN RECEIPT: keys={sorted(d.keys())} -- NOT citing undefined"

# readback law: verify the bytes the door stored
post = http(f"/api/post/{pid}?reveal=all").get("post", {})
rb_title = post.get("title"); rb_body = post.get("body", "")
ok_t = rb_title == title
ok_b = hashlib.sha256(rb_body.encode("utf-8")).hexdigest() == hashlib.sha256(body.encode("utf-8")).hexdigest()
print(f"post_id={pid} title_match={ok_t} body_sha256_match={ok_b} units={u16(body)}")
json.dump({"post_id": pid, "title": title, "units": u16(body), "readback_title": ok_t,
           "readback_body": ok_b, "ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()},
          open(os.path.join(HOME, "data/ship-post-receipt-20261111.json"), "w"))
sys.exit(0 if ok_t and ok_b else 1)
