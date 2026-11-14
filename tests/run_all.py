# run_all.py — organs suite: sandbox fires (zero network, zero writes) + opt-in live read-only.
# Every test fires the organ's RED path deliberately (LAWS.md #4). Run: python tests/run_all.py [--live]
import os, sys, re, io, json, time, socket, subprocess, importlib.util, tempfile, contextlib, ast
import urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LIVE = "--live" in sys.argv
RESULTS = []

def record(name, ok, note=""):
    RESULTS.append((name, ok, note[:140]))
    print(("PASS " if ok else "FAIL ") + name + ("  " + note[:100] if note else ""))

def py_files():
    out = []
    for root, _, fs in os.walk(REPO):
        if "tests" in root.split(os.sep): continue
        for f in fs:
            if f.endswith(".py"): out.append(os.path.join(root, f))
    return out

# ---------- harness: exec a rig with mocked urlopen, scratch HOME/SEC, argv, captured stdout
class FakeResp:
    def __init__(self, data): self._d = data
    def read(self): return self._d
    def __enter__(self): return self
    def __exit__(self, *a): return False

def run_rig(rig_path, router, files=None, argv=None, env=None):
    scratch = tempfile.mkdtemp(prefix="organs_t_")
    home = os.path.join(scratch, "home"); sec = os.path.join(scratch, "sec")
    os.makedirs(home); os.makedirs(sec)
    json.dump({"secret": "test-secret"}, open(os.path.join(sec, "1f916.json"), "w"))
    for rel, content in (files or {}).items():
        p = os.path.join(home, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if not isinstance(content, (str, bytes)): content = json.dumps(content)
        open(p, "w", encoding="utf-8").write(content)
    os.environ["ORGANS_HOME"] = home
    os.environ["ORGANS_SECRETS"] = sec
    os.environ["ORGANS_SHOP_DIR"] = os.path.join(home, "shop")
    os.environ["ORGANS_LEG_DIR"] = os.path.join(home, "contribution")
    for k, v in (env or {}).items(): os.environ[k] = v
    src = open(rig_path, encoding="utf-8").read()
    real_urlopen = urllib.request.urlopen
    real_sleep = time.sleep
    calls = []
    def fake_urlopen(req, timeout=None):
        full = req.full_url if hasattr(req, "full_url") else str(req)
        p = full.split("://", 1)[1]; p = p[p.find("/"):]; calls.append(p)
        r = router(p, req)
        if isinstance(r, tuple) and r[0] == "raise":
            cls = r[1]; raise cls(req, 400, "Bad Request", None, None) if cls is urllib.error.HTTPError else cls(p)
        if isinstance(r, (dict, list)): return FakeResp(json.dumps(r).encode())
        return FakeResp(r if isinstance(r, bytes) else b"{}")
    urllib.request.urlopen = fake_urlopen
    time.sleep = lambda s: None
    buf = io.StringIO(); code = 0
    sys.argv = ["rig.py"] + (argv or [])
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(src, rig_path, "exec"), {"__name__": "__main__", "__file__": rig_path})
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except Exception as e:
        code = 90; buf.write(f"\nHARNESS-EXC {type(e).__name__}: {e}\n")
    finally:
        urllib.request.urlopen = real_urlopen; time.sleep = real_sleep
    tree = {}
    for root, _, fs in os.walk(home):
        for f in fs: tree[os.path.relpath(os.path.join(root, f), home).replace("\\", "/")] = open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
    return code, buf.getvalue(), tree, calls, home

def sub(cmd, cwd=None, env_extra=None):
    e = dict(os.environ); e.update(env_extra or {})
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=e, timeout=300)
    return p.returncode, p.stdout + p.stderr

# ---------- 1. compile all
ok = True; notes = []
for p in py_files():
    try: compile(open(p, encoding="utf-8").read(), p, "exec")
    except SyntaxError as e: ok = False; notes.append(f"{os.path.basename(p)}:{e.lineno}")
record("compile-all", ok, ",".join(notes))

# ---------- 2. AST undefined-name sweep (params/lambda-args/except-as/comprehension-targets defined)
def sweep(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    defined = set(b for b in dir(__builtins__)) | {"__file__", "__name__"}
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names: defined.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)): defined.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            if isinstance(n, ast.FunctionDef): defined.add(n.name)
            for a in ast.walk(n.args):
                if isinstance(a, ast.arg): defined.add(a.arg)
        elif isinstance(n, ast.ExceptHandler) and n.name: defined.add(n.name)
        elif isinstance(n, ast.comprehension):
            for a in ast.walk(n.target):
                if isinstance(a, ast.Name): defined.add(a.id)
        elif isinstance(n, ast.Global) or isinstance(n, ast.Nonlocal):
            for nm in n.names: defined.add(nm)
    return sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name)
                   and isinstance(n.ctx, ast.Load) and n.id not in defined})
bad = {os.path.basename(p): s for p in py_files() if (s := sweep(p))}
record("ast-undefined-sweep", not bad, json.dumps(bad)[:120])

# ---------- 3. portability residue: no absolute user paths, no shop identity, no baked secrets
res = {}
for p in py_files():
    t = open(p, encoding="utf-8").read()
    hits = []
    if re.search(r'[Cc]:[/\\\\][Uu]sers[/\\\\][Uu]ser', t): hits.append("winpath")
    for idn in ("shop3", "shop2", "swift-lantern", "newkin"):
        if idn in t: hits.append(idn)
    if re.search(r"[bs]w" + r"ift\b", t): hits.append("bare-handle")  # split literal: the scanner must not match its own pattern text
    if re.search(r":47[0-9]{3}\b", t): hits.append("estate-port")
    if re.search(r"\b100\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", t): hits.append("tailnet-ip")
    if re.search(r'[A-Za-z0-9+/]{40,}=', t): hits.append("long-token")
    if hits: res[os.path.basename(p)] = hits
record("portability-residue", not res, json.dumps(res)[:120])

# ---------- 4. counter_head: chain-walk + FIX-row re-cite max anchor
ledger = "\n".join([
 "| C5-1 | t | mint | Counter 1->2 |",
 "| C5-2 | t | mint | Counter 2->3 |",
 "| C5-3 | t | mint | Counter 3->4 |",
 "| C5-4 | t | mint | Counter 4->5 |",
 "| C5-5 | t | FIX head Counter 5->6; restatement re-cites Counter 3->4 |",
 "| C5-6 | t | mint | Counter 6->7 |",
])
def router_counter(p, req): return b"{}"
code, out, tree, _, home = run_rig(os.path.join(REPO, "scripts/counter_head.py"),
                                   router_counter, {"ledgers/CORPUS.md": ledger})
# last pair-row is C5-6 (Counter 6->7) -> head 7; FIX row max-cand test: drop last row
led2 = ledger.replace("| C5-6 | t | mint | Counter 6->7 |", "")
code2, out2, _, _, _ = run_rig(os.path.join(REPO, "scripts/counter_head.py"), router_counter,
                               {"ledgers/CORPUS.md": led2})
record("counter_head-head7", code == 0 and "7 |" in out, out.strip()[:60])
record("counter_head-fix-maxanchor", "canonical pair): 6 |" in out2, out2.strip()[:60])

# ---------- 5. inbox_walk2: per-bucket tokens, probe-gated drain, corrupt-state fail-closed, idless
BUCKETS = ("replies", "comments_on_your_posts", "in_threads_you_joined", "mentions_of_you")
def router_inbox(p, req):
    if "cursor_mode=id" in p:
        return {"now_utc": "x", "since_last_visit": {"totals": {"replies": 3}}}   # live door NON-zero
    if "before=T1" in p:
        return {"now_utc": "x", "since_last_visit": {"replies": [{"id": 5}, {"id": None}], "replies_next_before": None}}
    sv = {"replies": [{"id": 3, "body": "hi"}, {"id": 4}]}
    for b in BUCKETS[1:]: sv[b] = []
    sv["replies_next_before"] = "T1"
    return {"now_utc": "x", "since_last_visit": sv}
code, out, tree, calls, home = run_rig(os.path.join(REPO, "scripts/inbox_walk2.py"), router_inbox,
    {"data/inbox-walk-state.json": {"tokens": {}, "done": False, "pages": 0, "done_buckets": {}}})
stx = json.loads(tree.get("data/inbox-walk-state.json", "{}"))
toks_ok = code == 0 and all(stx.get("done_buckets", {}).get(b) for b in BUCKETS) and stx.get("tokens", {}).get("replies") == "T1"
record("inbox-perbucket-tokens", toks_ok, out.strip()[-90:])
record("inbox-idless-disclosed", "idless skipped: 1" in out, out.strip()[-60:])
record("inbox-both-pages-banked", '"id": 5' in tree.get("data/inbox-unread-20261109.jsonl", "")
       and '"id": 3' in tree.get("data/inbox-unread-20261109.jsonl", ""), "rows 3,4,5")
code, out, *_ = run_rig(os.path.join(REPO, "scripts/inbox_walk2.py"), router_inbox,
    {"data/inbox-walk-state.json": "{corrupt"})
record("inbox-corrupt-exit2", code == 2 and "CORRUPT" in out, out.strip()[:60])
def router_probe_fail(p, req):
    if "cursor_mode=id" in p: return ("raise", urllib.error.URLError)
    return {"since_last_visit": {"totals": {}}}
code, out, *_ = run_rig(os.path.join(REPO, "scripts/inbox_walk2.py"), router_probe_fail,
    {"data/inbox-walk-state.json": {"tokens": {}, "done": True, "pages": 0, "done_buckets": {b: True for b in BUCKETS}}})
record("inbox-probe-fail-not-drained", code == 2 and "PROBE-FAIL" in out, out.strip()[:70])

# ---------- 6. boardwalk: corrupt state, deep-err cursor-KEEP, idless, atomic (no tmp corpse)
def router_bw(p, req):
    if "before=DEEP" in p: return ("raise", urllib.error.HTTPError)
    return {"snapshot_id": "S1", "pin_snapshot": "P1", "next_before": "DEEP",
            "posts": [{"id": 10, "author": "a", "title": "t10", "created_at": 1},
                      {"author": "ghost", "title": "idless"}, {"id": 11, "author": "b", "title": "t11"}]}
st0 = {"seen": [{"id": 1, "author": "z", "title": "old", "ms": 0}], "cursor": "DEEP", "snapshot_id": "S1", "pin_snapshot": "P1"}
code, out, tree, calls, home = run_rig(os.path.join(REPO, "scripts/boardwalk_beat.py"), router_bw,
                                       {"data/boardwalk-state.json": st0})
st_after = json.loads(tree["data/boardwalk-state.json"])
record("boardwalk-deeperr-cursor-kept", "DEEP-ERR" in out and st_after["cursor"] == "DEEP", out.strip()[:70])
record("boardwalk-idless-not-poisoned", "IDLESS: 1" in out and None not in st_after["seen"]
       and all(_ is not None for _ in [r.get("id") for r in st_after["seen"]]), "idless disclosed")
record("boardwalk-no-tmp-corpse", not any(s.endswith(".tmp") for s in tree), ",".join(k for k in tree if k.endswith('.tmp')))
code, out, *_ = run_rig(os.path.join(REPO, "scripts/boardwalk_beat.py"), router_bw, {"data/boardwalk-state.json": "{oops"})
record("boardwalk-corrupt-exit2", code == 2 and "CORRUPT" in out, out.strip()[:60])
def router_bw2(p, req):  # cursor set, snapshot missing on head page
    return {"posts": [{"id": 12}], "next_before": "DEEP"}
st1 = {"seen": [], "cursor": "DEEP", "snapshot_id": None, "pin_snapshot": None}
code, out, tree2, *_ = run_rig(os.path.join(REPO, "scripts/boardwalk_beat.py"), router_bw2, {"data/boardwalk-state.json": st1})
record("boardwalk-degrade-disclosed", "DEGRADE" in out, out.strip()[:60])

# ---------- 7. truncation_sweep: zero-work exit2, no-shell + fields-absent RED, timestamped report
code, out, tree, *_ = run_rig(os.path.join(REPO, "scripts/truncation_sweep.py"),
                              lambda p, req: {}, {"data/me-history-20261109.json": {"nothing": []}})
record("trunc-zero-work-exit2", code == 2 and "ZERO ROWS" in out, out.strip()[:60])
def router_tr(p, req):
    if "/api/post/1" in p: return {"weird": {"mentions_in_code": 1}}          # unknown shell
    if "/api/post/2" in p: return {"post": {"id": 2, "title": "no delivery fields"}}  # fields absent
    if "/api/comment/3" in p: return {"comment": {"mentions_in_code": 2, "mentions_over_cap": 7}}
    return {}
hist = {"posts": [{"id": 1}, {"id": 2}], "comments": [{"id": 3}]}
code, out, tree, *_ = run_rig(os.path.join(REPO, "scripts/truncation_sweep.py"), router_tr,
                              {"data/me-history-20261109.json": hist})
report_files = [k for k in tree if k.startswith("data/truncation-sweep-")]
import datetime
ts_ok = report_files and re.search(r"truncation-sweep-\d{8}-\d{6}\.json", report_files[0])
record("trunc-red-exit1", code == 1 and "NO-SHELL" in out and "FIELDS-ABSENT" in out, out.strip()[-80:])
record("trunc-timestamped-report", bool(ts_ok), str(report_files[:1]))

# ---------- 8. relays: twin_fwd echoes through a rewritten scratch copy (port-rewrite harness)
srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1); target = srv.getsockname()[1]
def echo_loop():
    try:
        conn, _ = srv.accept()
        while True:
            d = conn.recv(65536)
            if not d: break
            conn.sendall(d)
    except OSError: pass
import threading as _th
_th.Thread(target=echo_loop, daemon=True).start()
src = open(os.path.join(REPO, "scripts/twin_fwd.py"), encoding="utf-8").read()
ports = re.findall(r"\b(\d{4,5})\b", src)
s = socket.socket(); s.bind(("127.0.0.1", 0)); listen_port = s.getsockname()[1]; s.close()
patched = re.sub(r'TARGET = \("127\.0\.0\.1", \d+\)', f'TARGET = ("127.0.0.1", {target})', src)
patched = re.sub(r'LISTEN = \("127\.0\.0\.1", \d+\)', f'LISTEN = ("127.0.0.1", {listen_port})', patched)
tp = os.path.join(tempfile.mkdtemp(prefix="relay_"), "fwd_test.py")
open(tp, "w").write(patched)
proc = subprocess.Popen([sys.executable, tp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time_real = time.monotonic(); got = None
while time.monotonic() - time_real < 5:
    try:
        c = socket.create_connection(("127.0.0.1", listen_port), timeout=2)
        c.sendall(b"PING-ORGAN"); got = c.recv(16); c.close(); break
    except OSError: time.sleep(0.3)
proc.terminate(); srv.close()
record("relay-echo-through", got == b"PING-ORGAN", str(got))

# ---------- 9. build_index: scratch tree builds; zero-file root refuses BEFORE destroying
bi = os.path.join(REPO, "index/build_index.py")
code, out, tree, *_ = run_rig(bi, lambda p, req: {},
    {"shop/a.md": "# alpha\nhello\n", "shop/sub/b.md": "# beta\nworld\n", "contribution/c.md": "# gamma\n"})
ok_build = code == 0 and any("index.db" in k for k in tree) and "index.db rebuilt" in out  # wave-5 W01: the promised report asserted ON STDOUT (was promised in a code comment only -- False-Health)
# zero-file: root dir exists but empty -> refuse exit 2
import shutil
for d in ("shop", "contribution"):
    pth = os.path.join(os.environ["ORGANS_HOME"], d)
    if os.path.isdir(pth): shutil.rmtree(pth); os.makedirs(pth)
c2, o2 = 0, ""
src2 = open(bi, encoding="utf-8").read(); buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf):
        exec(compile(src2, bi, "exec"), {"__name__": "__main__", "__file__": bi})
except SystemExit as e: c2 = e.code if isinstance(e.code, int) else 1
except Exception as e: c2 = 90; buf.write(repr(e))
o2 = buf.getvalue()
record("build-index-scratch", ok_build, out.strip()[-60:])
record("build-index-zero-refuse", c2 == 2 and "refus" in o2.lower(), o2.strip()[:60])  # wave-5 W17: rig truth is exit 2; (1,2) tolerated a gate-shaped 1

# ---------- 10. preflight: lookbehind (https:// not a drive path), torn receipts close the gate
pf = os.path.join(REPO, "scripts/venue/preflight_1f916.py")
RCV = "data/venue-replies-receipts-20261108.jsonl"
def router_pf(p, req):
    return {"today": {"posts_remaining": 1, "comments_remaining": 10, "votes_remaining": 50, "tags_remaining": 20},
            "now_utc": "2026-11-12T00:00:00Z"}
body_clean = "Kin note: see https://1f916.ai/api/surface — numbers only.\n"
bp = os.path.join(tempfile.mkdtemp(prefix="pf_"), "body.md"); open(bp, "w").write(body_clean)
code, out, tree, calls, _ = run_rig(pf, router_pf, {"ledgers/CORPUS.md": "| C5-1 | 2026-11-12T00:00:00Z | mint |\n", "data/venue-replies-receipts-20261108.jsonl": ""}, argv=[bp, "gid-test"])
record("preflight-clean-pass", code == 0 and "PASS" in out, f"rc={code} " + out.strip()[-80:])
body_leak = "key shape: " + "A"*40 + "=\n"
bp2 = os.path.join(tempfile.mkdtemp(prefix="pf_"), "b2.md"); open(bp2, "w").write(body_leak)
code, out, *_ = run_rig(pf, router_pf, {"ledgers/CORPUS.md": "| C5-1 | 2026-11-12T00:00:00Z | mint |\n"}, argv=[bp2, "gid-test2"])
record("preflight-screen-hard", code == 1, out.strip()[-70:])
# torn receipt line beside a fresh gid: gate must CLOSE (wave-2 cure: continue-swallow = fail-open)
code, out, *_ = run_rig(pf, router_pf, {"ledgers/CORPUS.md": "| C5-1 | 2026-11-12T00:00:00Z | mint |\n",
    RCV: '{"gid": "gid-test3", "cid": 1\n'}, argv=[bp, "test-ship3", "gid-test3"])
record("preflight-torn-receipt-closes-gate", code == 1 and "BLOCK" in out, out.strip()[-70:])
# missing receipt file = gate CLOSED (fail-closed by design)
code, out, *_ = run_rig(pf, router_pf, {"ledgers/CORPUS.md": "| C5-1 | 2026-11-12T00:00:00Z | mint |\n"}, argv=[bp, "gid-test4"])
record("preflight-missing-receipt-closes-gate", code == 1 and "gate CLOSED" in out, out.strip()[-70:])

# ---------- 11b. audit wave 3 (deleg_b499ec12): T-02 shipper firings, T-03 real door shell,
# F-regression reds (F-01 receipt-survives-readback, F-03 partial fields, F-07 gates-under -O,
# F-12 gguf header parse, F-14 zero-sample window, F-16 unreadable quota door).
import hashlib as _h

# ship_post: usage red, key-screen red (pre-network), GREEN firing, readback-death keeps the receipt
sp = os.path.join(REPO, "scripts/venue/ship_post_20261111.py")
def router_never(p, req): raise AssertionError("no network allowed on this leg: " + p)
code, out, *_ = run_rig(sp, router_never, {})
record("ship-post-usage-exit2", code == 2 and "usage" in out, out.strip()[:50])
_bp = os.path.join(tempfile.mkdtemp(prefix="sp_"), "b.md")
open(_bp, "w", encoding="utf-8").write("x " + "A"*60 + "=")
code, out, *_ = run_rig(sp, router_never, {}, argv=["kin title", _bp])
record("ship-post-keyscreen-exit2", code == 2 and "SCREEN" in out, out.strip()[:60])
_tp = os.path.join(tempfile.mkdtemp(prefix="sp_"), "t.md")
_tp2 = os.path.join(tempfile.mkdtemp(prefix="sp_"), "t2.md")
open(_tp, "w", encoding="utf-8").write("kin note body")
open(_tp2, "w", encoding="utf-8").write("body with bearer Bearer " + "Z"*20 + " tail")
def router_ship(p, req):
    if p.startswith("/api/post") and "?" not in p and req.data: return {"post_id": 77}
    if p.startswith("/api/post/77"): return {"post": {"title": "kin title", "body": "kin note body"}}
    return {}
code, out, tree, calls, home = run_rig(sp, router_ship, {}, argv=["kin title", _tp])
recs = [k for k in tree if k.startswith("data/ship-post-receipt")]
record("ship-post-green", code == 0 and "post_id=77" in out and "title_match=True" in out and recs
       and '"readback_ok": true' in tree[recs[0]], out.strip()[-70:])
def router_ship_rb(p, req):
    if p.startswith("/api/post") and "?" not in p and req.data: return {"post_id": 78}
    if p.startswith("/api/post/78"): return ("raise", urllib.error.HTTPError)  # readback door dies AFTER landing
code, out, tree, calls, home = run_rig(sp, router_ship_rb, {}, argv=["kin title", _tp])
recs2 = [k for k in tree if k.startswith("data/ship-post-receipt")]
# F-01 proof: readback dies, post LANDED -- receipt with the pid citation SURVIVES, exit 1, no crash
record("ship-post-readback-death-keeps-receipt",
       code == 1 and "READBACK-FAIL" in out and recs2 and '"post_id": 78' in tree[recs2[0]], out.strip()[-70:])
code, out, *_ = run_rig(sp, router_never, {}, argv=["kin title", _tp2])
record("ship-post-bearer-body-exit2", code == 2 and "SCREEN" in out, out.strip()[:60])

# ship_queue: GREEN full firing through the mock door + pin-mismatch RED + gates survive -O
sq = os.path.join(REPO, "scripts/ship_queue_20261111.py")
body1 = "kin reply body one"
dg1 = _h.sha256(body1.encode("utf-8")).hexdigest()
QF = "canon/board/ship-queue-20261110.md"
q_green = f"## 1. post 100 parent 50\n{body1}\n\nINTENT PINS\nPINDIGEST post 100 ship 1 sha256 {dg1}\n"
q_badpin = f"## 1. post 100 parent 50\n{body1}\n\nINTENT PINS\nPINDIGEST post 100 ship 1 sha256 {'0'*64}\n"
q_wrongpost = f"## 1. post 999 parent 50\n{body1}\n\nINTENT PINS\nPINDIGEST post 100 ship 1 sha256 {dg1}\n"
def router_sq(p, req):
    if p.startswith("/api/post/100") and req.data is None: return {"comments": [], "has_more": False, "post": {"body": "post body"}}
    if p == "/api/me": return {"me": {"handle": "tester", "today": {"comments_remaining": 8}}}
    if p == "/api/comment" and req.data: return {"comment_id": 5}
    if p.startswith("/api/comment/5"): return {"comment": {"author": "tester", "post_id": 100, "parent_id": 50}}
    return {}
code, out, tree, calls, home = run_rig(sq, router_sq, {QF: q_green})
recsq = [k for k in tree if k.startswith("data/ship-queue-receipts")]
record("ship-queue-green", code == 0 and "ships landed: 1" in out and recsq
       and '"pair_of_eyes": true' in tree[recsq[0]], out.strip()[-70:])
code, out, *_ = run_rig(sq, router_sq, {QF: q_badpin})
record("ship-queue-pindigest-gate", code == 2 and "GATE:" in out and "DIGEST MISMATCH" in out, out.strip()[:70])
code, out, *_ = run_rig(sq, router_sq, {QF: q_wrongpost})
record("ship-queue-pinpost-gate", code == 2 and "PIN POST MISMATCH" in out, out.strip()[:70])
# F-07 proof: under -O (optimize=2) asserts vanish; the explicit gates must still fire. No network on
# this leg -- the pin gate sits BEFORE any write door.
src_sq = open(sq, encoding="utf-8").read()
os.environ["ORGANS_HOME"] = tempfile.mkdtemp(prefix="sqo_")
buf2 = io.StringIO()
q_bad_file = os.path.join(os.environ["ORGANS_HOME"], "canon/board")
os.makedirs(q_bad_file, exist_ok=True)
open(os.path.join(os.environ["ORGANS_HOME"], QF), "w", encoding="utf-8").write(q_badpin)
sys.argv = ["rig.py"]
# wave-5 W06: hermetic doors on the -O leg -- GETs answered from a stub, ANY write door raises. The
# old comment claimed 'no network' with no mock: the leg ran on the LIVE shop seat (green by accident).
import urllib.request as _uq6
_real6 = _uq6.urlopen
class _R6:
    def __init__(self, d): self._d = d
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self): return json.dumps(self._d).encode()
def _no_write6(req, timeout=None, **kw):
    m = getattr(req, "get_method", lambda: "GET")()
    if m != "GET": raise AssertionError("SUITE -O LEG: write door reached -- " + str(getattr(req, "full_url", req)))
    u = getattr(req, "full_url", "")
    if "/api/me" in u: return _R6({"me": {"handle": "suite"}})
    if "/api/quota" in u: return _R6({"today": {"comments_remaining": 10, "posts_remaining": 3}, "now_utc": "2026-11-12T00:00:00Z"})
    if "/api/whoami" in u: return _R6({"handle": "suite"})
    return _R6({})
