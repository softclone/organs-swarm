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

# dream_beat.py — the dream organ's heartbeat (keeper order 2026-11-07, verbatim: "we do have budget for dreams, use your own seat on strata... 10 minute heartbeats give it plenty of space between your turns")
# LIMITS (H19 census 2026-11-07): sqlite backup+merge is safe for a QUIET store — a live write during backup can split the snapshot (bound: capture bells fire from THIS shop only, single writer);
# BOUND: the material gate's WHERE binds the RUNNER identity (--agent-id <runner>);
# merge loop must close OUTSIDE the table loop (#144 cure, in force);
# provider floor MNEMOS_MAX_TOKENS>=131072 (keeper law) — a store-side config regression re-prices every dream;
# material gate (six classes) is a TIME function: skips are the designed output for a young store, not failure;
# WSL2 route dies on host reboot (forwarder proc + ~/.mnemos/.env + WSL python deps are reboot-ephemeral).
# silent-failure probe fired 2026-11-07: skip-path exercised 6x (0.2s, zero model calls); merge-path exercised by hand-flight; real-dream path UNEXERCISED (material gate) — named bound.
# Runs as no_agent cron script. Zero LLM on the shop side; skips cost zero model calls; a real dream draws the shop's own seat via the :18080 forwarder.
# Safety: the LIVE store is never opened by WSL (9P corruption risk). Live -> sqlite backup -> copy -> dream on copy in WSL -> journal/belief rows merged back (busy_timeout tx).
import sqlite3, subprocess, sys, time, shutil, os

LIVE = os.environ.get("ORGANS_MNEMOS_DB", os.path.expanduser("~/mnemos/mnemos.db"))
STAGE = os.path.join(HOME, "data/dream/mdb-copy.sqlite")
# N5 cure (C5-16484): dead SH constant deleted -- the real WSL path is the literal at the subprocess leg

def main():
    t0 = time.time()
    os.makedirs(os.path.dirname(STAGE), exist_ok=True)
    # 1. snapshot live store (sqlite online backup — safe while MCP server runs)
    # W5 cure (C5-16484): sqlite CONNECTS-THEN-CREATES a missing LIVE store; dreams used to
    # run against a silently created empty DB. Fail closed on a missing store.
    if not os.path.exists(LIVE):
        print(f"DREAM-RED: LIVE store missing at {LIVE} -- refusing (exit 1)", flush=True)
        sys.exit(1)
    src = sqlite3.connect(LIVE, timeout=15)
    dst = sqlite3.connect(STAGE)
    src.backup(dst)
    dst.close(); src.close()
    # WAL SIDEAR CURE (2026-11-10): backup writes rows into STAGE's -wal sidecar; cp to WSL carries ONLY the
    # main file, so fresh queue rows are invisible to the organ (rows sat in an 11.6 MB sidecar; beats skipped
    # 'no question waits' while every door probe on Windows read the sidecar and showed them). Force the
    # main file to carry everything before the copy leg:
    ck = sqlite3.connect(STAGE, timeout=15)
    ck.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    ck.close()
    # 2. dream the hour on the copy, inside WSL
    p = subprocess.run(["wsl", "-e", "bash", (lambda _s: (_s if "USER" not in _s else __import__("sys").exit("DREAM-SH-UNCONFIGURED: set ORGANS_DREAM_SH (the placeholder default is not a real script) -- exit 2") or _s))(os.environ.get("ORGANS_DREAM_SH", "/mnt/c/USER/shop/data/dream_hour.sh"))],
                       capture_output=True, text=True, timeout=600)
    # B1 cure (clean-room audit child, deleg_a5592ce2, 2026-11-11): the WSL leg's returncode was
    # never inspected -- a dead WSL route (reboot-ephemeral, per this rig's own LIMITS line) exited 0
    # silently every 10 minutes. Dead producer = keeper alert.
    if p.returncode != 0:
        print(f"dream-beat DEAD-LEG: wsl exited {p.returncode} | {repr((p.stdout + p.stderr)[:200])} -- keeper alert")
        raise SystemExit(1)
    out = (p.stdout + p.stderr).strip().splitlines()
    verdict = next((l for l in out if "dream hour" in l), out[-1] if out else "no-output")
    # 2b. handoff prompt lands on disk for the shop to take (2026-11-07): the shop reads it at its next sweep.
    # W8 cure: the gate matched ANY line containing 'DREAM' -- error paths carry the word too, planting a
    # prompt from a broken run. Gate on the SUCCESS marker only (verdict line).
    # F-05 CURE (deleg_b499ec12): error lines carry the shared prefix "dream hour" too -- the gate is
    # a SUCCESS marker test: prefix present, skip named, and NO error token in the verdict.
    if ("dream hour" in verdict) and "skipped" not in verdict and "ERROR" not in verdict.upper():
        pf = os.path.join(HOME, "data/dream/pending-handoff-%s.md") % time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        with open(pf, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out))
        verdict += " | PROMPT ON DISK: " + os.path.basename(pf)
    # 3. merge dream output rows back (journal_entries, beliefs) — insert-if-missing, short tx
    live = sqlite3.connect(LIVE, timeout=20)
    live.execute("PRAGMA busy_timeout=15000")
    copy = sqlite3.connect(STAGE, timeout=5)
    merged = {"journal": 0, "beliefs": 0}
    for table, merged_key in (("journal_entries", "journal"), ("beliefs", "beliefs")):
        cols = [r[1] for r in copy.execute(f"PRAGMA table_info({table})").fetchall()]
        rows = copy.execute(f"SELECT * FROM {table}").fetchall()
        idix = cols.index("id")
        have = {r[0] for r in live.execute(f"SELECT id FROM {table}").fetchall()}
        n = 0
        for row in rows:
            if row[idix] not in have:
                live.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})", row)
                n += 1
        merged[merged_key] = n
    copy.close()
    live.commit(); live.close()
    print(f"dream-beat {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} | {verdict} | merged {merged} | {time.time()-t0:.1f}s | swift")

if __name__ == "__main__":
    main()
