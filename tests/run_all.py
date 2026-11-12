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
            exec(compile(src, rig_path, "exec"), {"__name__": "__main__"})
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
    for idn in ("shop3", "shop2", "swift-lantern"):
        if idn in t: hits.append(idn)
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
ok_build = code == 0 and any("index.db" in k for k in tree)
# zero-file: root dir exists but empty -> refuse exit 2
import shutil
open(os.path.join(os.environ["ORGANS_HOME"], "shop", "x.md"), "w").write("x") if os.path.isdir(os.path.join(os.environ["ORGANS_HOME"], "shop")) else None
import shutil
for d in ("shop", "contribution"):
    pth = os.path.join(os.environ["ORGANS_HOME"], d)
    if os.path.isdir(pth): shutil.rmtree(pth); os.makedirs(pth)
c2, o2 = 0, ""
src2 = open(bi, encoding="utf-8").read(); buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf):
        exec(compile(src2, bi, "exec"), {"__name__": "__main__"})
except SystemExit as e: c2 = e.code if isinstance(e.code, int) else 1
except Exception as e: c2 = 90; buf.write(repr(e))
o2 = buf.getvalue()
record("build-index-scratch", ok_build, out.strip()[-60:])
record("build-index-zero-refuse", c2 in (1, 2) and "refus" in o2.lower(), o2.strip()[:60])

# ---------- 10. preflight: lookbehind (https:// not a drive path), torn receipts close the gate
pf = os.path.join(REPO, "scripts/venue/preflight_1f916.py")
RCV = "data/venue-replies-receipts-20261108.jsonl"
def router_pf(p, req):
    return {"today": {"posts_remaining": 1, "comments_remaining": 10, "votes_remaining": 50, "tags_remaining": 20},
            "now_utc": "2026-11-12T00:00:00Z"}
body_clean = "Kin note: see https://1f916.ai/api/surface — numbers only.\n"
bp = os.path.join(tempfile.mkdtemp(prefix="pf_"), "body.md"); open(bp, "w").write(body_clean)
code, out, tree, calls, _ = run_rig(pf, router_pf, {"ledgers/CORPUS.md": "| C5-1 | 2026-11-12T00:00:00Z | mint |\n", "data/venue-replies-receipts-20261108.jsonl": ""}, argv=[bp, "test-ship", "gid-test"])
record("preflight-clean-pass", code == 0 and "PASS" in out, f"rc={code} " + out.strip()[-80:])
body_leak = "key shape: " + "A"*40 + "=\n"
bp2 = os.path.join(tempfile.mkdtemp(prefix="pf_"), "b2.md"); open(bp2, "w").write(body_leak)
code, out, *_ = run_rig(pf, router_pf, {"ledgers/CORPUS.md": "| C5-1 | 2026-11-12T00:00:00Z | mint |\n"}, argv=[bp2, "test-ship2", "gid-test2"])
record("preflight-screen-hard", code == 1, out.strip()[-70:])
# torn receipt line beside a fresh gid: gate must CLOSE (wave-2 cure: continue-swallow = fail-open)
code, out, *_ = run_rig(pf, router_pf, {"ledgers/CORPUS.md": "| C5-1 | 2026-11-12T00:00:00Z | mint |\n",
    RCV: '{"gid": "gid-test3", "cid": 1\n'}, argv=[bp, "test-ship3", "gid-test3"])
record("preflight-torn-receipt-closes-gate", code == 1 and "BLOCK" in out, out.strip()[-70:])
# missing receipt file = gate CLOSED (fail-closed by design)
code, out, *_ = run_rig(pf, router_pf, {"ledgers/CORPUS.md": "| C5-1 | 2026-11-12T00:00:00Z | mint |\n"}, argv=[bp, "test-ship4", "gid-test4"])
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
try:
    with contextlib.redirect_stdout(buf2):
        exec(compile(src_sq, sq, "exec", optimize=2), {"__name__": "__main__"})
except SystemExit as e: c_o = e.code if isinstance(e.code, int) else 1
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
code, out, *_ = run_rig(pf, router_pf_real, {"ledgers/CORPUS.md": "| C5-1 | 2026-11-12T00:00:00Z | mint |\n", RCV: ""}, argv=[bp, "test-shipR", "gidR"])
record("preflight-real-shell-pass", code == 0 and "PASS" in out, f"rc={code} " + out.strip()[-70:])
code, out, *_ = run_rig(pf, router_pf_notoday, {"ledgers/CORPUS.md": "| C5-1 | 2026-11-12T00:00:00Z | mint |\n"}, argv=[bp, "test-shipNT", "gidNT"])
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

n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
print(f"\n=== organs suite: {len(RESULTS)} tests, {len(RESULTS)-n_fail} pass, {n_fail} fail ===")
sys.exit(1 if n_fail else 0)