_uq6.urlopen = _no_write6
try:
    with contextlib.redirect_stdout(buf2):
        exec(compile(src_sq, sq, "exec", optimize=2), {"__name__": "__main__", "__file__": sq})
except SystemExit as e: c_o = e.code if isinstance(e.code, int) else 1
except AssertionError as e: c_o = 90; buf2.write("WRITE-DOOR-FIRED: " + str(e))
finally:
    _uq6.urlopen = _real6
record("ship-queue-gates-survive-O", c_o == 2 and "GATE:" in buf2.getvalue(), f"rc={c_o} " + buf2.getvalue().strip()[:60])

# counter_head: a ledger with NO Counter pair anywhere -> named refusal, exit 1
code, out, *_ = run_rig(os.path.join(REPO, "scripts/counter_head.py"), lambda p, req: {},
                        {"ledgers/CORPUS.md": "| C5-1 | t | mint | no counters here |\n"})
record("counter-nopair-exit1", code == 1, f"rc={code} " + out.strip()[:60])

# F-03 regression: row with PARTIAL delivery fields (one present, one absent) must fire FIELDS-ABSENT
def router_tr_partial(p, req):
    if "/api/post/4" in p: return {"post": {"id": 4, "title": "t", "mentions_in_code": 3}}  # over_cap absent
    return {}
code, out, *_ = run_rig(os.path.join(REPO, "scripts/truncation_sweep.py"), router_tr_partial,
                        {"data/me-history-20261109.json": {"posts": [{"id": 4}], "comments": []}})
record("trunc-partial-fields-red", code == 1 and "FIELDS-ABSENT" in out, out.strip()[-70:])

# F-16 + T-03: real venue shell {me:{...}} rides the preflight (P5 unwrap); door WITHOUT counters HARD-BLOCKS
def router_pf_real(p, req):
    return {"me": {"handle": "tester", "handle_old": "t", "created_at": "x",
                   "today": {"posts_remaining": 2, "comments_remaining": 10, "votes_remaining": 50, "tags_remaining": 20},
                   "lifetime": {}, "now_utc": "2026-11-12T00:00:00Z"}}
def router_pf_notoday(p, req):
    return {"me": {"handle": "tester"}}
code, out, *_ = run_rig(pf, router_pf_real, {"ledgers/CORPUS.md": "| C5-1 | 2026-11-12T00:00:00Z | mint |\n", RCV: ""}, argv=[bp, "gidR"])
record("preflight-real-shell-pass", code == 0 and "PASS" in out, f"rc={code} " + out.strip()[-70:])
code, out, *_ = run_rig(pf, router_pf_notoday, {"ledgers/CORPUS.md": "| C5-1 | 2026-11-12T00:00:00Z | mint |\n"}, argv=[bp, "gidNT"])
record("preflight-no-counters-hardblocks", code == 1 and "quota leg CLOSED" in out, out.strip()[-70:])

# F-12: gguf rig PARSES its header -- synthetic GGUF fixture built in-test (alignment 32, 1 tensor)
import struct as _st
def mk_gguf(path, alignment=32, n_tensors=1):
    k = b"general.alignment"
    kv = _st.pack("<Q", len(k)) + k + _st.pack("<I", 4) + _st.pack("<I", alignment)
    hdr = b"GGUF" + _st.pack("<I", 3) + _st.pack("<Q", n_tensors) + _st.pack("<Q", 1) + kv
    pos = (len(hdr) + alignment - 1) // alignment * alignment
    name = b"blk.0.w"
    # grammar A (llama.cpp gguf spec): name-u64len, nd u32, ty u32, off u64, dims u64 x nd
    rec = _st.pack("<Q", len(name)) + name + _st.pack("<I", 1) + _st.pack("<I", 18) + _st.pack("<Q", 0) + _st.pack("<Q", 100)
    pad = (alignment - len(rec) % alignment) % alignment
    open(path, "wb").write(hdr + b"\0" * (pos - len(hdr)) + rec + b"\0" * pad + b"\0" * 64)
    return pos
gpath = os.path.join(tempfile.mkdtemp(prefix="g_"), "fixture.gguf")
gpos = mk_gguf(gpath)
code, out, *_ = run_rig(os.path.join(REPO, "scripts/molt/gguf_hist.py"), lambda p, req: {}, {}, argv=[gpath])
record("gguf-header-parse-green", code == 0 and f"table_start={gpos}" in out and "parsed: 1 of 1" in out, out.strip()[:90])
code, out, *_ = run_rig(os.path.join(REPO, "scripts/molt/gguf_hist.py"), lambda p, req: {}, {})
record("gguf-unconfigured-exit2", code == 2 and "GGUF-UNCONFIGURED" in out, out.strip()[:60])

# F-14: window recorder with a dead nvidia door captures ZERO rows -> named non-green exit 1
_win = os.path.join(REPO, "scripts/skin/window.py")
import subprocess as _sp
class _ShimRun:
    @staticmethod
    def run(cmd, **kw):
        class R: stdout = ""
        return R()
real_subprocess = sys.modules.get("subprocess")
sys.modules["subprocess"] = type("shim", (), {"run": _ShimRun.run})()
try:
    code, out, *_ = run_rig(_win, lambda p, req: {}, argv=["3", "red-zero"])
finally:
    sys.modules["subprocess"] = real_subprocess
record("window-zero-samples-not-green", code == 1 and "ZERO samples" in out, out.strip()[:70])

# ---------- 12. live read-only (opt-in)
if LIVE:
    def get(p):
        rq = urllib.request.Request(p, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(rq, timeout=25) as r: return r.read().decode()
    try:
        s = get("https://1f916.ai/api/surface")
        record("live-surface-doc", "/api/post" in s and "post_id" in s, f"{len(s)} bytes")
    except Exception as e: record("live-surface-doc", False, type(e).__name__)
    try:
        d = json.loads(get("https://1f916.ai/api/post/2099?limit=5"))
        okg = isinstance(d.get("comments"), list) and "has_more" in d
        record("live-thread-door-grammar", okg, f"comments={len(d.get('comments', []))}")
    except Exception as e: record("live-thread-door-grammar", False, type(e).__name__)
    seat = os.environ.get("ORGANS_SEAT_URL")
    if seat:
        try:
            h = json.loads(get(seat.rstrip("/") + "/api/health"))
            record("live-seat-health", "uptimeSec" in json.dumps(h), json.dumps(h)[:80])
        except Exception as e: record("live-seat-health", False, type(e).__name__)
    print("(live tests are GETs only — the suite performs zero venue writes in any mode)")


# --- cadence census red-path tests (2026-11-12, dream-lane autopsy organ) ---
import tempfile, subprocess
def _cad(name, jobs_obj, want_rc, want_in, want_not=(), extra_env=None):  # wave-6 W6-15: hermetic pins (extra_env), never the live estate
    _td = tempfile.mkdtemp()
    _jp = os.path.join(_td, "jobs.json")
    json.dump({"jobs": jobs_obj}, open(_jp, "w", encoding="utf-8"))
    _ff6 = os.path.join(_td, "firings.jsonl"); open(_ff6, "w", encoding="utf-8").write("")
    _env = dict(os.environ, ORGANS_JOBS=_jp, ORGANS_LEDGER=os.path.join(_td, "missing.md"),
               ORGANS_HOME=_td, ORGANS_SECRETS=_td, ORGANS_SHOP_DIR=_td, ORGANS_LEG_DIR="none", ORGANS_TZ_OFFSET="-6",
               ORGANS_BELL_FIRINGS=_ff6)  # wave-6 W6-15: every path the rig resolves is pinned to the fixture
    _env.update(extra_env or {})
    _r = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "cadence_audit.py")],
                        capture_output=True, text=True, env=_env, timeout=120)
    _out = _r.stdout + _r.stderr
    record("cadence-" + name, _r.returncode == want_rc and all(x in _out for x in want_in) and all(x not in _out for x in want_not),
           "rc=%d | %s" % (_r.returncode, _out[:90]))
_cad("clean-green", [{"name": "a", "script": "", "enabled": True, "schedule": {"kind": "interval", "minutes": 10, "display": "every 10m"}, "last_status": "ok"}], 0, (), ("BELL CENSUS",))
_cad("live-red-alert", [{"name": "dream", "script": "", "enabled": True, "schedule": {"kind": "interval", "minutes": 10, "display": "every 10m"}, "last_status": "error"}], 1, ("BELL CENSUS RED", "LIVE-RED: dream"))
_cad("oneshot-red-advisory", [{"name": "old", "script": "", "enabled": True, "schedule": {"kind": "once", "run_at": "2026-01-01T00:00:00"}, "last_status": "error"}], 0, ("one-shot/disabled reds",), ("LIVE-RED",))  # wave-5 W15: fixtures track the honest label


# --- dream_beat red-path tests (2026-11-12; sandboxed env pins: NO real store, NO WSL fire) ---
def _dream(name, live_env, dream_sh_env, want_rc, want_in):
    _td = tempfile.mkdtemp()
    _env = dict(os.environ, ORGANS_HOME=_td, ORGANS_SECRETS=_td, ORGANS_SHOP_DIR=_td,
               ORGANS_LEG_DIR="none", ORGANS_MNEMOS=live_env)
    if dream_sh_env is None:
        _env.pop("ORGANS_DREAM_SH", None)
    else:
        _env["ORGANS_DREAM_SH"] = dream_sh_env
    _r = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "dream_beat.py")],
                        capture_output=True, text=True, env=_env, timeout=120)
    _out = _r.stdout + _r.stderr
    record("dream-" + name, _r.returncode == want_rc and all(x in _out for x in want_in),
           "rc=%d | %s" % (_r.returncode, _out[:90]))
_dream("missing-store-failclosed", os.path.join(tempfile.mkdtemp(), "absent.db"), None, 1, ("DREAM-RED", "LIVE store missing"))
_dream("sh-gate-missing-store", os.path.join(tempfile.mkdtemp(), "absent.db"), "/mnt/c/USERshop/x.sh", 1, ("DREAM-RED",))
# store present + placeholder path -> gate fires BEFORE any WSL call
import sqlite3 as _s3
_sdp = os.path.join(tempfile.mkdtemp(), "live.db")
_c = _s3.connect(_sdp); _c.execute("CREATE TABLE journal_entries(id TEXT)"); _c.execute("CREATE TABLE beliefs(id TEXT)"); _c.commit(); _c.close()
_dream("placeholder-rejection", _sdp, "/mnt/c/USERshop/x.sh", 2, ("DREAM-SH-UNCONFIGURED",))


# ============ wave-4 (deleg_4fbe40ed, 2026-11-12): cures proven, coverage gaps closed ============
import datetime as _dt4
# F-08: disabled red bell = obituary, not alert
_cad("disabled-red-obituary", [{"name": "gone", "script": "", "enabled": False,
      "schedule": {"kind": "interval", "minutes": 10, "display": "every 10m"}, "last_status": "error"}],
     0, ("one-shot/disabled reds",), ("LIVE-RED",))  # wave-5 W15: fixtures track the honest label
# misses leg exercised: scheduled interval bell with stale last_run_at must MISS and alert
_stale = (_dt4.datetime.now(_dt4.timezone.utc) - _dt4.timedelta(hours=10)).isoformat()
_cad("cadence-miss-alert", [{"name": "missed", "script": "", "enabled": True, "state": "scheduled",
      "schedule": {"kind": "interval", "minutes": 10, "display": "every 10m"}, "last_status": "ok", "last_run_at": _stale}],
     1, ("CADENCE AUDIT", "MISS:"))
# F-13b: full-silence clean fixture (good ledger, fresh firings, green bells => empty stdout, rc 0)
def _silence4():
    _td = tempfile.mkdtemp()
    _now = _dt4.datetime.now(_dt4.timezone.utc)
    json.dump({"jobs": [{"name": "a", "script": "", "enabled": True, "state": "scheduled",
               "schedule": {"kind": "interval", "minutes": 10, "display": "every 10m"}, "last_status": "ok",
               "last_run_at": _now.isoformat()}]}, open(os.path.join(_td, "jobs.json"), "w"))
    open(os.path.join(_td, "ledger.md"), "w", encoding="utf-8").write(
        "| C5-1 | t | mint | Counter 7134->7135 |\n| C5-2 | t | mint | Counter 7135->7136 |\n")
    with open(os.path.join(_td, "firings.jsonl"), "w", encoding="utf-8") as fh:
        for k in range(4):
            fh.write(json.dumps({"job": "a", "last_run": _dt4.datetime.fromtimestamp(_now.timestamp() - k * 600, _dt4.timezone.utc).isoformat()}) + "\n")  # wave-5 W16: real firings-store grammar (job/last_run); name/ts made every phase leg skip silently
    r = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "cadence_audit.py")], capture_output=True, text=True, timeout=120,
        env=dict(os.environ, ORGANS_JOBS=os.path.join(_td, "jobs.json"), ORGANS_LEDGER=os.path.join(_td, "ledger.md"),
                 ORGANS_BELL_FIRINGS=os.path.join(_td, "firings.jsonl"), ORGANS_HOME=_td, ORGANS_TZ_OFFSET="-6", ORGANS_ROW_PREFIX="C5"))  # wave-5 W20 companion: fixture carries the prefix grammar
    record("cadence-clean-full-silence", r.returncode == 0 and (r.stdout + r.stderr).strip() == "",
           f"rc={r.returncode} out={repr((r.stdout + r.stderr)[:80])}")
_silence4()
# F-14b: ship_queue zero work is not green (rem ample, queue empty)
def router_q4(p, req):
    return {"today": {"comments_remaining": 10, "posts_remaining": 3}, "now_utc": "2026-11-12T00:00:00Z"}
code, out, *_ = run_rig(os.path.join(REPO, "scripts", "ship_queue_20261111.py"), router_q4,
                        {"canon/board/ship-queue-20261110.md": "no sections here\n"})
record("ship-queue-zero-work-not-green", code == 3, f"rc={code} {out.strip()[-60:]}")
# F-14/F-15/F-07 gguf red-paths
_zp = os.path.join(tempfile.mkdtemp(prefix="gz_"), "zero.gguf"); mk_gguf(_zp, n_tensors=0)
code, out, *_ = run_rig(os.path.join(REPO, "scripts/molt/gguf_hist.py"), lambda p, req: {}, {}, argv=[_zp])
record("gguf-zero-tensors-refused", code == 2 and "ZERO tensors" in out, f"rc={code} {out.strip()[:60]}")
_a0 = os.path.join(tempfile.mkdtemp(prefix="ga_"), "a0.gguf")
_k = b"general.alignment"
open(_a0, "wb").write(b"GGUF" + _st.pack("<I", 3) + _st.pack("<Q", 1) + _st.pack("<Q", 1) + _st.pack("<Q", len(_k)) + _k + _st.pack("<I", 4) + _st.pack("<I", 0) + b"\0" * 64)
code, out, *_ = run_rig(os.path.join(REPO, "scripts/molt/gguf_hist.py"), lambda p, req: {}, {}, argv=[_a0])
record("gguf-alignment-zero-refused", code == 2 and "NONSENSE" in out, f"rc={code} {out.strip()[:60]}")
_bp = os.path.join(tempfile.mkdtemp(prefix="gb_"), "b.gguf")
_kb = b"general.alignment"
_kvb = _st.pack("<Q", len(_kb)) + _kb + _st.pack("<I", 4) + _st.pack("<I", 32)
_hd = b"GGUF" + _st.pack("<I", 3) + _st.pack("<Q", 1) + _st.pack("<Q", 1) + _kvb
_pos = (len(_hd) + 31) // 32 * 32
_nm = b"w"  # F-07: single-char tensor name must parse
_rec = _st.pack("<Q", len(_nm)) + _nm + _st.pack("<I", 1) + _st.pack("<Q", 100) + _st.pack("<Q", 13 << 8) + _st.pack("<I", 0)  # grammar B: dims, flags(top byte 13=Q5_K), off u32
_pad = (32 - len(_rec) % 32) % 32
open(_bp, "wb").write(_hd + b"\0" * (_pos - len(_hd)) + _rec + b"\0" * _pad + b"\0" * 64)
code, out, *_ = run_rig(os.path.join(REPO, "scripts/molt/gguf_hist.py"), lambda p, req: {}, {}, argv=[_bp])
record("gguf-grammar-B-green", code == 0 and "grammar=B" in out and "parsed: 1 of 1" in out, f"rc={code} {out.strip()[:80]}")
# F-02: quota door answering today={} is unreadable = CLOSED
code, out, *_ = run_rig(pf, lambda p, req: {"today": {}, "now_utc": "2026-11-12T00:00:00Z"},
                        {"ledgers/CORPUS.md": "| C5-1 | 2026-11-12T00:00:00Z | mint |\n", RCV: ""},
                        argv=[bp, "gid-empty"])
record("preflight-empty-counters-closed", code == 1 and "CLOSED" in out, f"rc={code} {out.strip()[-60:]}")
# F-03: dedup reads the UNION stores -- a queue-receipts pin blocks re-ship
_dupseed = json.dumps([{"ship": 1, "post": "gid-union", "parent_requested": 5, "comment_id": 42,
                        "parent_attached": 5, "parent_MOVED": False, "pair_of_eyes": True,
                        "dedup": False, "readback": "OK", "ts": "2026-11-12T00:00:00+00:00"}])  # wave-6 W6-16: REAL queue receipt grammar (ship/post/comment_id) -- the synthetic pin/cid shape hid the union blind spot for two audit generations
code, out, *_ = run_rig(pf, router_pf, {"ledgers/CORPUS.md": "| C5-1 | 2026-11-12T00:00:00Z | mint |\n",
    "data/ship-queue-receipts-20261111.json": _dupseed}, argv=[bp, "gid-union"])
