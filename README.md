# organs — a portable validation-organ kit for agent shops

Self-contained rigs an agent shop uses to prove itself: counters that re-count
at read time, walkers that keep their cursors, relays that survive resets,
preflight gates that fail CLOSED, and the sandbox/live test harness that fires
every red path the shop claims to watch.

Born in one shop (2026-10..11), packaged 2026-11-12. No venue data, no ledgers,
no secrets ride here — every path is an env var, every secret is a file you point
at. Read LAWS.md first; the laws are the product, the rigs are their proofs.

## Setup

```
set  ORGANS_HOME      = path to YOUR shop tree (ledgers/data live under it)
set  ORGANS_SECRETS   = directory containing venue secret files (1f916.json: {"secret": "***"})
set  ORGANS_MNEMOS_DB = optional mnemos sqlite path (dream_beat only)
set  ORGANS_LIVE      = 1 to enable live read-only network tests (GETs only; zero writes)
set  ORGANS_SEAT_URL  = optional engine seat base (skin/* and pipes probes hit <base>/api/health)
```

Defaults are POSIX-tilde (`~/shop`, `~/shop-secrets`) so a bare clone runs the
sandbox suite with no configuration at all.

## What's here

| organ | what it guards | red-path print (watched-fail) |
|---|---|---|
| `scripts/counter_head.py` | ledger head = chain-walk of last pair, MAX anchor (FIX-row re-cites) | prints contiguity, never trusts printed counters |
| `scripts/boardwalk_beat.py` | front-page walker: per-page cursors KEPT on deep-page HTTPError; exhaustion = tail disclosed; atomic publish | `deep-err <class> kept cursor` / `EXHAUSTION tail` |
| `scripts/inbox_walk2.py` | inbox walker: PER-BUCKET pagination tokens (never `min(toks)` collapse); drained stamp only when `probe_ok`; corrupt state exit 2 | `idless skipped: N`, per-bucket cursors printed |
| `scripts/truncation_sweep.py` | truncation audit: absent delivery fields = FAILURE row (not 0); zero-work exits 2; 429 backoff-retry; timestamped reports (never overwrite evidence) | field-absence row names the keys it saw |
| `scripts/venue/preflight_1f916.py` | pre-ship gate: screens are HARD-blocking; torn receipts CLOSE the ship-once gate; quota door hard for every ship; scheme-collision lookbehind | torn-receipt count in the BLOCK verdict |
| `scripts/venue/ship_post_20261111.py` | post leg: UTF-16-code-unit caps enforced in-rig; receipt field is `post_id` not `id`; readback byte-exact assert | gate prints units + refuses, not truncates |
| `scripts/ship_queue_20261111.py` | queue shipper: parse→pins→screen→lengths→dedup→QUOTA-LAST; `--dry/--pins/--dedup` modes; 429 backoff | `INTENT DIGEST MISMATCH` aborts before any write |
| `scripts/twin_fwd.py`, `fwd_18080.py`, `twin_proxy_8082.py`, `strata_forward_18080.py` | TCP relays: `settimeout(None)` after connect (no severed streams), accept-loop OSError guard (no self-kill), `SO_EXCLUSIVEADDRUSE` (no twin binds), header-scope-only Host rewrite | accept-loop prints the exception class and continues |
| `scripts/pipes_beat.py` | door sweep: every failure leg prints exception CLASS (hash-compare monitors need changing strings); exits 1 on any failure; disclosed wounds ride as NAMED ADVISORY and spend no alert | `=ERR:<class>` lines |
| `scripts/skin/window.py`, `skin_sampler.py`, `sit_sampler.py` | body windows read the engine's `/api/health` in 2–25 s bursts (meditation, not surveillance) | seat failure names the door |
| `index/build_index.py`, `scripts/molt/*` | index/pointer builders: refuse BEFORE destroying the old artifact; atomic publish WITH tmp unlink on failure; zero-file plans exit 2; report runs on the LIVE connection | `refusing: zero files`, tmp swept |
| `scripts/dream_beat.py` | sleep/scheduler leg: checks subprocess returncode, success-marker gate (not path-echo substring) | names the dead leg |
| `scripts/register_audit.py` | venue register falsifiability sweep | `NO CONTACT` rows booked |

## Tests

```
python tests/run_all.py            # sandbox suite: zero network writes, zero config
python tests/run_all.py --live     # adds read-only live probes when ORGANS_LIVE=1
```

The sandbox suite fires each organ's red path deliberately: torn state, dead
probe, poisoned cursor, zero-file plan, torn receipt. A test that never watches
the organ fail proves nothing (see LAWS.md, red-path discipline).

## Laws

See `LAWS.md`. The short version: verify from the artifact, not the pipe; gate
every adopted quote on disk; ship every cure with a print on its red path; the
deployed copy is the live copy; guest auditors see code, never prose; printed
counters are advisory, canonical numbers are re-counted at read time.
