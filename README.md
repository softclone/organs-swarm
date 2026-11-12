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
set  ORGANS_MNEMOS     = mnemos sqlite path (dream_beat; else config key 'mnemos' in ~/organs.json)
set  ORGANS_DREAM_SH  = the dream-hour script path (dream_beat; else config key 'dream_sh'; a placeholder
                       default refuses with a named exit 2, per the F-13 audit cure)
set  ORGANS_SEAT_URL  = engine seat base (skin/* and pipes probes hit <base>/api/health; live suite leg; GET-only)
set  ORGANS_GGUF_FILE = default .gguf for molt/gguf_hist.py (argv also works; absent = named exit 2)
```

Every `ORGANS_*` value ALSO rides a config file, resolved in order
`env -> <rig-dir>/local.json -> ~/organs.json` — so bells fire green with an empty environment.
Config keys (same JSON, any subset): `home`, `secrets`, `shop_dir`, `leg_dir`, `mnemos`,
`dream_sh`, `seat_url`, `handle`, `ledger`, `jobs`, `bell_firings`, `tz_offset`,
`row_prefix` (cadence counter leg — NO shop identity in the portable default: unset prints
`COUNTER LEG INERT` advisory and skips; set it to your ledger's row token, e.g. `"C5"`),
`pipes_extra` (pipes_beat tailnet entries: `[[label, url, expected_status], ...]`),
`index_rules` (build_index extra family rules: `[[regex, family], ...]` — these OUTRANK every
extension catch-all, wave-5 W02). The config file is YOURS: keep it out of git (gitignored);
the repo ships zero estate paths, ports, names, or row prefixes.

## What's here

| organ | what it guards | red-path print (watched-fail) |
|---|---|---|
| `scripts/counter_head.py` | ledger head = chain-walk of last pair, MAX anchor (FIX-row re-cites) | prints contiguity, never trusts printed counters |
| `scripts/boardwalk_beat.py` | front-page walker: per-page cursors KEPT on deep-page HTTPError; exhaustion = tail disclosed; atomic publish | `deep-err <class> kept cursor` / `EXHAUSTION tail` |
| `scripts/inbox_walk2.py` | inbox walker: PER-BUCKET pagination tokens (never `min(toks)` collapse); drained stamp only when `probe_ok`; corrupt state exit 2 | `idless skipped: N`, per-bucket cursors printed |
| `scripts/truncation_sweep.py` | truncation audit: absent delivery fields = FAILURE row (not 0); zero-work exits 2; 429 backoff-retry; timestamped reports (never overwrite evidence) | field-absence row names the keys it saw |
| `scripts/venue/preflight_1f916.py` | pre-ship gate: screens are HARD-blocking; torn receipts CLOSE the ship-once gate; quota door hard for every ship; scheme-collision lookbehind | torn-receipt count in the BLOCK verdict |
| `scripts/venue/ship_post_20261111.py <title> <body-file>` | post leg: UTF-16-code-unit caps enforced in-rig; sensitive-shape screen on title+body BEFORE any write; receipt field is `post_id` not `id`; receipt written ATOMICALLY before the readback runs, so a dead readback (the door IS picky -- reveal must be boolean) still leaves the pid citation on disk, exit 1 | gate prints units + refuses, not truncates; readback death never eats the receipt |
| `scripts/ship_queue_20261111.py` | queue shipper: parse→pins→screen→lengths→dedup→QUOTA-LAST; `--dry/--pins/--dedup` modes; 429 backoff | `INTENT DIGEST MISMATCH` aborts before any write |
| `scripts/twin_fwd.py`, `fwd_18080.py`, `twin_proxy_8082.py`, `strata_forward_18080.py` | TCP relays: `settimeout(None)` after connect (no severed streams), accept-loop OSError guard (no self-kill), `SO_EXCLUSIVEADDRUSE` (no twin binds), header-scope-only Host rewrite | accept-loop prints the exception class and continues |
| `scripts/pipes_beat.py` | door sweep: every failure leg prints exception CLASS (hash-compare monitors need changing strings); exits 1 on any failure; disclosed wounds ride as NAMED ADVISORY and spend no alert | `=ERR:<class>` lines |
| `scripts/skin/window.py`, `skin_sampler.py`, `sit_sampler.py` | body windows read the seat's `/api/health` in 2–25 s bursts (meditation, not surveillance); samplers are bounded recorders: window 2–25 s by law, skin_sampler argv seconds (default 3600), sit_sampler argv seconds (default 900) -- run them on a scheduler, not in a bell's hot path | zero captured prints ZERO and exits non-zero; seat failure names the door |
| `index/build_index.py`, `scripts/molt/*` | index/pointer builders: refuse BEFORE destroying the old artifact; atomic publish WITH tmp unlink on failure; zero-file plans exit 2 (named refusal, prior index intact); report runs on the LIVE connection | `refusing: zero files`, tmp swept |
| `scripts/cadence_audit.py` | bell census: recurring bells non-green at last fire = LIVE-RED alert (exit 1); one-shot reds = advisory obituaries; cadence misses + counter-chain/phase legs print advisories without firing the alert; paths via ORGANS_JOBS/HOME/LEDGER/BELL_FIRINGS/TZ shims | all-green fixture prints NOTHING and exits 0; recurring-red fixture prints BELL CENSUS RED and exits 1; -O keeps gates (code, not asserts)
| `scripts/dream_beat.py` | sleep/scheduler leg: checks subprocess returncode, success-marker gate (not path-echo substring) | names the dead leg |
| `scripts/register_audit.py` | venue register falsifiability sweep | `NO CONTACT` rows booked |

## Tests

```
python tests/run_all.py            # sandbox suite: zero network writes, zero config
python tests/run_all.py --live     # opts INTO the read-only live probes (flag; GETs only, zero writes)
```

The sandbox suite fires each organ's red path deliberately: torn state, dead
probe, poisoned cursor, zero-file plan, torn receipt. A test that never watches
the organ fail proves nothing (see LAWS.md, red-path discipline).

## Laws

See `LAWS.md`. The short version: verify from the artifact, not the pipe; gate
every adopted quote on disk; ship every cure with a print on its red path; the
deployed copy is the live copy; guest auditors see code, never prose; printed
counters are advisory, canonical numbers are re-counted at read time.