record("preflight-union-store-dedup", code == 1 and "dup" in out, f"rc={code} {out.strip()[-60:]}")
# wave-6 W6-16: the legacy pin/cid shape must stay in the union too (both store grammars dedup)
code, out, *_ = run_rig(pf, router_pf, {"ledgers/CORPUS.md": "| C5-1 | 2026-11-12T00:00:00Z | mint |" + chr(10), "data/ship-queue-receipts-20261111.json": json.dumps([{"pin": "gid-legacy", "cid": 2}])}, argv=[bp, "gid-legacy"])
record("preflight-union-legacy-pin-dedup", code == 1 and "dup" in out, f"rc={code} {out.strip()[-60:]}")
# F-10: ship_post screen grammar == preflight's (case-insensitive, hex40 without =)
_hx = os.path.join(tempfile.mkdtemp(prefix="hx_"), "b.md")
open(_hx, "w", encoding="utf-8").write("pin quote 36A8DD2614FCDEDA" + "A" * 48 + "\n")
code, out, *_ = run_rig(os.path.join(REPO, "scripts/venue/ship_post_20261111.py"), lambda p, req: {}, {}, argv=["probe title", _hx])
record("ship-post-screen-hex40", code == 2 and "SCREEN" in out, f"rc={code} {out.strip()[:60]}")  # wave-5 W05: valid title + named refusal ON STDOUT is the proof; bare rc 2 also fires on arg-count accidents
# F-01b: ship_post pid gate survives -O: exec optimize=2 with a door that answers WITHOUT post_id
# (mocked urlopen -- zero real network), expect rc 2 + named refusal + NO receipt file.
def _opid_leg():
    _td = tempfile.mkdtemp()
    _body = os.path.join(_td, "b.md"); open(_body, "w", encoding="utf-8").write("plain body, screens clean.\n")
    src = open(os.path.join(REPO, "scripts", "venue", "ship_post_20261111.py"), encoding="utf-8").read()
    class _R:
        def read(self): return json.dumps({"ok": True}).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False
    _real = urllib.request.urlopen
    urllib.request.urlopen = lambda req, timeout=None, **kw: _R()
    _code, _buf = None, io.StringIO()
    _saved_argv = sys.argv
    sys.argv = ["rig.py", "title", _body]
    try:
        with contextlib.redirect_stdout(_buf):
            exec(compile(src, "ship_post.py", "exec", optimize=2), {"__name__": "__main__", "__file__": os.path.join(REPO, "scripts", "venue", "ship_post_20261111.py")})
    except SystemExit as e:
        _code = e.code if isinstance(e.code, int) else 1
    finally:
        urllib.request.urlopen = _real
        sys.argv = _saved_argv
    _home = os.environ.get("ORGANS_HOME", "")
    _receipts = [f for f in os.listdir(os.path.join(_home, "data")) if "receipt" in f.lower()] if _home and os.path.isdir(os.path.join(_home, "data")) else []
    record("ship-post-pid-gate-survives-O", _code == 2 and "NO post_id" in _buf.getvalue() and not _receipts,
           f"rc={_code} receipts={_receipts} {_buf.getvalue().strip()[:70]}")
_opid_leg()
# gguf magic gate survives -O (assert side-effect cure)
_gj = os.path.join(tempfile.mkdtemp(prefix="gj_"), "junk.gguf"); open(_gj, "w").write("junkjunkjunkjunk")
_r = subprocess.run([sys.executable, "-O", os.path.join(REPO, "scripts/molt/gguf_hist.py"), _gj], capture_output=True, text=True, timeout=60)
record("gguf-magic-gate-survives-O", _r.returncode == 2 and "NOT A GGUF" in (_r.stdout + _r.stderr), f"rc={_r.returncode}")

# ---------- wave-5 cures (deleg_cd0d5a8e): the red-paths the wave-4 suite left blind ----------
import urllib.error as _ue5
import sqlite3 as _s3w5

# W04 (LAWS #22): readback death must LAND the receipt before exit 1 -- no blind re-ring
def router_rd(p, req):
    if p.startswith("/api/post/100") and req.data is None: return {"comments": [], "has_more": False, "post": {"body": "post body"}}
    if p == "/api/me": return {"me": {"handle": "tester", "today": {"comments_remaining": 8}}}
    if p == "/api/comment" and req.data: return {"comment_id": 7}
    if p.startswith("/api/comment/7") and req.data is None: raise _ue5.URLError("suite readback death")
    return {}
code, out, tree, calls, home5 = run_rig(sq, router_rd, {QF: q_green})
_rec5 = [k for k in tree if k.startswith("data/ship-queue-receipts")]
record("ship-queue-readback-death-lands-receipt",
       code == 1 and "READBACK DEATH" in out and bool(_rec5)
       and '"comment_id": 7' in tree[_rec5[0]] and '"readback": "DEAD' in tree[_rec5[0]],
       out.strip()[-70:])

# W03: preflight dedup must read ship_post receipts' post_id field (it wrote post_id; preflight read gid/pin only)
code, out, *_ = run_rig(pf, router_pf, {
    "ledgers/CORPUS.md": "| C5-1 | 2026-11-12T00:00:00Z | mint |" + chr(10),
    "data/ship-post-receipt-9.json": json.dumps({"post_id": "gid-spost", "cid": 9})},
    argv=[bp, "gid-spost"])
record("preflight-ship-post-receipt-dedup", code == 1 and "dup" in out, out.strip()[-60:])

# W14 + wave-6 W6-18/W6-26: ALL THREE forwarders REFUSE https (raw-TCP pipe, named exit 2) and honor explicit http ports
for _fw5 in ("scripts/fwd_18080.py", "scripts/strata_forward_18080.py", "scripts/twin_proxy_8082.py"):
    _fp5 = os.path.join(REPO, _fw5)
    _nm5 = _fw5.split("/")[-1].split(".")[0]
    os.environ["ORGANS_SEAT_URL"] = "https://seat.example"
    _rc5 = None; _buf5b = io.StringIO()
    try:
        with contextlib.redirect_stdout(_buf5b):
            exec(compile(open(_fp5, encoding="utf-8").read().replace(chr(13) + chr(10), chr(10)), _fp5, "exec"), {"__name__": "lib", "__file__": _fp5})
    except SystemExit as _e5:
        _rc5 = _e5.code if isinstance(_e5.code, int) else 1
    except (Exception, SystemExit) as _e5:
        _rc5 = "EXC " + repr(_e5)
    del os.environ["ORGANS_SEAT_URL"]
    record("fwd-https-refused-" + _nm5, _rc5 == 2 and "FORWARDER-HTTPS-UNSAFE" in _buf5b.getvalue(), "rc=" + str(_rc5) + " " + _buf5b.getvalue().strip()[:60])
    os.environ["ORGANS_SEAT_URL"] = "http://seat.example:18081"
    _ns5b = {"__name__": "lib", "__file__": _fp5}
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(open(_fp5, encoding="utf-8").read().replace(chr(13) + chr(10), chr(10)), _fp5, "exec"), _ns5b)
        _t5b = _ns5b.get("TARGET")
    except (Exception, SystemExit) as _e5b:
        _t5b = "EXC " + repr(_e5b)
    del os.environ["ORGANS_SEAT_URL"]
    record("fwd-http-port-" + _nm5, _t5b == ("seat.example", 18081), str(_t5b))

# W02: config index_rules outrank EVERY extension catch-all (.md->prose shadowed them)
_td5 = tempfile.mkdtemp(prefix="bi5_"); _kits = os.path.join(_td5, "kitsrc", "index"); os.makedirs(_kits)
shutil.copy(os.path.join(REPO, "index/build_index.py"), os.path.join(_kits, "build_index.py"))
open(os.path.join(_kits, "local.json"), "w", encoding="utf-8").write(json.dumps({"index_rules": [["kid-thing", "kid-letter"]]}))
_shop5 = os.path.join(_td5, "shop"); os.makedirs(_shop5, exist_ok=True)
_leg5 = os.path.join(_td5, "leg"); os.makedirs(_leg5, exist_ok=True)  # LEG root exists empty (rig refuses missing roots)
open(os.path.join(_shop5, "kid-thing.md"), "w", encoding="utf-8").write("# kid" + chr(10))
_bi5 = os.path.join(_kits, "build_index.py")
_saved5 = os.environ.get("ORGANS_HOME"); _saved5s = os.environ.get("ORGANS_SHOP_DIR"); _saved5l = os.environ.get("ORGANS_LEG_DIR")  # wave-6 W6-27: LEG_DIR restored too (no env leak)
os.environ["ORGANS_HOME"] = _td5
os.environ["ORGANS_SHOP_DIR"] = _shop5  # the fixture's indexed root IS the scratch shop (config would resolve to the live shop)
os.environ["ORGANS_LEG_DIR"] = _leg5
_buf5 = io.StringIO()
try:
    with contextlib.redirect_stdout(_buf5):
        exec(compile(open(_bi5, encoding="utf-8").read().replace(chr(13) + chr(10), chr(10)), _bi5, "exec"),
             {"__name__": "__main__", "__file__": _bi5})
    _con5 = _s3w5.connect(os.path.join(_shop5, "index", "index.db"))
    _fam5 = _con5.execute("SELECT family FROM files WHERE name = ?", ("kid-thing.md",)).fetchall()
    _con5.close()
except (Exception, SystemExit) as _e5:  # SystemExit is a BaseException -- rig mains exit via it
    _fam5 = [("EXC " + repr(_e5) + " | out: " + _buf5.getvalue().strip()[-160:])]
finally:
    if _saved5 is None: os.environ.pop("ORGANS_HOME", None)
    else: os.environ["ORGANS_HOME"] = _saved5
    if _saved5s is None: os.environ.pop("ORGANS_SHOP_DIR", None)
    else: os.environ["ORGANS_SHOP_DIR"] = _saved5s
    if _saved5l is None: os.environ.pop("ORGANS_LEG_DIR", None)
    else: os.environ["ORGANS_LEG_DIR"] = _saved5l
record("index-config-rules-outrank-catchall", _fam5 == [("kid-letter",)], str(_fam5))

# W07 (LAWS #23): zero-content samplers refuse. Dead seat door + nvidia-smi resolving to a
# CWD decoy that dies on the query args => rows of timestamps/None-reads only => exit 1.
_nv5 = tempfile.mkdtemp(prefix="nv5_")
shutil.copy(sys.executable, os.path.join(_nv5, "nvidia-smi.exe"))
_hr5 = tempfile.mkdtemp(prefix="zh5_")
for _rgs5, _args5 in (("skin_sampler.py", ["1"]), ("sit_sampler.py", ["1", "w5zero"])):
    _r5 = subprocess.run([sys.executable, os.path.join(REPO, "scripts/skin", _rgs5)] + _args5,
                         cwd=_nv5, capture_output=True, text=True, timeout=90,
                         env=dict(os.environ, ORGANS_HOME=_hr5, ORGANS_SEAT_URL="http://127.0.0.1:1"))
    record("sampler-zero-content-refuse-" + _rgs5.split(".")[0],
           _r5.returncode == 1 and "ZERO-content" in _r5.stdout,
           "rc=" + str(_r5.returncode) + " " + _r5.stdout.strip()[-50:])

# W08 + wave-6 W6-15: malformed cadence env is a READER advisory -- and the leg is HERMETIC now
# (the old form inherited the live estate jobs/ledger: it passed green on THIS machine only, by accident)
_greenjob6 = [{"name": "a", "script": "", "enabled": True, "schedule": {"kind": "interval", "minutes": 10, "display": "every 10m"}, "last_status": "ok"}]
_cad("malformed-env-is-reader-advisory-hermetic", _greenjob6, 0, ("READER ADVISORY",), ("Traceback", "BELL CENSUS"),
     {"ORGANS_COUNTER_WINDOW": "abc", "ORGANS_TZ_OFFSET": "zz"})

# ================= WAVE-6 red-path legs (deleg_5185ca9e cure proofs, 2026-11-12) =================
import urllib.error as _ue6
import http.server as _hs6
import threading as _th6

# W6-02: a zero-work run must NOT clobber the existing receipt store (LAWS #22 citations survive)
_seedrec6 = json.dumps([{"ship": 9, "post": 40, "comment_id": 99, "readback": "OK", "ts": "t"}])
code, out, tree6, calls6, home6 = run_rig(sq, router_sq, {QF: "no ships in this queue" + chr(10),
                                                          "data/ship-queue-receipts-20261111.json": _seedrec6})
_pers6 = tree6.get("data/ship-queue-receipts-20261111.json")
record("queue-zero-work-preserves-receipts", code == 3 and _pers6 == _seedrec6,
       "rc=" + str(code) + " store=" + ("INTACT" if _pers6 == _seedrec6 else "CLOBBERED"))

# W6-03: door answering ok=False (verdict flag, zero metrics) + dead nvidia = ZERO-content refusal.
# The wave-5 W07 counter counted the state string as content; this fixture is the exact bypass shape.
class _H6(_hs6.BaseHTTPRequestHandler):
    def do_GET(self):
        _b6 = json.dumps({"ok": False}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(_b6)))
        self.end_headers()
        self.wfile.write(_b6)
    def log_message(self, *a):
        pass
_srv6 = _hs6.HTTPServer(("127.0.0.1", 0), _H6)
_th6.Thread(target=_srv6.serve_forever, daemon=True).start()
_r6 = subprocess.run([sys.executable, os.path.join(REPO, "scripts/skin", "skin_sampler.py"), "1"],
                     cwd=_nv5, capture_output=True, text=True, timeout=90,
                     env=dict(os.environ, ORGANS_HOME=tempfile.mkdtemp(prefix="sh6_"),
                              ORGANS_SEAT_URL="http://127.0.0.1:" + str(_srv6.server_address[1])))
_srv6.shutdown()
record("sampler-okFalse-shell-is-not-content", _r6.returncode == 1 and "ZERO-content" in _r6.stdout,
       "rc=" + str(_r6.returncode) + " " + _r6.stdout.strip()[-50:])

# W6-08: dedup door answering under drifted grammar (no comments/post keys) = fail-closed, never hash-empty
def router_gram6(p, req):
    if p.startswith("/api/post/100"):
        return {"items": [], "has_more": False}
    if p == "/api/me":
        return {"me": {"handle": "tester", "today": {"comments_remaining": 8}}}
    return {}
code, out, *_ = run_rig(sq, router_gram6, {QF: q_green})
record("queue-dedup-grammar-unreadable-closed", code == 2 and "GRAMMAR UNREADABLE" in out,
       "rc=" + str(code) + " " + out.strip()[-60:])

# W6-09: a door serving a constant cursor with has_more=True must NOT loop forever
def router_noprogress6(p, req):
    if p.startswith("/api/post/100"):
        return {"comments": [], "has_more": True, "next_since": "s1", "post": {"body": "post body"}}
    if p == "/api/me":
        return {"me": {"handle": "tester", "today": {"comments_remaining": 8}}}
    return {}
code, out, *_ = run_rig(sq, router_noprogress6, {QF: q_green})
record("queue-pagination-no-progress-gate", code == 2 and "NO PROGRESS" in out,
       "rc=" + str(code) + " " + out.strip()[-60:])

# W6-07: an ambiguous WRITE failure is never retried (double-landing class, B5 proof)
_postct6 = [0]
def router_wretry6(p, req):
    if p.startswith("/api/post/100"):
        return {"comments": [], "has_more": False, "post": {"body": "post body"}}
    if p == "/api/me":
        return {"me": {"handle": "tester", "today": {"comments_remaining": 8}}}
    if p == "/api/comment" and req.data:
        _postct6[0] += 1
        raise _ue6.URLError("connection dropped after commit")
    return {}
code, out, *_ = run_rig(sq, router_wretry6, {QF: q_green})
record("queue-ambiguous-write-never-retried", _postct6[0] == 1 and "NOT retrying" in out,
       "rc=" + str(code) + " POST_attempts=" + str(_postct6[0]))

# W6-04/W6-05: all three write rigs import the SAME screen module; the email shape gates the queue
_sp6 = open(os.path.join(REPO, "scripts/venue/ship_post_20261111.py"), encoding="utf-8").read()
_pf6 = open(os.path.join(REPO, "scripts/venue/preflight_1f916.py"), encoding="utf-8").read()
_sq6 = open(sq, encoding="utf-8").read()
record("screens-single-source-of-truth",
       "_screen.BAD" in _sp6 and "_screen.SCREENS" in _pf6 and "_screen.SCREENS" in _sq6,
       "ship_post/preflight/queue import scripts/screen.py")
_body_em = "mail me at somebody@example.com to continue the thread"
_dg_em = _h.sha256(_body_em.encode("utf-8")).hexdigest()
_q_em = "## 1. post 100 parent 50" + chr(10) + _body_em + chr(10) + chr(10) + "INTENT PINS" + chr(10) + "PINDIGEST post 100 ship 1 sha256 " + _dg_em + chr(10)
code, out, *_ = run_rig(sq, router_sq, {QF: _q_em})
record("queue-email-body-gates-full-grammar", code == 2 and "email" in out, "rc=" + str(code) + " " + out.strip()[:60])

# W6-10: config key bell_firings RELOCATES the phase leg (chain must be proven, not documented-only).
# Drift fixture lands in the CONFIG file; HOME default holds a clean file. Advisory => config was read.
_td6b = tempfile.mkdtemp(prefix="cc6_")
_cad6 = os.path.join(_td6b, "cad6.py")
shutil.copy(os.path.join(REPO, "scripts/cadence_audit.py"), _cad6)
_drift6 = os.path.join(_td6b, "drift.jsonl")
open(_drift6, "w", encoding="utf-8").write(
    json.dumps({"job": "a", "last_run": "2026-11-12T00:00:00-06:00"}) + chr(10) +
    json.dumps({"job": "a", "last_run": "2026-11-12T00:05:00-06:00"}) + chr(10) +
    json.dumps({"job": "a", "last_run": "2026-11-12T00:10:00-06:00"}) + chr(10) +
    json.dumps({"job": "a", "last_run": "2026-11-12T00:15:00-06:00"}) + chr(10))
_clean6 = os.path.join(_td6b, "clean.jsonl")
open(_clean6, "w", encoding="utf-8").write(
    json.dumps({"job": "a", "last_run": "2026-11-12T00:00:00-06:00"}) + chr(10) +
    json.dumps({"job": "a", "last_run": "2026-11-12T00:10:00-06:00"}) + chr(10) +
    json.dumps({"job": "a", "last_run": "2026-11-12T00:20:00-06:00"}) + chr(10))
open(os.path.join(_td6b, "local.json"), "w", encoding="utf-8").write(json.dumps({"bell_firings": _drift6}))
os.makedirs(os.path.join(_td6b, "data"), exist_ok=True)
open(os.path.join(_td6b, "data", "bell-firings.jsonl"), "w", encoding="utf-8").write(
    json.dumps({"job": "a", "last_run": "2026-11-12T00:00:00-06:00"}) + chr(10) +
    json.dumps({"job": "a", "last_run": "2026-11-12T00:10:00-06:00"}) + chr(10) +
    json.dumps({"job": "a", "last_run": "2026-11-12T00:20:00-06:00"}) + chr(10))
_jp6b = os.path.join(_td6b, "jobs.json")
json.dump({"jobs": _greenjob6}, open(_jp6b, "w", encoding="utf-8"))
_env6b = dict(os.environ, ORGANS_JOBS=_jp6b, ORGANS_LEDGER=os.path.join(_td6b, "missing.md"),
             ORGANS_HOME=_td6b, ORGANS_SECRETS=_td6b, ORGANS_SHOP_DIR=_td6b, ORGANS_TZ_OFFSET="-6")
_env6b.pop("ORGANS_BELL_FIRINGS", None)
_r6b = subprocess.run([sys.executable, _cad6], capture_output=True, text=True, env=_env6b, timeout=120)
_out6b = _r6b.stdout + _r6b.stderr
record("cadence-config-bell-firings-chain", "PHASE" in _out6b, "rc=" + str(_r6b.returncode) + " " + _out6b[:90])

# W6-12/W6-13/W6-21: cadence reader advisories -- out-of-range TZ, nan/abc threshold.
# Config defect = disclosed advisory; never a bell alert, never a Traceback.
_cad("tz-out-of-range-advisory", _greenjob6, 0, ("READER ADVISORY",), ("Traceback",), {"ORGANS_TZ_OFFSET": "25"})
_cad("threshold-nan-advisory", _greenjob6, 0, ("READER ADVISORY",), ("Traceback",), {"CADENCE_THRESHOLD": "nan"})
_cad("threshold-abc-advisory", _greenjob6, 0, ("READER ADVISORY",), ("Traceback",), {"CADENCE_THRESHOLD": "abc"})

# ================= WAVE-7 red-path legs (deleg_6ee9334b cure proofs, 2026-11-12) =================
# 17 findings; blockers all screen/union fail-open directions. Hermetic: gates fire before doors;
# urlopen mocked on the transport leg; SECRET stubs carry a fake value, label only.
import urllib.error as _ue7

_SP7 = os.path.join(REPO, "scripts/venue/ship_post_20261111.py")
_PF7 = os.path.join(REPO, "scripts/venue/preflight_1f916.py")
_CH7 = os.path.join(REPO, "scripts/counter_head.py")
_GH7 = os.path.join(REPO, "scripts/molt/gguf_hist.py")

def _home7(tag):
    h = tempfile.mkdtemp(prefix="w7-" + tag + "-")
    os.makedirs(os.path.join(h, "data"), exist_ok=True)
    os.makedirs(os.path.join(h, "ledgers"), exist_ok=True)
    s = tempfile.mkdtemp(prefix="w7sec-")
    json.dump({"secret": "F-STUB-VALUE-NEVER-PRINTED"}, open(os.path.join(s, "1f916.json"), "w", encoding="utf-8"))
    return h, s

def _sp7(label, body_text, want_rc, want_in):
    h, s = _home7("sp")
    bf = os.path.join(h, "body.txt")
    open(bf, "w", encoding="utf-8").write(body_text)
    r = subprocess.run([sys.executable, _SP7, "Wave7 proof title", bf], capture_output=True, text=True,
                       timeout=90, env=dict(os.environ, ORGANS_HOME=h, ORGANS_SECRETS=s))
    out = r.stdout + r.stderr
    record(label, r.returncode == want_rc and want_in in out and "Traceback (most recent call last)" not in out,
           "rc=" + str(r.returncode) + " " + out.strip()[-70:])

