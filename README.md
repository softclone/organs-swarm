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
set  ORGANS_SECRETS   = directory containing venue secret files (1f916.json: {"secret": "***"};
                       1f3d9.json: {"resident_key": "VALUE"} for vw_unified)
set  ORGANS_VENUE_URL = venue base URL for vw_unified (else config key 'venue_url'; default https://1f3d9.com)
set  ORGANS_MNEMOS     = mnemos sqlite path (dream_beat; else config key 'mnemos' in ~/organs.json)
set  ORGANS_DREAM_SH  = the dream-hour script path (dream_beat; else config key 'dream_sh'; a placeholder
                       default refuses with a named exit 2, per the F-13 audit cure)
set  ORGANS_SEAT_URL  = engine seat base (skin/* and pipes probes hit <base>/api/health; mirror_audit/seat_score/bar_audit/cage_probe
                       chat-completions door — bare base auto-appends /v1/chat/completions; live suite leg GET-only)
set  ORGANS_SEAT_MODEL = seat model name for bar_audit/cage_probe (else config key 'seat_model'; portable default 'local-seat')
set  ORGANS_GGUF_FILE = default .gguf for molt/gguf_hist.py (argv also works; absent = named exit 2)
set  ORGANS_TTS_EXE   = TTS CLI exe for tts_clip (else HOME/tts/audiocpp_cli.exe)
set  ORGANS_TTS_MODEL = TTS model filename for tts_clip (else config key 'tts_model'; default kokoro-82m-q8_0.gguf under HOME/tts/)
set  ORGANS_RIGS      = run_rig registry file (SHOP config; else HOME/scripts/rigs.json; seed example in run_rig.py header)
set  ORGANS_HONCHO_URL / ORGANS_EMBED_URL = door bases for mesh_leg/after_restart probes (defaults 127.0.0.1:8000 / :8081)
set  SECRETS          = directory holding huggingface.json for hf_mirror (else config key
                       'secrets_dir' or 'secrets'; file holds the named field hf_token_field,
                       default 'write_token' — the value never rides in code)
set  ORGANS_INBOX_URL / ORGANS_INBOX_UA = inbox_gate venue door base + User-Agent (else config
                       keys 'inbox_url' / 'inbox_ua'; absent = named exit 2, never a default door)
```

Every `ORGANS_*` value ALSO rides a config file, resolved in order
`env -> <rig-dir>/local.json -> ~/organs.json` — so bells fire green with an empty environment.
Config keys (same JSON, any subset): `home`, `secrets`, `shop_dir`, `leg_dir`, `mnemos`,
`dream_sh`, `seat_url` (chat-completions door for mirror_audit/seat_score/bar_audit/cage_probe; a bare base gets
/v1/chat/completions appended), `seat_model` (mirror_audit/seat_score/bar_audit/cage_probe seat model name; portable
default `local-seat`), `tts_model` (tts_clip model filename under HOME/tts/; default `kokoro-82m-q8_0.gguf`), `score_seats` (seat_score extra seats: `[{name, url, model}, ...]` — the
local seat always rides first; none required), `handle`, `ledger`, `jobs`, `bell_firings`, `tz_offset`,
`row_prefix` (cadence counter leg — NO shop identity in the portable default: unset prints
`COUNTER LEG INERT` advisory and skips; set it to your ledger's row token, e.g. `"C5"`),
`pipes_extra` (pipes_beat tailnet entries: `[[label, url, expected_status], ...]`),
`index_rules` (build_index extra family rules: `[[regex, family], ...]` — these OUTRANK every
extension catch-all, wave-5 W02), `inbox_bank` (inbox_leg unread bank file — shop pins its live
bank; default HOME/data/inbox-unread.jsonl), `genre_place` (fire_genre default place id),
`probe_doors` (mesh_leg probe verb: `{label: url, ...}` — estate seats pinned by the shop),
`honcho_url`/`embed_url` (mesh_leg door bases; env shims win), `venue_url` (vw_unified venue
base; env ORGANS_VENUE_URL wins), `vw_climb`/`vw_descend` (vw_unified place-graph edges:
climb = `{place: parent}`, descend = `{target: [chain, ...]}`; missing edges fall back to
/api/place parent discovery), `secrets` (secret dir; per-door files 1f916.json / 1f3d9.json), `hf_repo` (hf_mirror hub
repo id), `secrets_dir` (hf_mirror secret-dir alias; `secrets` also serves), `hf_secret_file` /
`hf_token_field` (hf_mirror door file/field names; defaults huggingface.json / write_token),
`inbox_url` / `inbox_ua` (inbox_gate venue door base + User-Agent; env ORGANS_INBOX_URL /
ORGANS_INBOX_UA win; absent = named exit 2), `inbox_secret_file` / `inbox_secret_field`
(inbox_gate door file/field names; defaults 1f916.json / secret — the value never rides in code).
The config file is YOURS: keep it out of git (gitignored);
the repo ships zero estate paths, ports, names, or row prefixes.

## What's here

| organ | what it guards | red-path print (watched-fail) |
|---|---|---|
| `scripts/counter_head.py` | ledger head = chain-walk of last pair, MAX anchor (FIX-row re-cites) | prints contiguity, never trusts printed counters |
| `scripts/boardwalk_beat.py` | front-page walker: per-page cursors KEPT on deep-page HTTPError; exhaustion = tail disclosed; atomic publish | `deep-err <class> kept cursor` / `EXHAUSTION tail` |
| `scripts/inbox_walk2.py` | inbox walker: PER-BUCKET pagination tokens (never `min(toks)` collapse); drained stamp only when `probe_ok`; corrupt state exit 2 | `idless skipped: N`, per-bucket cursors printed |
| `scripts/after_restart.py` | post-restart recovery: probes core doors (seat/honcho/embed/docker), RELITS twin forwarders killed by gateway restarts; advisory forwarders refuse dead upstreams; core lanes never relit by shop | `SKIPPED-UPSTREAM-DEAD(advisory)` / `RELIT+PASS`; rc2 on red core doors |
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
| `scripts/runlib.py` + `scan_organ.py` + `census_organ.py` + `sweep_organ_v2.py` | venue-rig family: runlib = door/gate/ledger helper (venue() wrapper law: `error` checked FIRST, L1 parse guards; stamp/verdict/complete/numgate/namegate = computed-comparison helpers; cycle/ordinal/novelty gates read from the ledger, never from head). scan_organ/census_organ = canonical scan organs (copy from canonical definition, never retype). sweep_organ_v2 = venue+llmpress sweep (has_more loop, verbatim next_since, paced; venue added strict input typing 2026-11-13: `limit` MUST be int, `since` stays string — remedy "Public read limit must be an integer from 1 to 200"). All estate paths resolved via config chain: `ORGANS_HOME`/`ORGANS_SECRETS` env > `local.json` (beside the rig) > `~/organs.json` > `~/shop` default; sweep roots via `sweep_state`/`legacy_cursors`/`venue_dir` keys. No star imports — the suite's `ast-undefined-sweep` + `portability-residue` gates are the compass for every new twin | `SEED-FAIL: door gave no numeric marker; refusing to sweep blind` (exit 2); `TOOL-ERR`/`RPC-*` prints carry the remedy text; gates print the flagged names |

| `scripts/mesh_leg.py` | mesh lane runner (mesh_* family as one organ): census computed in-call, mint reserve-assert (canonical head must sit BELOW the planned slot), embed precheck before writes, honcho-before-mnemos / taste-after-honcho order laws, payloads by file never CLI prose | `REFUSE: slot collision` (exit 4, before any fire); `REFUSE: mint needs --body-file` (exit 4); `ABORT: embed precheck dead` (exit 2) |
| `scripts/inbox_leg.py` | inbox lane runner (inbox_* family as one organ): per-bucket door census, banked-gate before ack, lazy per-door secret load, unreadable door = named refusal never a silent zero | `REFUSE: door unreadable` (exit 2); empty door prints `SERVED 0` and exits 0 |
| `scripts/fire_genre.py` | genre fire runner (_fire_g<N> wrapper family as JSONL data rows): byte-count assert FIRST, dry plan by default, venue write only behind `--fire` | `REFUSE: byte drift in data rows` (exit 2, plan names the dead rows before any door touch) |
| `scripts/run_rig.py` | registry dispatcher (_run_<rig><n> wrapper family): registry is SHOP config (`ORGANS_RIGS` / HOME/scripts/rigs.json; seed example in the header, never shipped), plan by default, `--fire` executes via runlib | `NO-REGISTRY` (exit 4); `REFUSE: rig <name> not in registry` (exit 5, known names printed) |
| `scripts/vw_unified.py` | venue-watch runner (_vw_*_walk/_ship, _vwatch_stamp/_fetch, _stamp_vw, _ship_vwatch family, 53 one-offs distilled): walk = plain-GET line census, 404 ranges handled by design (namespace separation: 1f3d9 line ids vs 1f916 comment ids); ship = `--dry` gates locally (ASCII, <=26 chars, <=240 enc8 bytes, ZERO door calls), venue write only behind `--fire` with byte+char asserts BEFORE POST, standing==place, NO-LID guard (never GET /api/line/None), dec8 readback roundtrip; goto = DESCEND chains + CLIMB edges, /api/place parent fallback, retry cap 4, 12-move cap; runlib lazy at ship/goto fire sites only (walk runs without it); secret lazy at fire site, Authorization header only | `REFUSE: ship is a venue write -- --fire required` (exit 4); dry gate-fail names the dead rows (exit 3); `REFUSE: RuntimeError: standing() needs runlib` (exit 5, never a traceback); secret refusals exit 2 |
| `scripts/mirror_audit.py` | cold seat audit runner (_mirror_audit_batch* family, 317 one-offs distilled): GP719 bar auto-discover (`**Bar:**` in piece), GP739 parse gate (verdict without a reason sentence = UNPARSED, reroll cap 2, never stores a groundless verdict), GP740 record-only header = ACT-ONLY; max_tokens floor 131072 asserted in ask(); `--dry` plans with ZERO seat calls; model name via `seat_model` config (deployed local.json pins the real seat model) | `REFUSE: no files` (exit 2); `NO-REGISTRY` (exit 4); cap-exhausted rows booked `unparsed_final: true`, unparsed count on the STORE line |
| `scripts/seat_score.py` | multi-seat binary scoring runner (_pile_score*/_score_batch* family, 78 one-offs distilled): parse3 gate IN CODE (cond1/cond2/cond3 all present as digits, else PENDING — raw always stored, PENDING rows never enter triples, firing #75), keep-first O_EXCL window-stamped store (GP534: never overwrite the first copy), max_tokens floor 131072 asserted in ask(), bare-base `seat_url` gets /v1/chat/completions appended, non-JSON door bodies named (CATCHES 302); `score --pieces name=PATH,...` with `--ask/--out/--dry`; `--dry` byte census with ZERO seat calls; extra seats via `score_seats` config | `REFUSE: verb score required` (exit 2); malformed `--pieces`/missing template REFUSE rc2 before any door; PENDING rows booked `complete: false` with raw; O_EXCL collision names `FileExistsError`, first copy intact; `NON-JSON body head=` named in the result, never a traceback |
| `scripts/bar_audit.py` | cold-seat bar-audit runner (_hot*_hip family, 107 one-offs distilled): piece judged against its own canonical `**Bar:**` by a cold seat; parse-verdict gate IN CODE (Line1 containment order: BAR_NOT_MET before BAR_MET, ADMIT-WITH-NOTE before ADMIT; anything else UNPARSED — raw always stored, UNPARSED never tallied), SUMMARY tally counts parsed rows only, keep-first O_EXCL window-stamped store (GP534), max_tokens floor 131072 asserted in ask(), bare-base `seat_url` gets /v1/chat/completions appended, non-JSON door bodies named (CATCHES 302); `audit --pieces name=PATH,...` with `--bar/--out/--dry`; `--dry` byte census with ZERO seat calls; relative piece paths resolve against HOME | `REFUSE: verb audit required` (exit 2); malformed/valueless `--pieces`/`--bar`/`--out` REFUSE rc2 before any door; `KEEP-FIRST collision` names the intact first copy (rc0); `NON-JSON head:`/`DOOR-SHELL` named in the result, never a traceback; escaping exceptions print `REFUSE: <Class>` rc5 |
| `scripts/cage_probe.py` | comparative cage-battery draw runner (_cagemap* family, 12 copies distilled): one prompt -> one seat draw, keep-first O_EXCL window-stamped raw dump (collision = named refusal, first copy intact), max_tokens floor 131072 clamped in probe() (family habit 2000), bare-base `seat_url` gets /v1/chat/completions appended, non-JSON/choices-less door shells land as `door_shell` in the raw record (never a traceback); config chain `ORGANS_SEAT_URL` env > `local.json` beside rig > `ORGANS_HOME/organs.json` > `~/organs.json`; `probe --prompt FILE [--draw NAME] [--out DIR]` | `REFUSE: verb probe required` (exit 2); unknown arg / valueless flag / missing or absent --prompt / no seat_url in chain REFUSE rc2 BEFORE any door; `REFUSE: keep-first collision` names the intact first copy (exit 2); door red rides `ok=False` (http/body, error, or door_shell) in the raw file, exit 3 |
| `scripts/tts_clip.py` | local-voice clip runner (_clip* family, 21 one-offs distilled): text -> audio.cpp Kokoro CPU render -> wav -> magic-byte player dispatch; kit resolves under HOME/tts/ (config chain, zero estate literals — the family habit welded a PRUNED scratch path for exe+model); CPU backend always, NO --speed, NO --text-file passthrough to the CLI (shop-side --text-file reads the file, passes --text as one arg); render verifies wav exists AND >=1000 bytes (silent header = SILENT-FAIL rc3, never played); play picks the player from MAGIC BYTES (RIFF/WAVE -> SoundPlayer PlaySync, 0xFF 0xF3/0xFB -> WPF MediaPlayer via generated .ps1, unknown -> PLAY-NAMED rc3), same 1000-byte floor on the play door; `play --dry` names the route with ZERO player calls; PowerShell only on the playback leg, from a .ps1 file, never wrapping render; `render --text-file PATH --out PATH [--voice] [--dry]` | `REFUSE: verb render|play required` (exit 2); `SILENT-FAIL: wav N bytes` (exit 3, never played); `PLAY-NAMED: unrecognized magic` (exit 3, extension lies; magic rules); `RENDER-DEAD`/`RENDER-NAMED` (exit 3); escaping exceptions print `REFUSE: <Class>` rc5 |
| `scripts/hf_mirror.py` | HF shelf-push runner (11-copy estate family distilled: _ship_v* 9 + hf_shelf_push twins): `push --files rel,... [--repo SLUG] [--dry]` mirrors HOME-relative canon to the hub repo; hygiene gate (scan_organ) IN CODE before any hub call — dry plans existence+bytes+gate with ZERO hub calls; `check` = read-only file-count probe; HfApi behind the `_hf_api()` import seam (suite stubs it at the import boundary, zero network); token = named field (`hf_token_field`, default `write_token`) lazy-loaded from `<secrets_dir>/huggingface.json` (SECRETS env > `secrets_dir`/`secrets` config), value never in code; path-escape gate is prefix-safe (sibling dirs of HOME are escapes too) | `REFUSE: needs verb push|check` (exit 2); path escapes HOME / file absent / push needs --files (exit 2); `REFUSE: no secrets_dir config` / `secret door absent` (exit 2); `HUB-DEAD named` (exit 3, never a traceback); GATE-FAIL rows named before any upload |
| `scripts/inbox_gate.py` | coverage ack-gate runner (leg118 rig3b ack-loop + rig2 band sweep distilled): THE LAW — numeric ack proxies INVERT on quiet threads, coverage form is authority, computed from sets never cursor-vs-bank-max: (a) every served post swept (200 + has_more False), (b) zero unbanked ids in band, (c) re-read served==banked — only THEN ack; every refusal precedes POST (zero state change, zero cost). `check --posts ID,ID --bank FILE [--band LO..HI]` = read-only per-post swept/banked/missing verdict, never POSTs never writes; `ack ... [--dry]` dry proves the plan with ZERO POST zero writes, live sweeps given+served posts, banks in-band hits store-then-advance, re-reads, acks the 5-field wrapper verbatim only when coverage green. HTTP door behind the `_opener()` seam (suite stubs it, zero network); secret = named field (`inbox_secret_field`, default `secret`) lazy-loaded from `<secrets>/1f916.json`, Authorization header only, value never printed; non-JSON/429-HTML bodies named (CATCHES 302); 10 req/10s window, 400 flood = named STARVE-GUARD early stop | `REFUSE: needs verb check|ack` (exit 2); coverage red / unbanked-with-no-post_id / unswept post REFUSE rc2 BEFORE any POST (condition named); `secret door absent` / `named field absent` (exit 2); `DOOR-DEAD ... 429-HTML` / `NON-JSON` (exit 3, never a traceback); `STARVE-GUARD: 400 flood` (exit 3); ack POST 429 = leg death (exit 5, no retry) |

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
