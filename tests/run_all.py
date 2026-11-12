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

n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
print(f"\n=== organs suite: {len(RESULTS)} tests, {len(RESULTS)-n_fail} pass, {n_fail} fail ===")
sys.exit(1 if n_fail else 0)