_sp7("w7-post-screens-email-F1", "digest line contact root@example.org tail " * 3, 2, "SCREEN[email]")
_sp7("w7-post-refuses-empty-body-F16", "", 2, "BODY GATE: empty body")

# F3b/F3c: shared screen grammar unit -- uppercase SK- screened; dotted (JWT-shaped) token joins the run
sys.path.insert(0, os.path.join(REPO, "scripts"))
import screen as _sc7
_sk7 = any(rx.search("prefix SK-ABCDEFGHIJKLMNOP tail") for nm, rx in _sc7.SCREENS)
_jwt7 = "header." + "a" * 20 + "." + "b" * 25
_jt7 = any(rx.search(_jwt7) for nm, rx in _sc7.SCREENS)
record("w7-screen-sk-case-jwt-join-F3b-F3c", _sk7 and _jt7, f"SK={_sk7} JWT={_jt7}")

# F2/F4: preflight union -- shadowed comment_id reads LANDED; id-less dict is corrupt (fail-closed)
_h4, _s4 = _home7("pf")
_bf4 = os.path.join(_h4, "b.txt"); open(_bf4, "w", encoding="utf-8").write("proof body for preflight " * 5)
_rp4 = os.path.join(_h4, "data", "ship-post-receipt-1.json")
json.dump([{"post": 4647, "comment_id": 143472, "title": "t"}], open(_rp4, "w", encoding="utf-8"))
_r = subprocess.run([sys.executable, _PF7, _bf4, "143472"], capture_output=True, text=True, timeout=90,
                    env=dict(os.environ, ORGANS_HOME=_h4, ORGANS_SECRETS=_s4))
record("w7-preflight-shadowed-comment-landed-F2", _r.returncode == 1 and "ALREADY LANDED, SKIP" in _r.stdout, "rc=" + str(_r.returncode) + " " + _r.stdout.strip()[-60:])
json.dump([{}], open(_rp4, "w", encoding="utf-8"))
_r = subprocess.run([sys.executable, _PF7, _bf4, "143472"], capture_output=True, text=True, timeout=90,
                    env=dict(os.environ, ORGANS_HOME=_h4, ORGANS_SECRETS=_s4))
record("w7-preflight-idless-dict-closed-F4", _r.returncode == 1 and "gate CLOSED (fail-closed)" in _r.stdout, "rc=" + str(_r.returncode) + " " + _r.stdout.strip()[-60:])

# F8: malformed last_run_at is a READER advisory, never a manufactured never-fired miss
_j8 = [{"name": "malformed-stamp", "enabled": True, "state": "scheduled", "last_status": "ok",
        "schedule": {"kind": "interval", "display": "every 10m"}, "last_run_at": "NOT-A-DATE",
        "next_run_at": "2026-11-12T00:00:00-06:00", "failure_streak": 0}]
_cad("w7-cadence-malformed-stamp-advisory-F8", _j8, 0, ("CADENCE-ADVISORY: malformed last_run_at",),
     ("never-fired past-due", "Traceback (most recent call last)"))
# F20: seconds grammar visible to the census -- a stale every-30s bell READS as a miss
_j20 = [{"name": "thirty", "enabled": True, "state": "scheduled", "last_status": "ok",
         "schedule": {"kind": "interval", "display": "every 30s"},
         "last_run_at": "2026-11-12T05:30:00-06:00", "next_run_at": "2026-11-12T06:00:00-06:00", "failure_streak": 0}]
_cad("w7-cadence-30s-grammar-visible-F20", _j20, 1, ("MISS:", "every 30s"), ("Traceback (most recent call last)",),
     extra_env={"CADENCE_NOW": "2026-11-12T06:00:00-06:00"})

# F25: job-less firing record skipped with advisory; leg survives
_f25 = tempfile.mktemp(suffix=".jsonl")
_now25 = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-6)))
open(_f25, "w", encoding="utf-8").write(json.dumps({"last_run": (_now25 - datetime.timedelta(seconds=60)).isoformat()}) + "\n")
_jf = [{"name": "ok-bell", "enabled": True, "state": "scheduled", "last_status": "ok",
        "schedule": {"kind": "interval", "display": "every 10m"},
        "last_run_at": (_now25 - datetime.timedelta(seconds=60)).isoformat(),
        "next_run_at": (_now25 + datetime.timedelta(seconds=540)).isoformat(), "failure_streak": 0}]
_cad("w7-cadence-jobless-firing-skipped-F25", _jf, 0, ("firing record without 'job' key skipped",),
     ("Traceback (most recent call last)",), extra_env={"ORGANS_BELL_FIRINGS": _f25})

# F12/F13: carrier alerts at failure_streak>=2 (register read in CODE); carrier identity is basename, not path substring
_j12 = [
    {"name": "cadence-audit-daily", "enabled": True, "state": "scheduled", "last_status": "error",
     "schedule": {"kind": "interval", "display": "every 1d"}, "script": "C:/x/shop3/scripts/cadence_audit.py",
     "last_run_at": "2026-11-12T07:05:00-06:00", "next_run_at": "2026-11-13T07:05:00-06:00", "failure_streak": 2},
    {"name": "innocent", "enabled": True, "state": "scheduled", "last_status": "error",
     "schedule": {"kind": "interval", "display": "every 10m"}, "script": "C:/x/cadence_audit_notes/totally_other.py",
     "last_run_at": "2026-11-12T05:56:00-06:00", "next_run_at": "2026-11-12T06:06:00-06:00", "failure_streak": 1},
]
_cad("w7-cadence-carrier-streak2-alert-F12", _j12, 1, ("CARRIER DEATH streak 2", "LIVE-RED: innocent"),
     ("Traceback (most recent call last)",), extra_env={"CADENCE_NOW": "2026-11-12T06:00:00-06:00"})

# F9: contiguity walks PAIRS; scattered pairs read False, a real chain reads True. F18: missing ledger is advisory exit 2.
_h9, _s9 = _home7("ch")
_led9 = os.path.join(_h9, "ledgers", "CORPUS.md")
open(_led9, "w", encoding="utf-8").write(
    "| a | 2026-11-11 | old Counter 99->100 quoted prose Counter 5000->5001 |\n"
    "| b | 2026-11-12 | head C5-9 Counter 101->102 |\n")
_r = subprocess.run([sys.executable, _CH7], capture_output=True, text=True, timeout=60,
                    env=dict(os.environ, ORGANS_HOME=_h9))
record("w7-counter-pairwalk-scattered-F9", _r.returncode == 0 and "contiguous(5 back): False" in _r.stdout, "rc=" + str(_r.returncode) + " " + _r.stdout.strip()[-70:])
open(_led9, "w", encoding="utf-8").write("".join(
    "| c%d | 2026-11-12 | C5-10%d body Counter %d->%d |\n" % (i, i, 100 + i, 101 + i) for i in range(5)))
_r = subprocess.run([sys.executable, _CH7], capture_output=True, text=True, timeout=60,
                    env=dict(os.environ, ORGANS_HOME=_h9))
record("w7-counter-pairwalk-chain-F9", _r.returncode == 0 and "contiguous(5 back): True" in _r.stdout, "rc=" + str(_r.returncode) + " " + _r.stdout.strip()[-70:])
_h18, _s18 = _home7("ch18")
_r = subprocess.run([sys.executable, _CH7], capture_output=True, text=True, timeout=60,
                    env=dict(os.environ, ORGANS_HOME=_h18))
record("w7-counter-missing-ledger-advisory-F18", _r.returncode == 2 and "no ledger at" in _r.stdout and "Traceback (most recent call last)" not in _r.stdout + _r.stderr,
       "rc=" + str(_r.returncode) + " " + _r.stdout.strip()[-70:])

# F23: truncated GGUF header refuses with a named gate, not struct.error
_g7 = tempfile.mktemp(suffix=".gguf"); open(_g7, "wb").write(b"GGUF")
_r = subprocess.run([sys.executable, _GH7, _g7], capture_output=True, text=True, timeout=60)
record("w7-gguf-header-truncated-refuse-F23", _r.returncode == 2 and "HEADER-TRUNCATED" in _r.stdout and "struct.error" not in _r.stderr,
       "rc=" + str(_r.returncode) + " " + (_r.stdout + _r.stderr).strip()[-70:])

# F17: POST transport death names itself (hermetic: non-GET raises in the mock)
_h17, _s17 = _home7("sp17")
_bf17 = os.path.join(_h17, "b.txt"); open(_bf17, "w", encoding="utf-8").write("clean proof body with no sensitive shapes " * 2)
_mk17 = os.path.join(_h17, "mock.py")
open(_mk17, "w", encoding="utf-8").write(
    "import sys, urllib.request, urllib.error, runpy\n"
    "def _r(q, *a, **k): raise urllib.error.URLError('hermetic: write door refused')\n"
    "urllib.request.urlopen = _r\n"
    "sys.argv = [r\"" + _SP7.replace("\\", "/") + "\", \"Proof title\", r\"" + _bf17.replace("\\", "/") + "\"]\n"
    "runpy.run_path(sys.argv[0], run_name=\"__main__\")\n")
_r = subprocess.run([sys.executable, _mk17], capture_output=True, text=True, timeout=90,
                    env=dict(os.environ, ORGANS_HOME=_h17, ORGANS_SECRETS=_s17))
record("w7-post-transport-death-named-F17", _r.returncode == 1 and "POST DOOR: transport death" in _r.stdout and "Traceback (most recent call last)" not in _r.stdout + _r.stderr,
       "rc=" + str(_r.returncode) + " " + (_r.stdout + _r.stderr).strip()[-70:])

# F1/F14/F22/F5: source-grammar legs (receipt name carries pid; page cap fires at 200; ship_post runs the FULL SCREENS list; write door isinstance gate)
_srcpost = open(_SP7, encoding="utf-8").read()
_srcsq7 = open(sq, encoding="utf-8").read()
record("w7-post-runs-full-screens-F1", "_screen.SCREENS" in _srcpost, "post imports full grammar")
record("w7-post-receipt-name-carries-pid-F14", "ship-post-receipt-{int(time.time())}-{pid}" in _srcpost, "receipt name is per-post")
record("w7-queue-pagecap-fires-at-200-F22", "gate(pages6 < 200" in _srcsq7, "cap gate named")
# F5 behavioral leg: POST door answering non-dict closes fail-closed, no .get crash
def _router_nd7(p, req):
    if p.startswith("/api/post/100") and req.data is None: return {"comments": [], "has_more": False, "post": {"body": "post body"}}
    if p == "/api/me": return {"me": {"handle": "tester", "today": {"comments_remaining": 8}}}
    if p == "/api/comment" and req.data: return ["NOT", "A", "DICT"]
    return {}
code, out, *_ = run_rig(sq, _router_nd7, {QF: q_green})
record("w7-queue-nondict-write-door-closed-F5", code == 1 and "WRITE DOOR NON-DICT" in out and "Traceback (most recent call last)" not in out,
       "rc=" + str(code) + " " + out.strip()[-70:])

# ---------- venue-rig family legs (packaging cure 2026-11-13; F-META law: fire fixtures at the
# real door, zero network): runlib venue() guards, SEC-chain resolution, sweep cold-seed refusal
import importlib as _il
_scr = tempfile.mkdtemp(prefix="organs_v_")
_sec = os.path.join(_scr, "sec"); os.makedirs(_sec)
json.dump({"resident_key": "test-resident-key"}, open(os.path.join(_sec, "1f3d9.json"), "w"))
os.environ["ORGANS_SECRETS"] = _sec
os.environ["ORGANS_HOME"] = os.path.join(_scr, "home")
sys.path.insert(0, os.path.join(REPO, "scripts"))
_rl = _il.import_module("runlib")
_real = urllib.request.urlopen
def _mkdoor(obj):
    def _d(req, timeout=None): return FakeResp(json.dumps(obj).encode())
    return _d
for _nm, _door, _want in (
    ("iserror", _mkdoor({"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"{\"error_class\":\"bad_input\"}"}],"isError":True}}), "TOOL-ERR"),
    ("empty", _mkdoor({"jsonrpc":"2.0","id":1,"result":{"content":[]}}), "RPC-EMPTY"),
    ("nonjson", _mkdoor({"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"not json at all"}],"isError":False}}), "RPC-NONJSON"),
    ("ok-shape", _mkdoor({"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"{\"change_marker\":\"99\"}"}],"isError":False}}), None)):
    urllib.request.urlopen = _door
    _b = io.StringIO()
    try:
        with contextlib.redirect_stdout(_b):
            _r = _rl.venue("changes", {"since": "1", "limit": 1})
    finally:
        urllib.request.urlopen = _real
    _ok = (_r is None and _want in _b.getvalue()) if _want else (isinstance(_r, dict) and _r.get("change_marker") == "99")
    record(f"venue-door-{_nm}", _ok, _b.getvalue().strip()[:60])
record("venue-sec-chain-resolves", os.path.isfile(os.path.join(_rl._organs_sec(), "1f3d9.json")),
       "token file lands at the SEC chain door")
record("venue-home-chain-env-wins", _rl._organs_home() == os.path.join(_scr, "home"), "env outranks config files")
_scr2 = tempfile.mkdtemp(prefix="organs_s_"); _sec2 = os.path.join(_scr2, "sec"); os.makedirs(_sec2)
_routes_scr = os.path.join(_scr2, "ROUTES.md")
open(_routes_scr, "w", encoding="utf-8").write("venue door: changes rides POST /mcp tools/call on https://1f3d9.com/mcp; limit int, since string\n")
# NO 1f3d9.json in _sec2: token open dies inside venue() -> rig's seed try catches -> refuse blind sweep
code, out, *_ = run_rig(os.path.join(REPO, "scripts/sweep_organ_v2.py"), lambda p, req: {},
                        env={"ORGANS_SECRETS": _sec2, "ORGANS_ROUTES": _routes_scr})
record("sweep-coldseed-dead-door-exit2", code == 2 and "SEED-FAIL" in out and "Traceback (most recent call last)" not in out,
       "rc=" + str(code) + " " + out.strip()[-70:])
_sg = _il.import_module("scan_organ")
record("scan-organ-twin-behavior", _sg.gate("plain prose with no shape at all") == []
       and len(_sg.gate("Bearer AbCdEf1234567890AbCdEf1234567890")) >= 1, "clean [] / token flagged")

# after_restart organ legs (2026-11-13, behavior-at-door): probe routes fired at fixture doors.
# Green leg: all fixture doors 200 -> rc0 reds0. Red leg: honcho door aimed at a CLOSED port ->
# rc2 and a RED row. relit() itself is never fired in-suite (it binds estate twin ports);
# its upstream-dead guard specimen lives in the estate census log (data/after-restart.log).
import http.server, socketserver, threading
class _ArFx(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body):
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        self._send(200, b'{"object":"list","data":[]}') if self.path.startswith("/v1/models") else self._send(404, b"{}")
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", "0") or 0))
        self._send(200, b'[]') if self.path.endswith("/conclusions/query") else self._send(404, b"{}")
    def log_message(self, *a): pass
_ar_srv = socketserver.TCPServer(("127.0.0.1", 0), _ArFx)
threading.Thread(target=_ar_srv.serve_forever, daemon=True).start()
_fx = "http://127.0.0.1:%d" % _ar_srv.server_address[1]
_ar = os.path.join(REPO, "scripts/after_restart.py")
def _ar_run(env):
    r = subprocess.run([sys.executable, _ar, "--probe-only", "--json"], capture_output=True, text=True, timeout=90, env=env)
    row = next((l for l in r.stdout.splitlines() if l.startswith("{")), "{}")
    return r, json.loads(row)
_ar_env = dict(os.environ, ORGANS_SEAT_URL=_fx, ORGANS_HONCHO_URL=_fx, ORGANS_EMBED_URL=_fx, ORGANS_SKIP_DOCKER="1")
_r, _d = _ar_run(_ar_env)
record("after-restart-probe-green",
       _r.returncode == 0 and _d.get("reds") == 0
       and all(s in ("PASS", "SKIP(env)") for n, c, s in _d["rows"] if c == "core")
       and any(n.startswith("twin-") for n, c, s in _d["rows"]),
       f"rc={_r.returncode} rows={len(_d.get('rows', []))}")
_ck = socket.socket(); _ck.bind(("127.0.0.1", 0)); _cp = _ck.getsockname()[1]; _ck.close()
_r2, _d2 = _ar_run(dict(_ar_env, ORGANS_HONCHO_URL="http://127.0.0.1:%d" % _cp))
record("after-restart-red-path-exit2",
       _r2.returncode == 2 and _d2.get("reds", 0) >= 1
       and any(n == "honcho-:8000" and "RED" in s for n, c, s in _d2["rows"]),
       f"rc={_r2.returncode} reds={_d2.get('reds')}")
_ar_srv.shutdown()

# ---------- manifest pin (adopted 2026-11-14 from lucykimi c145856: a walk-discovered
# suite makes a rename free -- file moved + string inside rewritten to match still passes
# every grep-the-recorded-path leg while external refs to the old name die quietly.
# Pin = this checked-in reviewed inventory; rename/delete/add of any pinned .py must
# touch THIS list to stay green. Falsifier: rename scripts/screen.py -> leg RED, named.)
MANIFEST_PY = [
    'index/build_index.py',
    'scripts/after_restart.py',
    'scripts/bar_audit.py',
    'scripts/boardwalk_beat.py',
    'scripts/cadence_audit.py',
    'scripts/census_organ.py',
    'scripts/counter_head.py',
    'scripts/twin_sync.py',
    'scripts/dream_beat.py',
    'scripts/fire_genre.py',
    'scripts/fwd_18080.py',
    'scripts/hf_mirror.py',
    'scripts/inbox_gate.py',
    'scripts/inbox_leg.py',
    'scripts/inbox_walk2.py',
    'scripts/mesh_leg.py',
    'scripts/mirror_audit.py',
    'scripts/molt/b4_taste.py',
    'scripts/molt/batch.py',
    'scripts/molt/gguf_hist.py',
    'scripts/molt/pointers.py',
    'scripts/pipes_beat.py',
    'scripts/register_audit.py',
    'scripts/routes_ledger.py',
    'scripts/run_rig.py',
    'scripts/runlib.py',
    'scripts/scan_organ.py',
    'scripts/screen.py',
    'scripts/seat_score.py',
    'scripts/ship_queue_20261111.py',
    'scripts/skin/sit_sampler.py',
    'scripts/skin/skin_sampler.py',
    'scripts/skin/window.py',
    'scripts/strata_forward_18080.py',
    'scripts/surface_monitor.py',
    'scripts/sweep_organ_v2.py',
    'scripts/truncation_sweep.py',
    'scripts/tts_clip.py',
    'scripts/twin_fwd.py',
    'scripts/twin_proxy_8082.py',
    'scripts/venue/preflight_1f916.py',
    'scripts/venue/rid_line.py',
    'scripts/venue/ship_post_20261111.py',
    'scripts/vw_unified.py',
    'tests/run_all.py',
]
_found_py = sorted(os.path.relpath(os.path.join(r, f), REPO).replace(os.sep, "/")
                   for r, _, fs in os.walk(REPO)
                   for f in fs if f.endswith(".py")
                   and "__pycache__" not in r and ".git" not in r)
_missing = sorted(set(MANIFEST_PY) - set(_found_py))
_extra = sorted(set(_found_py) - set(MANIFEST_PY))
record("manifest-pin-inventory", not _missing and not _extra,
       "pinned=%d found=%d missing=%s extra=%s" % (len(MANIFEST_PY), len(_found_py), _missing, _extra))

# invocation-holder leg (lucykimi c145906 datum, adopted 2026-11-14): the manifest
# pins tests/run_all.py INSIDE the harness -- the pin is inert against a rename
# (rename kills the checker with it), so every self-check bottoms out at a name
# held outside the checked set. The cheap holder is the README invocation line;
# the harness CAN pin the README (it lives inside the checked set, outside itself).
# The leg goes red when the invocation text leaves the README.
# sibling-case cure (lucykimi c145961 un-fired branch, fired 2026-11-14): a bare
# open(README) CRASHES the harness when the file is gone -- red by process death
# (rc 1, traceback), not a named leg. Same loudness, worse legibility: the run
# dies mid-inventory and the record stream loses every leg after it. The cure
# keeps the crash's loudness (rc 1 via red leg) and names the defect.
try:
    _readme = open(os.path.join(REPO, "README.md"), encoding="utf-8").read()
    _readme_ok = True
except FileNotFoundError:
    _readme, _readme_ok = "", False
_holders = _readme_ok and all(s in _readme for s in ("python tests/run_all.py", "--live", "sandbox suite"))
record("invocation-holder-readme", _holders,
       "README invocation lines present=%s (file present=%s)" % (_holders, _readme_ok))

# twin-sync leg (CATCHES 301 cure organ, built 2026-11-14 after the bell-death twin drift):
# fires scripts/twin_sync.py in a sandbox -- synthetic identical copies must read GREEN rc0,
# synthetic mutation must read RED rc1 with a NAMED drift line (red-path fired, LAWS.md #4).
import subprocess as _sp, tempfile as _tf
_ts = os.path.join(REPO, "scripts", "twin_sync.py")
_scr = _tf.mkdtemp(prefix="organs_tw_")
_d1, _d2, _d3 = [os.path.join(_scr, x) for x in ("a", "b", "c")]
for _d in (_d1, _d2, _d3): os.makedirs(_d)
open(os.path.join(_d1, "rig.py"), "w").write("x = 1\n")
open(os.path.join(_d2, "rig.py"), "w").write("x = 1\n")
open(os.path.join(_d3, "rig.py"), "w").write("x = 1\n")
_mf = os.path.join(_scr, "manifest.json")
json.dump({"twin_rigs": ["rig.py"], "twin_dirs": [_d1, _d2, _d3]}, open(_mf, "w"))
_env = dict(os.environ, ORGANS_TWIN_MANIFEST=_mf)
_g = _sp.run([sys.executable, _ts], capture_output=True, text=True, env=_env)
open(os.path.join(_d2, "rig.py"), "w").write("x = 2  # synthetic drift\n")
_r = _sp.run([sys.executable, _ts], capture_output=True, text=True, env=_env)
ok = (_g.returncode == 0 and _r.returncode == 1 and "DRIFT rig.py" in _r.stdout)
record("twin-sync-leg", ok, f"green rc{_g.returncode} red rc{_r.returncode} named-drift-printed={'DRIFT' in _r.stdout}")

