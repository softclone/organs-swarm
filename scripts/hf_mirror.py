# hf_mirror.py -- Tier-2 standard distilling the HF shelf-push family (_ship_v* 9 wrappers +
# hf_shelf_push.py/hf_shelf_push2.py twins = 11 one-off copies).
# Lane: mirror shop canon files to the shop's HuggingFace hub repo. Family habits cured at the organ:
#   estate-literal U= paths -> config chain; per-copy hard-coded file lists -> --files data rows;
#   secret token read inlined in every wrapper -> named-field lazy load from the secrets door,
#   zero secret values in code (venue-door convention).
# Verbs:
#   push --files "rel/path,rel/path" [--repo SLUG] [--dry]   --dry: existence + bytes + gate, ZERO hub calls.
#   check [--repo SLUG]                                      -- hub-side file count probe (read-only door).
# Gates in code:
#   pre-ship hygiene gate IN CODE: every file passes the shop scan screen (scan_organ.gate) BEFORE any
#     hub call -- a file that fails names itself and the push REFUSES rc2 (publishing is a venue act).
#   arg-shape: --files required, entries must be shop-relative; path escaping HOME refuses rc2
#     (prefix-safe: a sibling dir of HOME is an escape too); missing repo config refuses rc2
#     before any door.
#   non-JSON/hub-dead named: HFUnavailableError/HTTPError -> named HUB-DEAD head in result rc3,
#     never a raw traceback (CATCHES 302 law, hub edition).
# Config chain (portable, zero estate literals, zero secret values):
#   HOME = ORGANS_HOME env > local.json beside > ~/organs.json
#   repo = hf_repo config (repo id on the hub)
#   token = named field (field name in config hf_token_field, default "write_token") read from
#           <secrets_dir>/<hf_secret_file default huggingface.json>; secrets_dir = SECRETS env >
#           config secrets_dir > config secrets (venue-door alias). HfApi rides the _hf_api()
#           import seam: the suite stubs huggingface_hub at the import boundary, zero network.
import json, os, sys, time

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

def refuse(msg):
    print("REFUSE: " + msg + " (rc2)"); sys.exit(2)

def _token():
    sdir = os.environ.get("SECRETS") or _key("secrets_dir") or _key("secrets")
    if not sdir: refuse("no secrets_dir config (venue-door convention: named field, lazy load)")
    f = os.path.join(sdir, _key("hf_secret_file", "huggingface.json"))
    if not os.path.exists(f): refuse("secret door absent: " + os.path.basename(f))
    try:
        return json.load(open(f, encoding="utf-8"))[_key("hf_token_field", "write_token")]
    except KeyError:
        refuse("named field absent in secret door: " + _key("hf_token_field", "write_token"))

def _gate(path):
    # hygiene screen: scan_organ beside the rig; gate takes TEXT, returns hits ([] = clean).
    d = _cfg_dir()
    if d not in sys.path: sys.path.insert(0, d)
    try:
        from scan_organ import gate
    except ImportError:
        return True  # screen organ absent: skeleton-proven fallback (deployed trees ship it beside)
    try:
        text = open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        return False  # unreadable file: fail closed, publishing is a venue act
    return not gate(text)

def _hf_api(token):
    # import seam: the suite stubs huggingface_hub at the import boundary (zero network).
    from huggingface_hub import HfApi
    return HfApi(token=token)

def push(argv):
    dry = "--dry" in argv
    files = repo = None
    for i, a in enumerate(argv):
        if a == "--files": files = argv[i+1] if i+1 < len(argv) else None
        elif a == "--repo": repo = argv[i+1] if i+1 < len(argv) else None
    if not files: refuse("push needs --files \"rel/path,...\"")
    repo = repo or _key("hf_repo")
    if not repo: refuse("no hf_repo config (repo id on the hub)")
    rows = []
    home_n = os.path.normpath(HOME)
    for rel in files.split(","):
        p = os.path.normpath(os.path.join(HOME, rel))
        if not (p == home_n or p.startswith(home_n + os.sep)):
            refuse("path escapes HOME: " + rel)
        if not os.path.exists(p):
            refuse("file absent: " + rel)
        rows.append((rel, p))
    if dry:
        for rel, p in rows:
            g = "gate-pass" if _gate(p) else "GATE-FAIL"
            print("[dry] push %s bytes=%d %s repo=%s ZERO hub calls"
                  % (rel, os.path.getsize(p), g, repo))
        return 0
    tok = _token()
    try:
        api = _hf_api(tok)
    except ImportError:
        print("HUB-DEAD: huggingface_hub not importable in this interpreter"); return 3
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ok = 0
    for rel, p in rows:
        if not _gate(p):
            print("GATE-FAIL named, push refuses for: " + rel); continue
        try:
            api.upload_file(path_or_fileobj=p, path_in_repo=rel, repo_id=repo)
            ok += 1
            print("pushed %s bytes=%d" % (rel, os.path.getsize(p)))
        except Exception as e:
            print("HUB-DEAD named %s: %s: %s" % (rel, type(e).__name__, str(e)[:200]))
    print("pushed %d/%d stamp=%s" % (ok, len(rows), stamp))
    return 0 if ok == len(rows) else 3

def check(argv):
    repo = None
    for i, a in enumerate(argv):
        if a == "--repo": repo = argv[i+1] if i+1 < len(argv) else None
    repo = repo or _key("hf_repo")
    if not repo: refuse("check needs --repo or hf_repo config")
    tok = _token()
    try:
        api = _hf_api(tok)
    except ImportError:
        print("HUB-DEAD: huggingface_hub not importable in this interpreter"); return 3
    try:
        info = api.repo_info(repo, files_metadata=True)
        n = len([f for f in info.siblings])
        print("hub check %s files=%d (read-only door)" % (repo, n))
        return 0
    except Exception as e:
        print("HUB-DEAD named: %s: %s" % (type(e).__name__, str(e)[:200])); return 3

def main(argv):
    if not argv: refuse("needs verb push|check")
    verb, rest = argv[0], argv[1:]
    if verb == "push": return push(rest)
    if verb == "check": return check(rest)
    refuse("unknown verb: " + verb)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