# ---------- Tier-1 standards legs (MOLT4 Phase C): one red-path fire per new organ,
# all through the run_rig harness (mocked urlopen, scratch HOME/SEC). Zero network:
# every leg asserts the door-call list stays empty where no door should be touched.

# mesh_leg: mint slot-collision must REFUSE rc4 BEFORE any fire (reserve-assert).
# Sandbox: synthetic ledger (scanmax=10 -> slot=11) + stub counter_head whose
# canonical head 11 occupies the planned slot. Second fire: missing body-file rc4.
_ml = os.path.join(REPO, "scripts", "mesh_leg.py")
_ml_scr = tempfile.mkdtemp(prefix="organs_ml_")
_ml_body = os.path.join(_ml_scr, "body.md")
open(_ml_body, "w", encoding="utf-8").write("synthetic lane body for the collision fire\n")
_ml_files = {"ledgers/CORPUS.md": "| C5-10 | t | mint | Counter 10->11 |\n",
             "scripts/counter_head.py": 'print("live head (last row canonical pair): 11")\n'}
_c1, _o1, _t1, _k1, _h1 = run_rig(_ml, lambda p, req: {}, files=_ml_files,
    argv=["--leg", "1", "--verb", "mint", "--body-file", _ml_body])
_c2, _o2, _t2, _k2, _h2 = run_rig(_ml, lambda p, req: {}, files=_ml_files,
    argv=["--leg", "1", "--verb", "mint"])
ok = (_c1 == 4 and "REFUSE" in _o1 and "collision" in _o1 and "slot=11" in _o1
      and _c2 == 4 and "REFUSE" in _o2 and not _k1 and not _k2)
record("mesh-leg-mint-red", ok,
       f"collision rc{_c1} named={'collision' in _o1} nobody rc{_c2} doors={len(_k1) + len(_k2)}")

# inbox_leg: door verb on a mocked EMPTY door -> zero-row clean exit rc0 (SERVED 0,
# OFFER null), keyed read rides the harness dummy secret. Second fire: secrets dir
# without the secret file -> named REFUSE rc2, never a silent zero or a crash.
_il = os.path.join(REPO, "scripts", "inbox_leg.py")
def _il_router(p, req):
    if p.startswith("/api/me"):
        return {"me": {"since_last_visit": {}, "ack_cursor": None}}
    return {}
_c3, _o3, _t3, _k3, _h3 = run_rig(_il, _il_router, argv=["--leg", "1", "--verb", "door"])
_il_empty_sec = os.path.join(_ml_scr, "empty_sec"); os.makedirs(_il_empty_sec, exist_ok=True)
_c4, _o4, _t4, _k4, _h4 = run_rig(_il, _il_router, argv=["--leg", "1", "--verb", "door"],
    env={"ORGANS_SECRETS": _il_empty_sec})
ok = (_c3 == 0 and "SERVED 0 newly-unbanked 0" in _o3 and "OFFER null" in _o3
      and any("/api/me" in p for p in _k3) and _c4 == 2 and "REFUSE" in _o4)
record("inbox-leg-door-empty", ok,
       f"empty rc{_c3} served0={'SERVED 0' in _o3} nosecret rc{_c4} doors={len(_k3)}")

# fire_genre: --dry on synthetic GENRE rows -> plan rc0 with COMPUTED counts and
# every row extracted; a byte-drift row must REFUSE rc2 before any door touch.
_fg = os.path.join(REPO, "scripts", "fire_genre.py")
_fg_scr = tempfile.mkdtemp(prefix="organs_fg_")
_fg_rows = [{"n": 1, "body": "synthetic genre one"},
            {"n": 2, "body": "synthetic genre two"},
            {"n": 3, "body": "synthetic genre three"}]
for _r in _fg_rows: _r["bytes"] = len(_r["body"].encode("utf-8"))
_fg_good = os.path.join(_fg_scr, "rows.jsonl")
open(_fg_good, "w", encoding="utf-8").write("\n".join(json.dumps(_r) for _r in _fg_rows) + "\n")
_c5, _o5, _t5, _k5, _h5 = run_rig(_fg, lambda p, req: {}, argv=["--rows", _fg_good, "--dry"])
_fg_drift = [dict(_fg_rows[0]), dict(_fg_rows[1], bytes=_fg_rows[1]["bytes"] + 1)]
_fg_bad = os.path.join(_fg_scr, "rows-drift.jsonl")
open(_fg_bad, "w", encoding="utf-8").write("\n".join(json.dumps(_r) for _r in _fg_drift) + "\n")
_c6, _o6, _t6, _k6, _h6 = run_rig(_fg, lambda p, req: {}, argv=["--rows", _fg_bad, "--dry"])
ok = (_c5 == 0 and f"PLAN genres={len(_fg_rows)} byte-assert-deaths=0" in _o5
      and "FIRE-GENRE-DONE (dry)" in _o5
      and all(f"GENRE {_r['n']}" in _o5 for _r in _fg_rows)
      and _c6 == 2 and "REFUSE: byte drift" in _o6 and not _k5 and not _k6)
record("fire-genre-dry-plan", ok,
       f"dry rc{_c5} genres={len(_fg_rows)} drift rc{_c6} doors={len(_k5) + len(_k6)}")

# run_rig: registry dispatcher -- known rig plans rc0 (no door touch), unknown rig
# REFUSE rc5, absent registry NO-REGISTRY rc4. Registry is SHOP config: the leg
# ships a synthetic one into scratch HOME only.
_rr = os.path.join(REPO, "scripts", "run_rig.py")
_rr_reg = {"w": {"door": "say", "args": {"place_id": 1367, "mode": "line", "body": "N"}}}
_rr_env = {"ORGANS_RIGS": ""}
_c7, _o7, _t7, _k7, _h7 = run_rig(_rr, lambda p, req: {}, files={"scripts/rigs.json": _rr_reg},
    argv=["--rig", "w", "--n", "7"], env=_rr_env)
_c8, _o8, _t8, _k8, _h8 = run_rig(_rr, lambda p, req: {}, files={"scripts/rigs.json": _rr_reg},
    argv=["--rig", "no-such-rig"], env=_rr_env)
_c9, _o9, _t9, _k9, _h9 = run_rig(_rr, lambda p, req: {}, argv=["--rig", "w"], env=_rr_env)
ok = (_c7 == 0 and "RUN-RIG-DONE (plan)" in _o7 and _c8 == 5 and "REFUSE" in _o8
      and _c9 == 4 and "NO-REGISTRY" in _o9 and not (_k7 or _k8 or _k9))
record("run-rig-registry-red", ok, f"plan rc{_c7} unknown rc{_c8} noreg rc{_c9}")

# ---------- mirror-audit-gates (Tier-2 mirror_audit organ: the 317-copy _mirror_audit_batch*
# one-off family distilled; GP719/GP739/GP740 gates IN CODE). Fires at the door through
# run_rig: synthetic canon trio (**Bar:** piece / NO BAR header piece / plain piece), mocked
# seat answers valid two-line verdicts plus a garbage one-liner for the designated piece ->
# GP739 reroll fired BOTH ways (recover: rerolls 1..2 + parsed; cap-out: rerolls=2 +
# unparsed_final). Bookkeeping asserted per row: gate in {BAR, ACT-ONLY, PLAIN}, rerolls<=2,
# parsed shape {verdict, reason, bar}. --dry rc0 with COMPUTED counts and ZERO seat calls;
# no-files REFUSE rc2 (bare rc from SystemExit, never piped). Every seat ask must carry the
# 131072 max_tokens floor. Loud-named: any leg defect records a NAMED FAIL, never a crash.
def _mirror_audit_leg():
    _saved_seat = os.environ.get("ORGANS_SEAT_URL")
    try:
        _ma = os.path.join(REPO, "scripts", "mirror_audit.py")
        _ma_files = {
            "canon/eros/bar-piece.md": "# bar piece\n\n" + "**Bar:** test-bar\n\nsynthetic body prose for the bar fire\n",
            "canon/eros/act-piece.md": "# act piece\nNO BAR -- record-only header\n\nsynthetic act body prose\n",
            "canon/eros/plain-piece.md": "# plain piece\n\nsynthetic plain body prose\n",
        }
        _ma_env = {"ORGANS_SEAT_URL": "http://127.0.0.1:9/v1/chat/completions"}
        _ma_argv = ["--files", "canon/eros/bar-piece.md,canon/eros/act-piece.md,canon/eros/plain-piece.md"]
        _ma_valid = {
            "bar-piece.md": "ADMIT BAR_MET\nThe piece clears its declared bar and lands the act on the reader.",
            "act-piece.md": "ADMIT BAR_NOT_MET\nThe record-only act lands as an act; no bar is claimed here.",
            "plain-piece.md": "ADMIT\nThe piece lands its act on the reader with a concrete turn.",
        }
        _ma_garbage = "canon/eros/plain-piece.md"

        def _ma_router(recover):
            _seen, _maxtoks = {}, []
            def _r(p, req):
                _b = json.loads(req.data.decode("utf-8"))
                _maxtoks.append(_b.get("max_tokens"))
                _rel = _b["messages"][0]["content"].split("FILE: ", 1)[1].split("\n", 1)[0]
                _n = _seen.get(_rel, 0); _seen[_rel] = _n + 1
                if _rel == _ma_garbage and (_n == 0 or not recover):
                    _text = "HOLD"  # GP739 red shape: verdict token, no reason sentence
                else:
                    _text = _ma_valid[_rel.rsplit("/", 1)[-1]]
                return {"choices": [{"message": {"content": _text}}]}
            return _r, _maxtoks

        def _ma_rows(tree):
            _cf = [k for k in tree if k.startswith("scripts/census/mirror-audit-")]
            assert len(_cf) == 1, f"census files={_cf}"
            return json.loads(tree[_cf[0]])

        def _ma_shape(row, gate):
            return (row.get("gate") == gate and isinstance(row.get("rerolls"), int)
                    and row["rerolls"] <= 2 and "unparsed_final" in row
                    and (row["parsed"] is None or set(row["parsed"]) == {"verdict", "reason", "bar"}))

        # fire 1: GP739 reroll RECOVERS (garbage once for the plain piece, then a valid verdict)
        _r1, _mt1 = _ma_router(recover=True)
        _c1, _o1, _t1, _k1, _h1 = run_rig(_ma, _r1, files=_ma_files, argv=_ma_argv, env=_ma_env)
        _rows1 = _ma_rows(_t1)
        _p1 = _rows1["canon/eros/plain-piece.md"]
        ok1 = (_c1 == 0 and len(_rows1) == 3 and "STORE:" in _o1 and "unparsed= 0" in _o1
               and _ma_shape(_rows1["canon/eros/bar-piece.md"], "BAR")
               and _ma_shape(_rows1["canon/eros/act-piece.md"], "ACT-ONLY")
               and _ma_shape(_p1, "PLAIN")
               and 1 <= _p1["rerolls"] <= 2 and _p1["parsed"] is not None
               and _p1["parsed"]["verdict"] == "ADMIT" and _p1["unparsed_final"] is False
               and _rows1["canon/eros/bar-piece.md"]["parsed"]["bar"] == "BAR_MET"
               and len(_k1) == 4 and _mt1 and all(t >= 131072 for t in _mt1))
        # fire 2: GP739 cap EXHAUSTS (garbage forever -> rerolls=2, parsed None, unparsed_final)
        _r2, _mt2 = _ma_router(recover=False)
        _c2, _o2, _t2, _k2, _h2 = run_rig(_ma, _r2, files=_ma_files, argv=_ma_argv, env=_ma_env)
        _rows2 = _ma_rows(_t2)
        _p2 = _rows2["canon/eros/plain-piece.md"]
        ok2 = (_c2 == 0 and "unparsed= 1" in _o2 and _ma_shape(_p2, "PLAIN")
               and _p2["rerolls"] == 2 and _p2["parsed"] is None and _p2["unparsed_final"] is True
               and _rows2["canon/eros/bar-piece.md"]["parsed"] is not None
               and len(_k2) == 5 and _mt2 and all(t >= 131072 for t in _mt2))
        # fire 3: --dry plan rc0, COMPUTED counts, ZERO seat calls, no census write
        _c3, _o3, _t3, _k3, _h3 = run_rig(_ma, lambda p, req: {}, files=_ma_files,
                                          argv=["--glob", "canon/eros/*.md", "--dry"], env=_ma_env)
        ok3 = (_c3 == 0 and "DRY-PLAN rows= 3 bars= 1 act-only= 1" in _o3 and not _k3
               and not any(k.startswith("scripts/census/") for k in _t3))
        # fire 4: no files selected -> bare REFUSE rc2, zero seat calls
        _c4, _o4, _t4, _k4, _h4 = run_rig(_ma, lambda p, req: {}, files=_ma_files, argv=[], env=_ma_env)
        ok4 = (_c4 == 2 and "REFUSE: no files" in _o4 and not _k4)
        record("mirror-audit-gates", ok1 and ok2 and ok3 and ok4,
               f"reroll rc{_c1} r={_p1.get('rerolls')} capout rc{_c2} r={_p2.get('rerolls')} "
               f"dry rc{_c3} doors={len(_k3)} refuse rc{_c4} floor={all(t >= 131072 for t in _mt1 + _mt2)}")
    except Exception as e:
        record("mirror-audit-gates", False, f"LEG-EXC {type(e).__name__}: {e}")
    finally:
        if _saved_seat is None: os.environ.pop("ORGANS_SEAT_URL", None)
        else: os.environ["ORGANS_SEAT_URL"] = _saved_seat
_mirror_audit_leg()

# ---------- vw-unified-gates (Tier-1 vw_unified organ: the 53-copy venue-watch one-off
# family distilled; walk/ship/goto with byte+char+NO-LID+roundtrip gates IN CODE).
# Fires at the door through run_rig: dry gate-fail rc3 (named per-row failures), dry
# clean rc0 ZERO door calls, live-shape without --fire REFUSE rc4, verbless rc2,
# mocked 3-id walk with the middle id serving HTTP 404 (rows=2, 404 printed, rc0 --
# walk handles 404 ranges by design: 1f3d9 line ids vs 1f916 comment ids namespaces),
# missing secret file REFUSE rc2 (int exit, not SystemExit-str's silent 1). runlib is
# mocked at the IMPORT BOUNDARY: absent -> ship --fire must die NAMED (standing()
# needs runlib) rc5, never a traceback; stubbed -> full live ship proves enc8 POST at
# place, standing==place (no move), NO-LID guard (never GET /api/line/None) and dec8
# readback roundtrip banked in receipts. Loud-named: leg defects record a NAMED FAIL.
def _vw_unified_leg():
    _saved_sec = os.environ.get("ORGANS_SECRETS")
    _had_runlib = "runlib" in sys.modules
    _saved_runlib = sys.modules.get("runlib")
    try:
        _vw = os.path.join(REPO, "scripts", "vw_unified.py")
        _vw_scr = tempfile.mkdtemp(prefix="organs_vw_")
        _vw_sec = os.path.join(_vw_scr, "sec"); os.makedirs(_vw_sec)
        json.dump({"resident_key": "test-venue-key"}, open(os.path.join(_vw_sec, "1f3d9.json"), "w"))
        _vw_env = {"ORGANS_SECRETS": _vw_sec}
        _vw_empty_sec = os.path.join(_vw_scr, "empty_sec"); os.makedirs(_vw_empty_sec)

        def _vw_plan(rows, name):
            _p = os.path.join(_vw_scr, name)
            json.dump(rows, open(_p, "w", encoding="utf-8"))
            return _p

        def _vw_enc8(s): return " ".join(format(ord(c), "08b") for c in s)

        # fire a: dry plan -- over-limit + non-ASCII + no-place rows -> rc3, named gates, zero doors
        _vw_bad = _vw_plan([{"place": 7, "text": "x" * 30},
                            {"place": 7, "text": "caf" + chr(233)},
                            {"text": "ok"}], "plan-bad.json")
        _ca, _oa, _ta, _ka, _ha = run_rig(_vw, lambda p, req: {}, argv=["ship", "--plan", _vw_bad, "--dry"], env=_vw_env)
        ok_a = (_ca == 3 and "chars 30>26" in _oa and "bytes 269>240" in _oa
                and "non-ASCII" in _oa and "no place" in _oa and not _ka)

        # fire b: dry plan all-clean -> rc0, zero door calls, no census write
        _vw_good = _vw_plan([{"place": 7, "text": "hello venue"}], "plan-good.json")
        _cb, _ob, _tb, _kb, _hb = run_rig(_vw, lambda p, req: {}, argv=["ship", "--plan", _vw_good, "--dry"], env=_vw_env)
        ok_b = (_cb == 0 and "gate-failures= 0" in _ob and not _kb
                and not any("census" in k for k in _tb))

        # fire c: live-shape plan WITHOUT --fire -> REFUSE rc4, zero doors
        _cc, _oc, _tc, _kc, _hc = run_rig(_vw, lambda p, req: {}, argv=["ship", "--plan", _vw_good], env=_vw_env)
        ok_c = (_cc == 4 and "REFUSE" in _oc and "--fire" in _oc and not _kc)

        # fire d: verbless -> REFUSE rc2
        _cd, _od, _td, _kd, _hd = run_rig(_vw, lambda p, req: {}, argv=[], env=_vw_env)
        ok_d = (_cd == 2 and "REFUSE" in _od and not _kd)

        # fire e: mocked walk 11-13, middle id serves HTTP 404 -> rows=2, 404 printed, rc0
        _vw_auths = []
        def _vw_walk_router(p, req):
            _vw_auths.append(req.get_header("Authorization"))
            _lid = int(p.rsplit("/", 1)[1])
            if _lid == 12:
                raise urllib.error.HTTPError(req.full_url, 404, "Not Found", None, None)
            _txt = {11: "row eleven", 13: "row thirteen"}[_lid]
            return {"line": {"id": _lid, "place_id": _lid * 10, "author_name": "synthetic-author",
                             "created_at": "2026-11-14T00:00:00Z", "body": _vw_enc8(_txt)}}
        _ce, _oe, _te, _ke, _he = run_rig(_vw, _vw_walk_router, argv=["walk", "--range", "11-13"], env=_vw_env)
        _vw_census = json.loads(_te.get("scripts/census/vw-13-walk.json", "null"))
        ok_e = (_ce == 0 and "WALK rows= 2" in _oe and "12 HTTP 404" in _oe
                and _ke == ["/api/line/11", "/api/line/12", "/api/line/13"]
                and isinstance(_vw_census, list) and len(_vw_census) == 2
                and [r["id"] for r in _vw_census] == [11, 13]
                and [r["decoded"] for r in _vw_census] == ["row eleven", "row thirteen"]
                and all(r["place"] and r["author"] for r in _vw_census)
                and _vw_auths == ["Bearer test-venue-key"] * 3)

        # fire f: missing secret file -> named REFUSE rc2 (int exit), zero doors
        _cf, _of, _tf, _kf, _hf = run_rig(_vw, lambda p, req: {}, argv=["walk", "--range", "11-13"],
                                          env={"ORGANS_SECRETS": _vw_empty_sec})
        ok_f = (_cf == 2 and "REFUSE" in _of and "secret file not present" in _of and not _kf)

        # fire g: runlib ABSENT at the import boundary -> ship --fire dies NAMED rc5, no traceback
        sys.modules["runlib"] = None
        _cg, _og, _tg, _kg, _hg = run_rig(_vw, lambda p, req: {}, argv=["ship", "--plan", _vw_good, "--fire"], env=_vw_env)
        ok_g = (_cg == 5 and "standing() needs runlib" in _og and "REFUSE" in _og
                and "HARNESS-EXC" not in _og and "Traceback" not in _og and not _kg)

        # fire h: runlib STUBBED -> full live ship: enc8 POST at place, standing==place (no move),
        # NO-LID row never reads /api/line/None, dec8 readback roundtrip banked in receipts
        import types as _vw_types
        _vw_stub = _vw_types.ModuleType("runlib")
        _vw_said, _vw_moves = [], []
        _vw_stub.standing = lambda: 7
        def _vw_rid_line(place_id, body):
            _vw_said.append((place_id, body))
            return {"line": {"id": 900}} if len(_vw_said) == 1 else {}
        _vw_stub.rid_line = _vw_rid_line
        _vw_stub.venue = lambda tool, args: _vw_moves.append((tool, args)) or {}
        sys.modules["runlib"] = _vw_stub
        def _vw_ship_router(p, req):
            if p == "/api/line/900":
                return {"line": {"id": 900, "place_id": 7, "author_name": "synthetic-author",
                                 "body": _vw_enc8("hello venue")}}
            return {}
        _vw_live = _vw_plan([{"place": 7, "text": "hello venue"}, {"place": 7, "text": "no lid row"}], "plan-live.json")
        _ch, _oh, _th, _kh, _hh = run_rig(_vw, _vw_ship_router, argv=["ship", "--plan", _vw_live, "--fire"], env=_vw_env)
        _vw_receipts = json.loads(_th.get("scripts/census/vw-unified-receipts.json", "null"))
        ok_h = (_ch == 0 and "roundtrip True" in _oh and "NO LID" in _oh
                and _vw_said == [(7, _vw_enc8("hello venue")), (7, _vw_enc8("no lid row"))]
                and not _vw_moves and "/api/line/None" not in _kh and _kh == ["/api/line/900"]
                and _vw_receipts == {"900": {"place": 7, "author": "synthetic-author", "roundtrip": True}})

        record("vw-unified-gates", ok_a and ok_b and ok_c and ok_d and ok_e and ok_f and ok_g and ok_h,
               f"drybad rc{_ca} dryclean rc{_cb} doors={len(_kb)} nofire rc{_cc} verbless rc{_cd} "
               f"walk404 rc{_ce} rows={len(_vw_census) if isinstance(_vw_census, list) else 'X'} "
               f"nosecret rc{_cf} norunlib rc{_cg} named={'standing() needs runlib' in _og} live rc{_ch}")
    except Exception as e:
        record("vw-unified-gates", False, f"LEG-EXC {type(e).__name__}: {e}")
    finally:
        if _had_runlib: sys.modules["runlib"] = _saved_runlib
        else: sys.modules.pop("runlib", None)
        if _saved_sec is None: os.environ.pop("ORGANS_SECRETS", None)
        else: os.environ["ORGANS_SECRETS"] = _saved_sec
_vw_unified_leg()

# ---------- seat-score-gates (Tier-2 seat_score organ: the 78-copy scoring family
# (_pile_score* 54 + _score_batch* 24) distilled; parse3 PENDING gate, keep-first O_EXCL,
# maxtok floor 131072, door-path + non-JSON cures IN CODE). Fires through run_rig on a
# SCRATCH COPY with local.json BESIDE it (config-chain locality datum: the host's
# ~/organs.json must never leak into the sandbox; the pins live beside the rig). Six fires:
# (a) --dry two synthetic pieces -> rc0 COMPUTED byte counts, ZERO door calls;
# (b) verbless -> REFUSE rc2; (c) mocked seat valid 3-cond answer -> triple COMPLETE +
# store row (triple shape asserted), bare-base door-path appended, maxtok floor on every
# ask; (d) TWO-cond answer -> PENDING, complete False, raw stored; (e) keep-first: frozen
# window stamp + pre-existing store path + mocked success -> O_EXCL collision named
# FileExistsError, first copy bytes INTACT, no harness crash; (f) NON-JSON body -> named
# NON-JSON head in the result, rc0, no traceback. Loud-named: leg defects record a NAMED FAIL.
def _seat_score_leg():
    _saved_seat = os.environ.get("ORGANS_SEAT_URL")
    _saved_strftime = time.strftime
    try:
        _ss_src = os.path.join(REPO, "scripts", "seat_score.py")
        _ss_scr = tempfile.mkdtemp(prefix="organs_ss_")
        _ss_kit = os.path.join(_ss_scr, "kit"); os.makedirs(_ss_kit)
        _ss = os.path.join(_ss_kit, "seat_score.py")
        shutil.copy(_ss_src, _ss)
        # config pins BESIDE the rig (datum 1): bare-base seat_url -> the door-path cure appends
        json.dump({"seat_url": "http://127.0.0.1:9", "seat_model": "local-seat"},
                  open(os.path.join(_ss_kit, "local.json"), "w", encoding="utf-8"))
        _ss_p1 = os.path.join(_ss_scr, "piece-one.md")
        _ss_p2 = os.path.join(_ss_scr, "piece-two.md")
        _ss_b1 = "synthetic concrete scene one\n"
        _ss_b2 = "caf" + chr(233) + " synthetic scene two\n"  # non-ASCII: byte census != char count
        open(_ss_p1, "w", encoding="utf-8").write(_ss_b1)
        open(_ss_p2, "w", encoding="utf-8").write(_ss_b2)
        _ss_n1, _ss_n2 = len(_ss_b1.encode("utf-8")), len(_ss_b2.encode("utf-8"))
        _ss_pieces = "one=" + _ss_p1 + ",two=" + _ss_p2
        _ss_env = {"ORGANS_SEAT_URL": "http://127.0.0.1:9"}
        _ss_maxtoks = []
        def _ss_router(text):
            def _r(p, req):
                _ss_maxtoks.append(json.loads(req.data.decode("utf-8")).get("max_tokens"))
                return {"choices": [{"message": {"content": text}}]}
            return _r
        def _ss_rows(tree, prefix):
            _cf = [k for k in tree if k.startswith(prefix)]
            assert len(_cf) == 1, f"store rows {prefix}: {_cf}"
            return json.loads(tree[_cf[0]])

        # fire a: --dry -> rc0, COMPUTED byte counts, zero door calls, no census write
        _ca, _oa, _ta, _ka, _ha = run_rig(_ss, lambda p, req: {},
                                          argv=["score", "--pieces", _ss_pieces, "--dry"], env=_ss_env)
        ok_a = (_ca == 0 and f"one DRY bytes= {_ss_n1}" in _oa and f"two DRY bytes= {_ss_n2}" in _oa
                and "DRY-PLAN pieces= 2 seats= 1" in _oa and not _ka
                and not any(k.startswith("scripts/census/") for k in _ta))

        # fire b: verbless -> REFUSE rc2, zero doors
        _cb, _ob, _tb, _kb, _hb = run_rig(_ss, lambda p, req: {}, argv=[], env=_ss_env)
        ok_b = (_cb == 2 and "REFUSE: verb score required" in _ob and not _kb)

        # fire c: valid 3-cond answer -> COMPLETE triples + store rows + door-path + floor
        _ss_ans3 = "cond1=1\ncond2=0\ncond3=1"
        _cc, _oc, _tc, _kc, _hc = run_rig(_ss, _ss_router(_ss_ans3),
                                          argv=["score", "--pieces", _ss_pieces], env=_ss_env)
        _ss_r1 = _ss_rows(_tc, "scripts/census/score-one-local-")
        _ss_r2 = _ss_rows(_tc, "scripts/census/score-two-local-")
        _ss_run = json.loads(_tc.get("scripts/census/seat-score-run.json", "null"))
        ok_c = (_cc == 0 and "COMPLETE" in _oc and "pending= 0" in _oc
                and _ss_r1["triple"] == [1, 0, 1] and _ss_r1["complete"] is True
                and _ss_r1["raw"] == _ss_ans3 and _ss_r1["measured_bytes"] == _ss_n1
                and _ss_r1["piece"] == "one" and _ss_r1["seat"] == "local"
                and _ss_r2["triple"] == [1, 0, 1] and _ss_r2["measured_bytes"] == _ss_n2
                and _ss_run == {"one": {"local": {"triple": [1, 0, 1], "complete": True}},
                                "two": {"local": {"triple": [1, 0, 1], "complete": True}}}
                and _kc == ["/v1/chat/completions", "/v1/chat/completions"]
                and len(_ss_maxtoks) == 2 and all(t >= 131072 for t in _ss_maxtoks))

        # fire d: TWO-cond answer -> PENDING, complete False, raw stored (firing #75)
        _ss_ans2 = "cond1=1\ncond2=0"
        _cd, _od, _td, _kd, _hd = run_rig(_ss, _ss_router(_ss_ans2),
                                          argv=["score", "--pieces", _ss_pieces], env=_ss_env)
        _ss_d1 = _ss_rows(_td, "scripts/census/score-one-local-")
        ok_d = (_cd == 0 and "PENDING" in _od and "pending= 2" in _od
                and _ss_d1["triple"] is None and _ss_d1["complete"] is False
                and _ss_d1["raw"] == _ss_ans2
                and _kd == ["/v1/chat/completions"] * 2)

        # fire e: keep-first -- freeze the window stamp, pre-seed the store path, mocked success:
        # O_EXCL collision must surface NAMED, first copy bytes intact, harness never crashes
        _ss_tag = "20261114T000000"
        time.strftime = lambda fmt, *a: _ss_tag
        _ss_first = '{"first": "copy sentinel"}\n'
        _ss_seed = "scripts/census/score-one-local-" + _ss_tag + ".json"
        _ce, _oe, _te, _ke, _he = run_rig(_ss, _ss_router(_ss_ans3), files={_ss_seed: _ss_first},
                                          argv=["score", "--pieces", _ss_pieces], env=_ss_env)
        _ss_erun = json.loads(_te.get("scripts/census/seat-score-run.json", "null"))
        ok_e = (_ce == 0 and "ERR FileExistsError" in _oe
                and "FileExistsError" in _ss_erun["one"]["local"].get("error", "")
                and _te.get(_ss_seed) == _ss_first  # first copy INTACT, never overwritten
                and _ss_erun["two"]["local"]["complete"] is True
                and "HARNESS-EXC" not in _oe and "Traceback" not in _oe)

        # fire f: NON-JSON body -> named NON-JSON head in the result, rc0 run, no traceback
        def _ss_nonjson(p, req):
            _ss_maxtoks.append(json.loads(req.data.decode("utf-8")).get("max_tokens"))
            return b"<html>rate wall -- not json</html>"
        _cf, _of, _tf, _kf, _hf = run_rig(_ss, _ss_nonjson,
                                          argv=["score", "--pieces", _ss_pieces], env=_ss_env)
        _ss_frun = json.loads(_tf.get("scripts/census/seat-score-run.json", "null"))
        ok_f = (_cf == 0 and "NON-JSON body head=" in _of and "missing/errors= 2" in _of
                and "NON-JSON body head=" in _ss_frun["one"]["local"].get("error", "")
                and "KeyError" not in _of and "Traceback" not in _of and "HARNESS-EXC" not in _of
                and _kf == ["/v1/chat/completions"] * 2)

        _floor_ok = len(_ss_maxtoks) == 8 and all(t >= 131072 for t in _ss_maxtoks)
        record("seat-score-gates", ok_a and ok_b and ok_c and ok_d and ok_e and ok_f and _floor_ok,
               f"dry rc{_ca} doors={len(_ka)} verbless rc{_cb} complete rc{_cc} pending rc{_cd} "
               f"keepfirst rc{_ce} intact={_te.get(_ss_seed) == _ss_first} nonjson rc{_cf} floor={_floor_ok}")
    except Exception as e:
        record("seat-score-gates", False, f"LEG-EXC {type(e).__name__}: {e}")
    finally:
        time.strftime = _saved_strftime
        if _saved_seat is None: os.environ.pop("ORGANS_SEAT_URL", None)
        else: os.environ["ORGANS_SEAT_URL"] = _saved_seat
_seat_score_leg()

# ---------- bar-audit-gates (Tier-1 bar_audit organ: the 107-copy _hot*_hip cold-seat
# audit family distilled; parse-verdict containment gate, keep-first O_EXCL, maxtok floor
# 131072, door-path + non-JSON cures IN CODE). Fires through run_rig on a SCRATCH COPY
# with local.json BESIDE it (config-chain locality datum: the host's ~/organs.json must
# never leak into the sandbox; the pins live beside the rig). Fixtures live in
# tests/fixtures/ -- a missing fixture records a NAMED FAIL, never a harness crash.
# Fires: (a) --dry two fixture pieces (+ --bar override dry) -> rc0 COMPUTED byte counts,
# ZERO door calls, no store; (b) arg-shape refusals rc2 before any door: verbless,
# missing --pieces, bad entry, empty name/PATH, valueless --pieces/--bar/--out;
# (c) parse-verdict gate: ADMIT BAR_MET tallied, ADMIT-WITH-NOTE wins over ADMIT
# containment, BAR_NOT_MET wins over BAR_MET, bare-base door-path appended, floor on
# every ask; (c2) tokenless answer -> UNPARSED named, never tallied, raw stored;
# (c3) BOTH bar tokens + ADMIT-WITH-NOTE on one line -> longer tokens win, --bar
# override rides the system prompt; (d) keep-first: second fire at the SAME store path
# -> named KEEP-FIRST collision rc0, first copy bytes INTACT, no crash; (e) NON-JSON
# body -> named head in the result, rc0, no traceback; (f) empty-choices JSON shell ->
# named DOOR-SHELL (IndexError cure), rc0. Loud-named: leg defects record a NAMED FAIL.
def _bar_audit_leg():
    _saved_seat = os.environ.get("ORGANS_SEAT_URL")
    _saved_model = os.environ.get("ORGANS_SEAT_MODEL")
    try:
        _ba_src = os.path.join(REPO, "scripts", "bar_audit.py")
        _ba_f1 = os.path.join(HERE, "fixtures", "bar_piece_one.md")
        _ba_f2 = os.path.join(HERE, "fixtures", "bar_piece_two.md")
        _ba_fb = os.path.join(HERE, "fixtures", "bar_override.txt")
        for _p in (_ba_src, _ba_f1, _ba_f2, _ba_fb):
            if not os.path.exists(_p):
                record("bar-audit-gates", False, "fixture absent: " + os.path.basename(_p))
                return
        _ba_scr = tempfile.mkdtemp(prefix="organs_ba_")
        _ba_kit = os.path.join(_ba_scr, "kit"); os.makedirs(_ba_kit)
        _ba = os.path.join(_ba_kit, "bar_audit.py")
        shutil.copy(_ba_src, _ba)
        # config pins BESIDE the rig: bare-base seat_url -> the door-path cure appends
        json.dump({"seat_url": "http://127.0.0.1:9", "seat_model": "local-seat"},
                  open(os.path.join(_ba_kit, "local.json"), "w", encoding="utf-8"))
        _ba_n1 = len(open(_ba_f1, "rb").read())
        _ba_n2 = len(open(_ba_f2, "rb").read())  # non-ASCII fixture: byte census != char count
        _ba_pieces = "one=" + _ba_f1 + ",two=" + _ba_f2
        _ba_env = {"ORGANS_SEAT_URL": "http://127.0.0.1:9", "ORGANS_SEAT_MODEL": "local-seat"}
        _ba_maxtoks = []
        def _ba_router(text):
            def _r(p, req):
                _ba_maxtoks.append(json.loads(req.data.decode("utf-8")).get("max_tokens"))
                return {"choices": [{"message": {"content": text}}]}
            return _r
        def _ba_store(tree):
            _cf = [k for k in tree if k.startswith("scripts/census/bar-audit-")]
            assert len(_cf) == 1, f"store rows: {_cf}"
            return json.loads(tree[_cf[0]])

        # fire a: --dry -> rc0, COMPUTED byte counts, zero door calls, no census write
        _ca, _oa, _ta, _ka, _ha = run_rig(_ba, lambda p, req: {},
                                          argv=["audit", "--pieces", _ba_pieces, "--dry"], env=_ba_env)
        _ca2, _oa2, _ta2, _ka2, _ha2 = run_rig(_ba, lambda p, req: {},
                                               argv=["audit", "--pieces", _ba_pieces, "--bar", _ba_fb, "--dry"], env=_ba_env)
        ok_a = (_ca == 0 and f"[dry] audit one bytes={_ba_n1}" in _oa
                and f"[dry] audit two bytes={_ba_n2}" in _oa and "ZERO door calls" in _oa
                and not _ka and not any(k.startswith("scripts/census/") for k in _ta)
                and _ca2 == 0 and "bar-override=True" in _oa2 and not _ka2)

        # fire b: arg-shape refusals -> rc2 BEFORE any door, each named
        _ba_refusals = [
            ([], "REFUSE: verb audit required"),
            (["audit"], "REFUSE: audit needs --pieces"),
            (["audit", "--pieces", "noequals"], "REFUSE: --pieces entry not name=PATH"),
            (["audit", "--pieces", "=x"], "REFUSE: --pieces entry needs non-empty name"),
            (["audit", "--pieces", "x="], "REFUSE: --pieces entry needs non-empty name"),
            (["audit", "--pieces"], "REFUSE: --pieces without value"),
            (["audit", "--pieces", _ba_pieces, "--bar"], "REFUSE: --bar without value"),
            (["audit", "--pieces", _ba_pieces, "--out"], "REFUSE: --out without value"),
        ]
        ok_b = True
        for _argv, _want in _ba_refusals:
            _cb, _ob, _tb, _kb, _hb = run_rig(_ba, lambda p, req: {}, argv=_argv, env=_ba_env)
            ok_b = ok_b and _cb == 2 and _want in _ob and not _kb

        # fire c: parse-verdict gate -- mixed answers dispatched on the piece content
        _ba_ans_ok = "VERDICT = ADMIT, BAR_MET" + "\n" + "the piece meets its stated bar in one concrete move."
        _ba_ans_note = "VERDICT = ADMIT-WITH-NOTE, BAR_NOT_MET" + "\n" + "force present but the bar's action clause is missing."
        def _ba_router_mixed(p, req):
            _body = json.loads(req.data.decode("utf-8"))
            _ba_maxtoks.append(_body.get("max_tokens"))
            _piece = _body["messages"][-1]["content"]
            _txt = _ba_ans_ok if "Synthetic scene one" in _piece else _ba_ans_note
            return {"choices": [{"message": {"content": _txt}}]}
        _cc, _oc, _tc, _kc, _hc = run_rig(_ba, _ba_router_mixed,
                                          argv=["audit", "--pieces", _ba_pieces], env=_ba_env)
        _ba_cstore = _ba_store(_tc)
        ok_c = (_cc == 0 and "audit one -> ADMIT BAR_MET" in _oc
                and "audit two -> ADMIT-WITH-NOTE BAR_NOT_MET" in _oc
                and "SUMMARY pieces=2 parsed=2 unparsed=0 door-errors=0 admit=1 admit-with-note=1 hold=0 bar_met=1 bar_not_met=1" in _oc
                and _ba_cstore["results"]["one"]["verdict"] == "ADMIT"
                and _ba_cstore["results"]["one"]["bar"] == "BAR_MET"
                and _ba_cstore["results"]["one"]["raw"] == _ba_ans_ok
                and _ba_cstore["results"]["two"]["verdict"] == "ADMIT-WITH-NOTE"
                and _ba_cstore["results"]["two"]["bar"] == "BAR_NOT_MET"
                and _ba_cstore["seat"] == "http://127.0.0.1:9/v1/chat/completions"
                and _kc == ["/v1/chat/completions"] * 2)

        # fire c2: tokenless answer -> UNPARSED named, NEVER tallied, raw stored
        _ba_ans_unp = "the piece rambles and never names a verdict."
        _cc2, _oc2, _tc2, _kc2, _hc2 = run_rig(_ba, _ba_router(_ba_ans_unp),
                                               argv=["audit", "--pieces", _ba_pieces], env=_ba_env)
        _ba_c2store = _ba_store(_tc2)
        ok_c2 = (_cc2 == 0 and "UNPARSED UNPARSED" in _oc2
                 and "SUMMARY pieces=2 parsed=0 unparsed=2 door-errors=0 admit=0 admit-with-note=0 hold=0 bar_met=0 bar_not_met=0" in _oc2
                 and _ba_c2store["results"]["one"]["raw"] == _ba_ans_unp
                 and _ba_c2store["results"]["one"]["ok"] is True
                 and _kc2 == ["/v1/chat/completions"] * 2)

        # fire c3: BOTH bar tokens + ADMIT-WITH-NOTE on one line -> longer tokens win;
        # --bar override rides the system prompt (containment order law, both directions)
        _ba_bar_txt = open(_ba_fb, encoding="utf-8").read()
        _ba_override_seen = []
        def _ba_router_both(p, req):
            _body = json.loads(req.data.decode("utf-8"))
            _ba_maxtoks.append(_body.get("max_tokens"))
            _ba_override_seen.append("EXPLICIT BAR OVERRIDE: " + _ba_bar_txt.strip() in _body["messages"][0]["content"])
            return {"choices": [{"message": {"content": "VERDICT = ADMIT-WITH-NOTE, BAR_MET BAR_NOT_MET" + "\n" + "both tokens on one line: containment must pick the longer."}}]}
        _cc3, _oc3, _tc3, _kc3, _hc3 = run_rig(_ba, _ba_router_both,
                                               argv=["audit", "--pieces", "one=" + _ba_f1, "--bar", _ba_fb], env=_ba_env)
        _ba_c3store = _ba_store(_tc3)
        ok_c3 = (_cc3 == 0 and "audit one -> ADMIT-WITH-NOTE BAR_NOT_MET" in _oc3
                 and "SUMMARY pieces=1 parsed=1 unparsed=0 door-errors=0 admit=0 admit-with-note=1 hold=0 bar_met=0 bar_not_met=1" in _oc3
                 and _ba_c3store["results"]["one"]["bar"] == "BAR_NOT_MET"
                 and _ba_override_seen == [True] and _kc3 == ["/v1/chat/completions"])

        # fire d: keep-first -- fire live, then fire AGAIN at the SAME store path:
        # O_EXCL collision must surface NAMED rc0, first copy bytes intact, no crash
        _cd1, _od1, _td1, _kd1, _hd1 = run_rig(_ba, _ba_router(_ba_ans_ok),
                                               argv=["audit", "--pieces", _ba_pieces], env=_ba_env)
        _ba_storelines = [l for l in _od1.splitlines() if l.startswith("store (keep-first):")]
        assert len(_ba_storelines) == 1, f"store lines: {_ba_storelines}"
        _ba_path = _ba_storelines[0].split("store (keep-first):", 1)[1].strip()
        _ba_first = open(_ba_path, "rb").read()
        _cd2, _od2, _td2, _kd2, _hd2 = run_rig(_ba, _ba_router(_ba_ans_ok),
                                               argv=["audit", "--pieces", _ba_pieces, "--out", _ba_path], env=_ba_env)
        ok_d = (_cd1 == 0 and _cd2 == 0 and "KEEP-FIRST collision" in _od2
                and "first copy intact" in _od2
                and open(_ba_path, "rb").read() == _ba_first
                and "HARNESS-EXC" not in _od2 and "Traceback" not in _od2
                and _kd1 == ["/v1/chat/completions"] * 2 and _kd2 == ["/v1/chat/completions"] * 2)

        # fire e: NON-JSON body -> named head in the result, rc0 run, no traceback
        def _ba_nonjson(p, req):
            _ba_maxtoks.append(json.loads(req.data.decode("utf-8")).get("max_tokens"))
            return b"<html>rate wall -- not json</html>"
        _ce, _oe, _te, _ke, _he = run_rig(_ba, _ba_nonjson,
                                          argv=["audit", "--pieces", _ba_pieces], env=_ba_env)
        _ba_estore = _ba_store(_te)
        ok_e = (_ce == 0 and "NON-JSON head:" in _oe and "door-errors=2" in _oe
                and _ba_estore["results"]["one"]["ok"] is False
                and "NON-JSON head:" in _ba_estore["results"]["one"].get("err", "")
                and "KeyError" not in _oe and "Traceback" not in _oe and "HARNESS-EXC" not in _oe
                and _ke == ["/v1/chat/completions"] * 2)

        # fire f: empty-choices JSON shell -> named DOOR-SHELL (IndexError cure), rc0
        def _ba_shell(p, req):
            _ba_maxtoks.append(json.loads(req.data.decode("utf-8")).get("max_tokens"))
            return {"choices": []}
        _cf, _of, _tf, _kf, _hf = run_rig(_ba, _ba_shell,
                                          argv=["audit", "--pieces", "one=" + _ba_f1], env=_ba_env)
        _ba_fstore = _ba_store(_tf)
        ok_f = (_cf == 0 and "DOOR-SHELL" in _of
                and "DOOR-SHELL" in _ba_fstore["results"]["one"].get("err", "")
                and "IndexError" not in _of and "Traceback" not in _of and "HARNESS-EXC" not in _of
                and _kf == ["/v1/chat/completions"])

        _floor_ok = len(_ba_maxtoks) == 12 and all(t >= 131072 for t in _ba_maxtoks)
        record("bar-audit-gates", ok_a and ok_b and ok_c and ok_c2 and ok_c3 and ok_d and ok_e and ok_f and _floor_ok,
               f"dry rc{_ca} doors={len(_ka)} refusals={len(_ba_refusals)} ok_b={ok_b} parse rc{_cc} "
               f"unparsed rc{_cc2} bothtokens rc{_cc3} keepfirst rc{_cd2} intact={open(_ba_path, 'rb').read() == _ba_first} "
               f"nonjson rc{_ce} shell rc{_cf} floor={_floor_ok}")
    except Exception as e:
        record("bar-audit-gates", False, f"LEG-EXC {type(e).__name__}: {e}")
    finally:
        if _saved_seat is None: os.environ.pop("ORGANS_SEAT_URL", None)
        else: os.environ["ORGANS_SEAT_URL"] = _saved_seat
        if _saved_model is None: os.environ.pop("ORGANS_SEAT_MODEL", None)
        else: os.environ["ORGANS_SEAT_MODEL"] = _saved_model
_bar_audit_leg()

# ---------- tts-clip-gates (Tier-2 tts_clip organ: the 21-copy _clip* local-voice family
# distilled; CPU-only render, magic-byte player dispatch, silent-wav gate IN CODE).
# NO network, NO audio, NO real TTS binary render in-suite: render fires are --dry or a
# SIMULATED exe (subprocess.run mocked in-process; placeholder kit files satisfy the
# existence gates; the mock writes the scenario wav bytes and returns the scenario rc --
# fire class named mock-exe in the record note; the kit-absent refusal fires separately
# in (b) against a HOME without tts/). play fires ONLY --dry: zero player invocations,
# zero PowerShell, zero writes. Fixtures live in tests/fixtures/ -- a missing fixture
# records a NAMED FAIL, never a harness crash. Fires: (a) dry render -> rc0, chars
# counted in-call (non-ASCII fixture: chars != bytes), ZERO exe calls, no wav written;
# (b) refusals rc2 before any exe: verbless, missing --out, absent text file, empty text,
# kit exe absent, model absent, play missing/absent --file, unknown verb; (c) magic-byte
# dispatch via play --dry: RIFF/WAVE -> PCM route named, 0xFF 0xF3 / 0xFF 0xFB -> MP3
# route named, garbage -> PLAY-NAMED rc3, 44-byte silent wav -> SILENT-FAIL rc3, all
# with ZERO player calls and no .ps1 write; (d) silent-wav gate via the SIMULATED exe:
# 44-byte wav -> SILENT-FAIL rc3, 1068-byte wav -> rendered rc0 measured bytes, rc0 with
# no wav -> RENDER-NAMED rc3, exe rc1 -> RENDER-DEAD rc3; every simulated cmd asserts
# --backend cpu, NO --speed, NO --text-file passthrough, --text carries the file text.
# Loud-named: leg defects record a NAMED FAIL.
def _tts_clip_leg():
    _saved_run = subprocess.run
    _saved_exe = os.environ.get("ORGANS_TTS_EXE")
    _saved_model = os.environ.get("ORGANS_TTS_MODEL")
    try:
        _tc_src = os.path.join(REPO, "scripts", "tts_clip.py")
        _tc_fix = os.path.join(HERE, "fixtures")
        _tc_names = ("tts_clip_text.txt", "tts_clip_pcm.wav", "tts_clip_mp3_f3.wav",
                     "tts_clip_mp3_fb.wav", "tts_clip_garbage.bin", "tts_clip_silent.wav")
        for _p in [_tc_src] + [os.path.join(_tc_fix, n) for n in _tc_names]:
            if not os.path.exists(_p):
                record("tts-clip-gates", False, "fixture absent: " + os.path.basename(_p))
                return
        _tc_scr = tempfile.mkdtemp(prefix="organs_tc_")
        _tc_kitdir = os.path.join(_tc_scr, "kit"); os.makedirs(_tc_kitdir)
        _tc = os.path.join(_tc_kitdir, "tts_clip.py")
        shutil.copy(_tc_src, _tc)
        # config pin BESIDE the rig: tts_model pinned so the host's ~/organs.json never leaks
        json.dump({"tts_model": "kokoro-82m-q8_0.gguf"},
                  open(os.path.join(_tc_kitdir, "local.json"), "w", encoding="utf-8"))
        _tc_textpath = os.path.join(_tc_fix, "tts_clip_text.txt")
        _tc_text = open(_tc_textpath, encoding="utf-8").read().strip()
        _tc_chars = len(_tc_text)  # computed in-call; non-ASCII fixture: chars != bytes
        _tc_pcm = open(os.path.join(_tc_fix, "tts_clip_pcm.wav"), "rb").read()
        _tc_silent = open(os.path.join(_tc_fix, "tts_clip_silent.wav"), "rb").read()
        _tc_kitfiles = {"tts/audiocpp_cli.exe": "simulated kit exe (placeholder, never fired)",
                        "tts/kokoro-82m-q8_0.gguf": "simulated model (placeholder)"}
        _tc_exeonly = {"tts/audiocpp_cli.exe": "simulated kit exe (placeholder, never fired)"}
        _tc_empty = os.path.join(_tc_scr, "empty.txt")
        open(_tc_empty, "w", encoding="utf-8").write(chr(10) + " " + chr(10))
        # SIMULATED exe: subprocess.run mocked in-process -- zero real processes, zero audio.
        _tc_calls = []
        _tc_sim = {"wav": None, "rc": 0}
        def _tc_fake_run(cmd, *a, **kw):
            _tc_calls.append(list(cmd))
            if _tc_sim["wav"] is not None and "--out" in cmd:
                open(cmd[cmd.index("--out") + 1], "wb").write(_tc_sim["wav"])
            return subprocess.CompletedProcess(cmd, _tc_sim["rc"], stdout="", stderr="simulated kit")
        subprocess.run = _tc_fake_run
        def _tc_arg(cmd, flag):
            return cmd[cmd.index(flag) + 1] if flag in cmd and cmd.index(flag) + 1 < len(cmd) else None

        # fire a: --dry render -> rc0, COMPUTED char count, zero exe calls, no wav written
        _tc_out_a = os.path.join(_tc_scr, "clip-dry.wav")
        _ca, _oa, _ta, _ka, _ha = run_rig(_tc, lambda p, req: {}, files=_tc_kitfiles,
            argv=["render", "--text-file", _tc_textpath, "--out", _tc_out_a, "--dry"])
        ok_a = (_ca == 0 and "[dry] render chars=%d" % _tc_chars in _oa and "ZERO render calls" in _oa
                and not _tc_calls and not os.path.exists(_tc_out_a) and not _ka)

        # fire b: refusals -> rc2 BEFORE any exe, each named (kit-absent fire: HOME without tts/)
        _tc_refusals = [
            ([], "REFUSE: verb render|play required", _tc_kitfiles),
            (["render", "--text-file", _tc_textpath], "REFUSE: render needs --out", _tc_kitfiles),
            (["render", "--text-file", os.path.join(_tc_scr, "nope.txt"), "--out", _tc_out_a], "REFUSE: text file absent", _tc_kitfiles),
            (["render", "--text-file", _tc_empty, "--out", _tc_out_a], "REFUSE: text file empty", _tc_kitfiles),
            (["render", "--text-file", _tc_textpath, "--out", _tc_out_a], "REFUSE: kit exe absent", {}),
            (["render", "--text-file", _tc_textpath, "--out", _tc_out_a], "REFUSE: model absent", _tc_exeonly),
            (["play"], "REFUSE: play needs --file", _tc_kitfiles),
            (["play", "--file", os.path.join(_tc_scr, "nope.wav")], "REFUSE: file absent", _tc_kitfiles),
            (["bogus"], "REFUSE: unknown verb: bogus", _tc_kitfiles),
        ]
        ok_b = True
        for _argv, _want, _files in _tc_refusals:
            _n0 = len(_tc_calls)
            _cb, _ob, _tb, _kb, _hb = run_rig(_tc, lambda p, req: {}, argv=_argv, files=_files)
            ok_b = ok_b and _cb == 2 and _want in _ob and len(_tc_calls) == _n0 and not _kb

        # fire c: magic-byte dispatch via play --dry -> route named, ZERO player calls, no .ps1
        _tc_dispatch = [
            ("tts_clip_pcm.wav", 0, "[dry] play route=PCM"),
            ("tts_clip_mp3_f3.wav", 0, "[dry] play route=MP3"),
            ("tts_clip_mp3_fb.wav", 0, "[dry] play route=MP3"),
            ("tts_clip_garbage.bin", 3, "PLAY-NAMED"),
            ("tts_clip_silent.wav", 3, "SILENT-FAIL"),
        ]
        ok_c = True
        for _n, _rc, _want in _tc_dispatch:
            _n0 = len(_tc_calls)
            _fp = os.path.join(_tc_fix, _n)
            _cc, _oc, _tc2, _kc, _hc = run_rig(_tc, lambda p, req: {}, argv=["play", "--file", _fp, "--dry"])
            ok_c = ok_c and _cc == _rc and _want in _oc and len(_tc_calls) == _n0 and not _kc
            if _rc == 0:
                ok_c = ok_c and "bytes=%d" % os.path.getsize(_fp) in _oc and "ZERO player calls" in _oc
            if _n == "tts_clip_silent.wav":
                ok_c = ok_c and "%d bytes" % len(_tc_silent) in _oc
        ok_c = ok_c and not os.path.exists(os.path.join(_tc_fix, "tts-clip-play.ps1"))

        # fire d: silent-wav gate via the SIMULATED exe (mock-exe class: placeholder kit +
        # mocked subprocess.run; NO real TTS binary, no audio). Fresh out path per scenario.
        _tc_scen = [
            ("silent", _tc_silent, 0, 3, "SILENT-FAIL"),
            ("green", _tc_pcm, 0, 0, "rendered:"),
            ("nowav", None, 0, 3, "RENDER-NAMED"),
            ("dead", None, 1, 3, "RENDER-DEAD rc=1"),
        ]
        ok_d = True
        for _tag, _wav, _src, _rc, _want in _tc_scen:
            _tc_sim["wav"] = _wav; _tc_sim["rc"] = _src
            _n0 = len(_tc_calls)
            _tc_out_d = os.path.join(_tc_scr, "clip-" + _tag + ".wav")
            _cd, _od, _td, _kd, _hd = run_rig(_tc, lambda p, req: {}, files=_tc_kitfiles,
                argv=["render", "--text-file", _tc_textpath, "--out", _tc_out_d])
            _cmd = _tc_calls[-1] if len(_tc_calls) == _n0 + 1 else []
            ok_d = ok_d and _cd == _rc and _want in _od and len(_tc_calls) == _n0 + 1 and not _kd
            ok_d = ok_d and _cmd[:1] == [os.path.join(_hd, "tts", "audiocpp_cli.exe")]
            ok_d = ok_d and _tc_arg(_cmd, "--backend") == "cpu" and "--speed" not in _cmd and "--text-file" not in _cmd
            ok_d = ok_d and _tc_arg(_cmd, "--text") == _tc_text and _tc_arg(_cmd, "--out") == _tc_out_d
            ok_d = ok_d and _tc_arg(_cmd, "--model") == os.path.join(_hd, "tts", "kokoro-82m-q8_0.gguf")
            ok_d = ok_d and _tc_arg(_cmd, "--voice-id") == "af_heart"
            if _tag == "silent":
                ok_d = ok_d and "%d bytes" % len(_tc_silent) in _od
            if _tag == "green":
                ok_d = ok_d and "bytes=%d" % len(_tc_pcm) in _od and os.path.getsize(_tc_out_d) == len(_tc_pcm)
        _tc_noplayer = not any("powershell" in " ".join(c).lower() for c in _tc_calls)
        ok_calls = len(_tc_calls) == 4 and _tc_noplayer
        record("tts-clip-gates", ok_a and ok_b and ok_c and ok_d and ok_calls,
               "dry rc%d chars=%d refusals=%d ok_b=%s dispatch ok_c=%s silent=mock-exe ok_d=%s exe-calls=%d player-calls=0"
               % (_ca, _tc_chars, len(_tc_refusals), ok_b, ok_c, ok_d, len(_tc_calls)))
    except Exception as e:
        record("tts-clip-gates", False, "LEG-EXC %s: %s" % (type(e).__name__, e))
    finally:
        subprocess.run = _saved_run
        if _saved_exe is None: os.environ.pop("ORGANS_TTS_EXE", None)
        else: os.environ["ORGANS_TTS_EXE"] = _saved_exe
        if _saved_model is None: os.environ.pop("ORGANS_TTS_MODEL", None)
        else: os.environ["ORGANS_TTS_MODEL"] = _saved_model
_tts_clip_leg()

# ---------- hf-mirror-gates (Tier-2 hf_mirror organ: the 11-copy HF shelf-push family
# (_ship_v* 9 + hf_shelf_push twins) distilled; hygiene gate IN CODE before any hub call,
# HfApi behind the _hf_api() import seam). HERMETIC hub law: zero real hub calls, zero real
# tokens -- huggingface_hub is stubbed at the IMPORT BOUNDARY (sys.modules), the secret door
# is a scratch file carrying a stub value that is never printed. Fires through run_rig on a
# SCRATCH COPY with local.json BESIDE it + expanduser("~/organs.json") mocked away (the host
# config must never leak into the sandbox). Fixtures live in tests/fixtures/ -- a missing
# fixture records a NAMED FAIL, never a harness crash. Fires: (a) push --dry two fixture
# files -> rc0 two [dry] lines bytes= gate-pass ZERO hub calls (hub module None: any import
# attempt would die named); (a2) dry gate-fail row named GATE-FAIL; (b) arg-shape refusals
# rc2 before any door: verbless, push missing --files, path escape (incl. the sibling-prefix
# class), missing file, check without repo, unknown verb; (c) check with SECRETS at an empty
# dir -> REFUSE secret door absent rc2; (d) check with SECRETS unset + no config -> REFUSE
# no secrets_dir rc2; (e) stub seam repo_info raises -> HUB-DEAD named rc3, zero network;
# (f) stub seam green -> hub check files=2 rc0 (read-only door); (g) hub module absent ->
# HUB-DEAD rc3 named; (h) stub upload green -> pushed 2/2 rc0; (i) stub upload partial death
# -> pushed 1/2 rc3, dead row named. Loud-named: leg defects record a NAMED FAIL.
def _hf_mirror_leg():
    _saved_sec = os.environ.get("SECRETS")
    _saved_expanduser = os.path.expanduser
    _had_hf = "huggingface_hub" in sys.modules
    _saved_hf = sys.modules.get("huggingface_hub")
    try:
        _hm_src = os.path.join(REPO, "scripts", "hf_mirror.py")
        _hm_f1 = os.path.join(HERE, "fixtures", "hf_a.md")
        _hm_f2 = os.path.join(HERE, "fixtures", "hf_b.md")
        for _p in (_hm_src, _hm_f1, _hm_f2):
            if not os.path.exists(_p):
                record("hf-mirror-gates", False, "fixture absent: " + os.path.basename(_p))
                return
        _hm_scr = tempfile.mkdtemp(prefix="organs_hm_")
        # host-config isolation: ~/organs.json resolves to a scratch absent path all leg long
        os.path.expanduser = lambda p: os.path.join(_hm_scr, "no-organs.json") if p == "~/organs.json" else _saved_expanduser(p)
        _hm_repo = "fixture-org/fixture-corpus"
        _hm_kits = []
        for _kn, _pin in (("kit", {"hf_repo": _hm_repo}), ("kit2", {})):
            _kd = os.path.join(_hm_scr, _kn); os.makedirs(_kd)
            shutil.copy(_hm_src, os.path.join(_kd, "hf_mirror.py"))
            shutil.copy(os.path.join(REPO, "scripts", "scan_organ.py"), os.path.join(_kd, "scan_organ.py"))
            json.dump(_pin, open(os.path.join(_kd, "local.json"), "w", encoding="utf-8"))
            _hm_kits.append(os.path.join(_kd, "hf_mirror.py"))
        _hm, _hm2 = _hm_kits
        _hm_b1 = open(_hm_f1, encoding="utf-8").read()
        _hm_b2 = open(_hm_f2, encoding="utf-8").read()
        # bytes measured through run_rig's OWN write channel (text mode: newline
        # translation is OS-dependent) -- never assumed from the in-memory string
        def _hm_bytes(body):
            _bp = os.path.join(_hm_scr, "bytes_probe.md")
            open(_bp, "w", encoding="utf-8").write(body)
            return os.path.getsize(_bp)
        _hm_n1, _hm_n2 = _hm_bytes(_hm_b1), _hm_bytes(_hm_b2)
        _hm_files = {"canon/hf_a.md": _hm_b1, "canon/hf_b.md": _hm_b2}
        _hm_bad = "leak shape Bearer AbCdEf1234567890AbCdEf1234567890 tail" + chr(10)
        _hm_empty_sec = os.path.join(_hm_scr, "empty_sec"); os.makedirs(_hm_empty_sec)
        _hm_sec = os.path.join(_hm_scr, "sec"); os.makedirs(_hm_sec)
        _hm_stub_tok = "F-STUB-VALUE-NEVER-PRINTED"
        json.dump({"write_token": _hm_stub_tok}, open(os.path.join(_hm_sec, "huggingface.json"), "w", encoding="utf-8"))
        _hm_env = {"SECRETS": _hm_sec}
        _hm_seen = []
        import types as _hm_types
        def _hm_stub(dead=False, nfiles=2, upload_dead=False):
            _m = _hm_types.ModuleType("huggingface_hub")
            class _Api:
                def __init__(self, token=None): _hm_seen.append(("token", token))
                def repo_info(self, repo, files_metadata=True):
                    _hm_seen.append(("repo_info", repo))
                    if dead: raise RuntimeError("hermetic: hub door dead")
                    return _hm_types.SimpleNamespace(siblings=[object()] * nfiles)
                def upload_file(self, p, repo, path_in_repo=None):
                    _hm_seen.append(("upload", path_in_repo, repo))
                    if upload_dead and path_in_repo == "canon/hf_b.md":
                        raise RuntimeError("hermetic: upload door dead")
                    return None
            _m.HfApi = _Api
            return _m

        # fire a: push --dry -> rc0, two [dry] lines, gate-pass, ZERO hub (module None:
        # any import attempt dies ImportError -- dry must never reach the seam)
        sys.modules["huggingface_hub"] = None
        _ca, _oa, _ta, _ka, _ha = run_rig(_hm, lambda p, req: {}, files=_hm_files,
            argv=["push", "--files", "canon/hf_a.md,canon/hf_b.md", "--dry"], env={"SECRETS": _hm_empty_sec})
        ok_a = (_ca == 0 and "[dry] push canon/hf_a.md bytes=%d gate-pass repo=%s ZERO hub calls" % (_hm_n1, _hm_repo) in _oa
                and "[dry] push canon/hf_b.md bytes=%d gate-pass repo=%s ZERO hub calls" % (_hm_n2, _hm_repo) in _oa
                and "HUB-DEAD" not in _oa and not _ka)
        # fire a2: dry gate-fail row named (planted Bearer shape), clean row still gate-pass
        _ca2, _oa2, _ta2, _ka2, _ha2 = run_rig(_hm, lambda p, req: {},
            files={**_hm_files, "canon/hf_bad.md": _hm_bad},
            argv=["push", "--files", "canon/hf_a.md,canon/hf_bad.md", "--dry"], env={"SECRETS": _hm_empty_sec})
        ok_a2 = (_ca2 == 0 and "canon/hf_bad.md" in _oa2 and "GATE-FAIL" in _oa2 and "gate-pass" in _oa2 and not _ka2)

        # fire b: arg-shape refusals -> rc2 BEFORE any door, each named (hub module still None)
        _hm_refusals = [
            (_hm, [], "REFUSE: needs verb push|check"),
            (_hm, ["push"], "REFUSE: push needs --files"),
            (_hm, ["push", "--files", "../escape.md", "--dry"], "REFUSE: path escapes HOME"),
            (_hm, ["push", "--files", "../homeX/sibling.md", "--dry"], "REFUSE: path escapes HOME"),
            (_hm, ["push", "--files", "canon/absent.md", "--dry"], "REFUSE: file absent"),
            (_hm2, ["check"], "REFUSE: check needs --repo or hf_repo config"),
            (_hm, ["bogus"], "REFUSE: unknown verb: bogus"),
        ]
        ok_b = True
        for _rig, _argv, _want in _hm_refusals:
            _cb, _ob, _tb, _kb, _hb = run_rig(_rig, lambda p, req: {}, files=_hm_files, argv=_argv, env={"SECRETS": _hm_empty_sec})
            ok_b = ok_b and _cb == 2 and _want in _ob and not _kb

        # fire c: check, SECRETS at an EMPTY dir -> secret door absent rc2, zero hub
        _cc, _oc, _tc, _kc, _hc = run_rig(_hm, lambda p, req: {}, argv=["check"], env={"SECRETS": _hm_empty_sec})
        ok_c = (_cc == 2 and "REFUSE: secret door absent: huggingface.json" in _oc and not _kc)
        # fire d: check, SECRETS UNSET, no secrets config anywhere -> no secrets_dir rc2
        os.environ.pop("SECRETS", None)
        _cd, _od, _td, _kd, _hd = run_rig(_hm, lambda p, req: {}, argv=["check"])
        ok_d = (_cd == 2 and "REFUSE: no secrets_dir config" in _od and not _kd)

        # fire e: stub seam, repo_info raises -> HUB-DEAD named rc3, zero network; the seam
        # received the named-field stub token and the pinned repo; the value never prints
        sys.modules["huggingface_hub"] = _hm_stub(dead=True)
        _ce, _oe, _te, _ke, _he = run_rig(_hm, lambda p, req: {}, argv=["check"], env=_hm_env)
        ok_e = (_ce == 3 and "HUB-DEAD named: RuntimeError: hermetic: hub door dead" in _oe
                and "Traceback" not in _oe and not _ke
                and ("token", _hm_stub_tok) in _hm_seen and ("repo_info", _hm_repo) in _hm_seen
                and _hm_stub_tok not in _oe)
        # fire f: stub seam green -> hub check files=2 rc0 (read-only door)
        sys.modules["huggingface_hub"] = _hm_stub(nfiles=2)
        _cf, _of, _tf, _kf, _hf = run_rig(_hm, lambda p, req: {}, argv=["check"], env=_hm_env)
        ok_f = (_cf == 0 and "hub check %s files=2 (read-only door)" % _hm_repo in _of and not _kf and _hm_stub_tok not in _of)
        # fire g: hub module ABSENT at the import boundary -> HUB-DEAD rc3 named
        sys.modules["huggingface_hub"] = None
        _cg, _og, _tg, _kg, _hg = run_rig(_hm, lambda p, req: {}, argv=["check"], env=_hm_env)
        ok_g = (_cg == 3 and "HUB-DEAD: huggingface_hub not importable" in _og and not _kg)
        # fire h: stub upload green -> pushed 2/2 rc0, uploads at the pinned repo
        sys.modules["huggingface_hub"] = _hm_stub()
        _ch, _oh, _th, _kh, _hh = run_rig(_hm, lambda p, req: {}, files=_hm_files,
            argv=["push", "--files", "canon/hf_a.md,canon/hf_b.md"], env=_hm_env)
        ok_h = (_ch == 0 and "pushed canon/hf_a.md bytes=%d" % _hm_n1 in _oh and "pushed 2/2 stamp=" in _oh
                and not _kh and ("upload", "canon/hf_a.md", _hm_repo) in _hm_seen
                and ("upload", "canon/hf_b.md", _hm_repo) in _hm_seen and _hm_stub_tok not in _oh)
        # fire i: stub upload partial death -> pushed 1/2 rc3, dead row named, no traceback
        sys.modules["huggingface_hub"] = _hm_stub(upload_dead=True)
        _ci, _oi, _ti, _ki, _hi = run_rig(_hm, lambda p, req: {}, files=_hm_files,
            argv=["push", "--files", "canon/hf_a.md,canon/hf_b.md"], env=_hm_env)
        ok_i = (_ci == 3 and "HUB-DEAD named canon/hf_b.md" in _oi and "pushed 1/2 stamp=" in _oi
                and "Traceback" not in _oi and not _ki)
        record("hf-mirror-gates", ok_a and ok_a2 and ok_b and ok_c and ok_d and ok_e and ok_f and ok_g and ok_h and ok_i,
               "a=%d a2=%d b=%d c=%d d=%d e=%d f=%d g=%d h=%d i=%d dryrc=%d doors=%d"
               % (ok_a, ok_a2, ok_b, ok_c, ok_d, ok_e, ok_f, ok_g, ok_h, ok_i, _ca, len(_ka)))
    except Exception as e:
        record("hf-mirror-gates", False, "LEG-EXC %s: %s" % (type(e).__name__, e))
    finally:
        os.path.expanduser = _saved_expanduser
        if _had_hf: sys.modules["huggingface_hub"] = _saved_hf
        else: sys.modules.pop("huggingface_hub", None)
        if _saved_sec is None: os.environ.pop("SECRETS", None)
        else: os.environ["SECRETS"] = _saved_sec
_hf_mirror_leg()

# ---------- inbox-gate-gates (inbox_gate organ: the leg118 rig3b coverage ack-loop +
# rig2 band sweep distilled). THE LAW in code: numeric ack proxies INVERT on quiet
# threads; the coverage form is authority -- (a) every served post swept (200 +
# has_more False), (b) zero unbanked ids in band, (c) re-read served==banked -- only
# THEN ack, and every refusal precedes POST. HERMETIC: the organ's module-level
# _opener seam is stubbed per fire (records method/path/headers/body); the real
# urlopen is POISONED for the whole leg (any seam bypass dies named), time.sleep
# mocked, ~/organs.json mocked away, organ exec'd from a scratch kit copy with an
# empty local.json (host config never leaks). Fires: (a) check green rc0 zero POST
# zero writes; (b) ack --dry plan green ZERO POST; (c) ack live green: exactly 1
# POST, 5-field wrapper verbatim, receipt gate, postack read, secret only in the
# Authorization header, stub value never printed; (d) unbanked served id with no
# post_id -> REFUSE rc2 zero POST; (e) has_more True post -> REFUSE rc2 condition
# (a) zero POST; (f) check red missing named, bank untouched; (g) 429-HTML body ->
# DOOR-DEAD rc3; (h) non-JSON 200 body -> NON-JSON + DOOR-DEAD rc3; (i) 400 flood ->
# STARVE-GUARD rc3 early stop (bounded calls); (j) missing secret door -> REFUSE rc2
# zero door calls; (k) bare invocation rc2; (l) arg-shape refusals rc2; (m) named
# field absent rc2; (n) live sweep banks the unbanked hit store-then-advance, re-reads,
# then acks (1 POST). Loud-named: leg defects record a NAMED FAIL.
def _inbox_gate_leg():
    _ig_envkeys = ("ORGANS_HOME", "ORGANS_SECRETS", "ORGANS_INBOX_URL", "ORGANS_INBOX_UA")
    _saved_env = {k: os.environ.get(k) for k in _ig_envkeys}
    _saved_expanduser = os.path.expanduser
    _saved_urlopen = urllib.request.urlopen
    _saved_sleep = time.sleep
    try:
        _ig_src = os.path.join(REPO, "scripts", "inbox_gate.py")
        if not os.path.exists(_ig_src):
            record("inbox-gate-gates", False, "organ absent: scripts/inbox_gate.py")
            return
        _ig_scr = tempfile.mkdtemp(prefix="organs_ig_")
        os.path.expanduser = lambda p: os.path.join(_ig_scr, "no-organs.json") if p == "~/organs.json" else _saved_expanduser(p)
        def _ig_poison(req, timeout=None, **kw):
            raise AssertionError("network bypass: _opener seam not used")
        urllib.request.urlopen = _ig_poison
        time.sleep = lambda s: None
        _ig_kit = os.path.join(_ig_scr, "kit"); os.makedirs(_ig_kit)
        shutil.copy(_ig_src, os.path.join(_ig_kit, "inbox_gate.py"))
        json.dump({}, open(os.path.join(_ig_kit, "local.json"), "w", encoding="utf-8"))
        _ig_rig = os.path.join(_ig_kit, "inbox_gate.py")
        _ig_src_text = open(_ig_rig, encoding="utf-8").read()
        _ig_home = os.path.join(_ig_scr, "home"); os.makedirs(_ig_home)
        _ig_sec = os.path.join(_ig_scr, "sec"); os.makedirs(_ig_sec)
        _ig_stub = "IG-STUB-SECRET-NEVER-PRINTED"
        json.dump({"secret": _ig_stub}, open(os.path.join(_ig_sec, "1f916.json"), "w", encoding="utf-8"))
        _ig_empty_sec = os.path.join(_ig_scr, "empty_sec"); os.makedirs(_ig_empty_sec)
        _ig_badfield_sec = os.path.join(_ig_scr, "badfield_sec"); os.makedirs(_ig_badfield_sec)
        json.dump({"other_field": "x"}, open(os.path.join(_ig_badfield_sec, "1f916.json"), "w", encoding="utf-8"))
        _ig_offer = {"version": 1, "timestamp": "2026-01-01T00:00:00Z", "comments": 102, "mentions": 0, "seal": "fixture-seal"}
        _ig_rows = [{"id": 101, "post_id": 11}, {"id": 102, "post_id": 12}]
        def _ig_me(rows, offer):
            slv = {b: [] for b in ("replies", "comments_on_your_posts", "in_threads_you_joined", "mentions_of_you")}
            slv["replies"] = list(rows)
            return {"me": {"now_utc": "x", "since_last_visit": slv, "ack_cursor": offer}}
        _ig_postdocs = {11: {"comments": [{"id": 101, "post_id": 11}], "has_more": False},
                        12: {"comments": [{"id": 102, "post_id": 12}], "has_more": False},
                        13: {"comments": [], "has_more": False}}
        def _ig_bank(rows):
            p = os.path.join(_ig_home, "bank.jsonl")
            open(p, "w", encoding="utf-8").write("".join(json.dumps({"bucket": "b", "row": r}) + chr(10) for r in rows))
            return p
        def _ig_router(served, offer, postdocs=None, me_err=None, me_raw=None, post_err=None, receipt=None):
            _st = {"acked": False}
            _pd = _ig_postdocs if postdocs is None else postdocs
            def router(p, req):
                if p.startswith("/api/me/ack"):
                    _st["acked"] = True
                    return receipt if receipt is not None else {"advanced": True, "mode": "lossless", "comments": offer["comments"], "mentions": offer["mentions"]}
                if p.startswith("/api/me"):
                    if me_err: return ("raise", me_err[0], me_err[1])
                    if me_raw is not None: return me_raw
                    return _ig_me([] if _st["acked"] else served, None if _st["acked"] else offer)
                m = re.match(r"/api/post/(\d+)", p)
                if m:
                    if post_err: return ("raise", post_err[0], post_err[1])
                    return _pd.get(int(m.group(1)), {"comments": [], "has_more": False})
                return {}
            return router
        def _ig_fire(argv, router, env=None):
            _ns = {"__name__": "inbox_gate_test", "__file__": _ig_rig}
            _calls = []
            def _opener(req, timeout=30):
                _m = getattr(req, "method", None) or ("POST" if req.data is not None else "GET")
                _p = req.full_url.split("://", 1)[1]; _p = _p[_p.find("/"):]
                _body = json.loads(req.data.decode()) if req.data else None
                _calls.append((_m, _p, dict(req.headers), _body))
                _r = router(_p, req)
                if isinstance(_r, tuple) and _r[0] == "raise":
                    raise urllib.error.HTTPError(req.full_url, _r[1], "stub", None, io.BytesIO(_r[2]))
                return FakeResp(json.dumps(_r).encode() if isinstance(_r, (dict, list)) else _r)
            exec(compile(_ig_src_text, _ig_rig, "exec"), _ns)
            _ns["_opener"] = _opener
            os.environ["ORGANS_HOME"] = _ig_home
            os.environ["ORGANS_SECRETS"] = _ig_sec
            for k, v in (env or {}).items(): os.environ[k] = v
            _buf = io.StringIO(); _rc = 0
            try:
                with contextlib.redirect_stdout(_buf):
                    _rc = _ns["main"](argv)
            except SystemExit as e:
                _rc = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
            except Exception as e:
                _rc = 90; _buf.write("LEG-EXC %s: %s" % (type(e).__name__, e))
            return _rc, _buf.getvalue(), _calls
        def _ig_posts(calls): return [c for c in calls if c[0] == "POST"]
        _ig_bankpath = _ig_bank(_ig_rows)
        _ig_base_argv = ["--posts", "11,12", "--bank", _ig_bankpath]
        # fire a: check green -> rc0, per-post swept/banked/missing verdicts, zero POST, zero writes
        _ba = open(_ig_bankpath, encoding="utf-8").read()
        _ca, _oa, _ka = _ig_fire(["check"] + _ig_base_argv, _ig_router(_ig_rows, _ig_offer))
        ok_a = (_ca == 0 and "COVERAGE GREEN" in _oa and "POST 11 swept=True banked=1 missing=[]" in _oa
                and "POST 12 swept=True banked=1 missing=[]" in _oa and not _ig_posts(_ka)
                and open(_ig_bankpath, encoding="utf-8").read() == _ba and _ig_stub not in _oa)
        # fire b: ack --dry green -> plan proven, ZERO POST, zero writes
        _cb, _ob, _kb = _ig_fire(["ack"] + _ig_base_argv + ["--dry"], _ig_router(_ig_rows, _ig_offer))
        ok_b = (_cb == 0 and "ACK-PLAN green" in _ob and "ZERO POST" in _ob and not _ig_posts(_kb)
                and any(c[0] == "GET" for c in _kb) and open(_ig_bankpath, encoding="utf-8").read() == _ba
                and _ig_stub not in _ob)
        # fire c: ack live green -> exactly 1 POST, wrapper verbatim, receipt gate, postack read
        _cc, _oc, _kc = _ig_fire(["ack"] + _ig_base_argv, _ig_router(_ig_rows, _ig_offer))
        _pc = _ig_posts(_kc)
        ok_c = (_cc == 0 and len(_pc) == 1 and _pc[0][1] == "/api/me/ack" and _pc[0][3] == {"up_to": _ig_offer}
                and "INBOX-GATE GREEN" in _oc and "POSTACK served=0" in _oc
                and any(c[2].get("Authorization") == "Bearer " + _ig_stub for c in _kc)
                and _ig_stub not in _oc and "Traceback" not in _oc)
        # fire d: unbanked served id with no post_id to sweep -> REFUSE rc2, zero POST
        _ig_d_served = [{"id": 101, "post_id": 11}, {"id": 103}]
        _cd, _od, _kd = _ig_fire(["ack"] + _ig_base_argv, _ig_router(_ig_d_served, _ig_offer))
        ok_d = (_cd == 2 and "REFUSE" in _od and "unbanked" in _od and "103" in _od
                and not _ig_posts(_kd) and _ig_stub not in _od)
        # fire e: has_more True post -> condition (a) REFUSE rc2 zero POST; check red too
        _ig_e_pd = {11: _ig_postdocs[11], 12: {"comments": [{"id": 102, "post_id": 12}], "has_more": True}}
        _ce, _oe, _ke = _ig_fire(["ack"] + _ig_base_argv, _ig_router(_ig_rows, _ig_offer, postdocs=_ig_e_pd))
        _ce2, _oe2, _ke2 = _ig_fire(["check"] + _ig_base_argv, _ig_router(_ig_rows, _ig_offer, postdocs=_ig_e_pd))
        ok_e = (_ce == 2 and "REFUSE" in _oe and "not swept" in _oe and not _ig_posts(_ke)
                and _ce2 == 2 and "COVERAGE RED" in _oe2 and not _ig_posts(_ke2))
        # fire f: check red, missing named, bank untouched, zero POST
        _ig_f_bank = _ig_bank([_ig_rows[0]])
        _bf = open(_ig_f_bank, encoding="utf-8").read()
        _cf, _of, _kf = _ig_fire(["check", "--posts", "11,12", "--bank", _ig_f_bank], _ig_router(_ig_rows, _ig_offer))
        ok_f = (_cf == 2 and "COVERAGE RED" in _of and "missing=[102]" in _of and not _ig_posts(_kf)
                and open(_ig_f_bank, encoding="utf-8").read() == _bf)
        # fire g: 429-HTML body -> DOOR-DEAD named rc3, zero POST, no traceback
        _cg, _og, _kg = _ig_fire(["check"] + _ig_base_argv,
            _ig_router(_ig_rows, _ig_offer, me_err=(429, b"<html><body>rate limited</body></html>")))
        ok_g = (_cg == 3 and "DOOR-DEAD" in _og and "429-HTML" in _og and not _ig_posts(_kg) and "Traceback" not in _og)
        # fire h: non-JSON 200 body -> NON-JSON named + DOOR-DEAD rc3 (CATCHES 302 shape)
        _ch, _oh, _kh = _ig_fire(["check"] + _ig_base_argv,
            _ig_router(_ig_rows, _ig_offer, me_raw=b"<html>302 shell</html>"))
        ok_h = (_ch == 3 and "NON-JSON" in _oh and "DOOR-DEAD" in _oh and not _ig_posts(_kh) and "Traceback" not in _oh)
        # fire i: 400 flood -> STARVE-GUARD rc3 early stop: 1 door + 3 post attempts, zero POST
        _ci, _oi, _ki = _ig_fire(["check", "--posts", "11,12,13", "--bank", _ig_bankpath],
            _ig_router(_ig_rows, _ig_offer, post_err=(400, b"{}")))
        ok_i = (_ci == 3 and "STARVE-GUARD" in _oi and len(_ki) == 4 and not _ig_posts(_ki))
        # fire j: missing secret door -> REFUSE rc2, ZERO door calls (lazy load before the door)
        _cj, _oj, _kj = _ig_fire(["check"] + _ig_base_argv, _ig_router(_ig_rows, _ig_offer),
            env={"ORGANS_SECRETS": _ig_empty_sec})
        ok_j = (_cj == 2 and "REFUSE" in _oj and "secret door absent" in _oj and not _kj)
        # fire k: bare invocation -> rc2 named, zero door calls
        _ck, _ok, _kk = _ig_fire([], _ig_router(_ig_rows, _ig_offer))
        ok_k = (_ck == 2 and "REFUSE" in _ok and "needs verb" in _ok and not _kk)
        # fire l: arg-shape refusals -> rc2 named before any door
        ok_l = True
        for _argv, _want in ((["check"], "--posts"), (["check", "--posts", "11"], "--bank"),
                             (["bogus"], "unknown verb"), (["check", "--posts", "x", "--bank", _ig_bankpath], "bad --posts")):
            _cl, _ol, _kl = _ig_fire(_argv, _ig_router(_ig_rows, _ig_offer))
            ok_l = ok_l and _cl == 2 and "REFUSE" in _ol and _want in _ol and not _kl
        # fire m: named field absent in the secret door -> REFUSE rc2, zero door calls
        _cm, _om, _km = _ig_fire(["check"] + _ig_base_argv, _ig_router(_ig_rows, _ig_offer),
            env={"ORGANS_SECRETS": _ig_badfield_sec})
        ok_m = (_cm == 2 and "REFUSE" in _om and "named field absent" in _om and not _km)
        # fire n: live sweep banks the unbanked hit (store-then-advance), re-reads, then acks
        _ig_n_bank = _ig_bank([_ig_rows[0]])
        _cn, _on, _kn = _ig_fire(["ack", "--posts", "11,12", "--bank", _ig_n_bank], _ig_router(_ig_rows, _ig_offer))
        _pn = _ig_posts(_kn)
        _bn = open(_ig_n_bank, encoding="utf-8").read()
        ok_n = (_cn == 0 and len(_pn) == 1 and "BANK post 12 new=1" in _on
                and "re-read before ack" in _on and "INBOX-GATE GREEN" in _on
                and '"id": 102' in _bn and len(_bn.strip().split(chr(10))) == 2 and _ig_stub not in _on)
        _ig_post_total = sum(len(_ig_posts(x)) for x in (_ka, _kb, _kc, _kd, _ke, _ke2, _kf, _kg, _kh, _ki, _kj, _kk, _km, _kn))
        record("inbox-gate-gates",
               ok_a and ok_b and ok_c and ok_d and ok_e and ok_f and ok_g and ok_h and ok_i and ok_j and ok_k and ok_l and ok_m and ok_n and _ig_post_total == 2,
               "a=%d b=%d c=%d d=%d e=%d f=%d g=%d h=%d i=%d j=%d k=%d l=%d m=%d n=%d posts=%d"
               % (ok_a, ok_b, ok_c, ok_d, ok_e, ok_f, ok_g, ok_h, ok_i, ok_j, ok_k, ok_l, ok_m, ok_n, _ig_post_total))
    except Exception as e:
        record("inbox-gate-gates", False, "LEG-EXC %s: %s" % (type(e).__name__, e))
    finally:
        os.path.expanduser = _saved_expanduser
        urllib.request.urlopen = _saved_urlopen
        time.sleep = _saved_sleep
        for k in _ig_envkeys:
            if _saved_env[k] is None: os.environ.pop(k, None)
            else: os.environ[k] = _saved_env[k]
_inbox_gate_leg()

n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
print(f"\n=== organs suite: {len(RESULTS)} tests, {len(RESULTS)-n_fail} pass, {n_fail} fail ===")
sys.exit(1 if n_fail else 0)
