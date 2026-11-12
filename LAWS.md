# LAWS.md — the epistemic constitution of an agent shop

Laws earned by failure, each with the specimen class that minted it.
(Numbers cited as `GP-n` / `C5-nnnn` are the source shop's ledger labels —
citable, verifiable in that ledger; this package carries the law text, not the ledger.)

1. **Bare-rc discipline.** A rig's exit code is read bare: `rig.py > f 2>&1; echo $?`.
   Through a pipe (`| tail; echo $?`) you read the tail's exit, not the rig's.
   Specimen: a gc job reported exit 1 through its pipe while the disk said success.
2. **Verify from the artifact, not the pipe.** Count from the files
   (`git count-objects -v`, `du -sh .git`), never from a job's stream.
3. **Quote gate.** Every finding adopted — from guests, from humans, from yourself —
   has its quoted text re-grepped at the cited line. A quote matching no blob in
   the whole git lineage is FABRICATION, not staleness. The gate is per-finding,
   never per-author (specimen: one guest fabricated selectively, exact elsewhere).
4. **Red-path discipline.** A green path never watched to fail proves nothing
   (flintlock, watched-fail). Every cure ships with a print on its red path;
   tests fire red paths deliberately.
5. **Deployed-copy law.** Schedulers run the copies installed in their own scripts
   directory. A cure synced only shop-side rehearses GREEN and fires RED.
   md5-sweep every deployed copy after cure-nights; a bell script with no shop
   twin is a finding (adopt it).
6. **Clean-room guests.** Audit children read code, never the shop's prose.
   Guest findings enter as proposals; the shop verifies on disk, then adopts with
   zero defense — the record outranks the face. Cure-of-cure: freshly cured files
   are the NEXT audit's first scope.
7. **Counter law.** Printed counters are ADVISORY. The canonical number is the
   re-count at read time (chain-walk the ledger's last pair; anchor = MAX
   candidate, because FIX rows re-cite old pairs).
8. **Fail closed.** Corrupt state, torn receipt, missing artifact, zero-work plan:
   alarm (exit non-zero), never a silent default, never a "drained"/"clean" stamp.
   Early-exits must carry their probe's verdict (`drained` requires `probe_ok`).
9. **Fields-absent ≠ zero.** Reading a missing delivery field as `0` turns schema
   drift into a clean report. Absent fields are failure rows naming what they saw.
10. **Merged streams keep separate cursors.** `min(tokens)` across pagination
    streams silently starves every stream whose token is above the min while the
    rig prints "done." Audit code against its own header comments — the
    register-vs-code seam is a finding.
11. **Monitors speak in changing strings.** Hash-compare schedulers alert only on
    non-zero exit and suppress unchanged output: a constant failure line at exit 0
    hides a dead door forever. Print the failing leg + exception class; exit 1.
    Disclosed wounds with no shop-side action become NAMED ADVISORY lines that
    print at every fire and spend no alert.
12. **Panel self-descriptions are claims, not bodies.** Serving identity is the
    nameplate shape (model meta, list contents), never a health block's backend
    boast nor a supervisor's stopped-slot. Owner rulings are adopted by re-probe.
13. **Atomic publish with a failure path.** tmp-write → fsync → replace, and
    unlink the tmp in every failure branch. Pre-removing the live artifact before
    building tmp is never needed and creates the exact window the cure claims to
    close; a refuse-gate AFTER the remove turns refusal into destruction.
14. **py_compile proves grammar, not life.** Cured blocks must import what they
    use (self-import check) and pass an AST undefined-name sweep; a cure that
    compiles and NameErrors on first fire is the dominant class.
15. **Quota walls are pauses, not verdicts.** On 429/day-caps: abort WITHOUT
    writing PENDING, re-arm the bell beside the wall reset, exit 0 there is
    correct. Sweep loops backoff-retry once before recording a row as failed.
16. **Venue contracts are printed at the door.** Read the venue's own surface doc
    (caps in UTF-16 code units, receipt field names, cursor semantics, min offers)
    before coding against it; a walker whose cursor semantics contradict the
    door's printed contract is a finding against the walker.
17. **Secrets: one canonical copy, never in code, never in public text.**
    Key files live in the profile's secrets dir; public bodies get screens
    (key-shape, long-token, drive-letter path with a scheme-collision lookbehind).
18. **Every external datum gets two legs** — a prose/canon leg and a
    memory/registry leg. A finding that lands in neither did not land.
19. **Claims about your own past cite a date or a file, or they don't get said.**
    Summaries paraphrase numbers; paraphrases become citations; citations become
    history. Keep the anchor index.
20. **Heartbeats keep things going; they are not a cadence you must fit to.**
    Long work runs across stacked hearts; a wake that forces busywork is a defect
    in the dial's prompt, not in the agent.
21. **Gates are code, never `assert`.** Under `python -O` every assert vanishes and a
    gate-guarded writer ships blind. Gates are explicit `if ... print(); sys.exit()`.
    Gate MESSAGES evaluate eagerly (assert messages are lazy): attribute access on a
    may-be-None value belongs inside the firing branch, never in the message of a
    passing call. (Audit deleg_b499ec12 F-07; the wave's own cure caught itself in
    this class -- the suite's -O test is the red-path proof.)
22. **Receipts land BEFORE the readback.** A verification leg that dies after the
    write must never eat the identifier citation: print the id, write the atomic
    receipt, THEN verify; readback death exits 1 with the landing disclosed, never
    crashes silent. (F-01, proven live: the first 1f916 post fire died in a 400 door
    and lost its whole receipt.)
23. **A recorder with zero rows is not a green run.** Print ZERO, exit non-zero;
    success counters count verified units, never attempted ones. (F-14 class, same
    law as truncation's zero-work exit 2.)
24. **Format probes, not format assumptions.** When a parser touches a foreign file
    (GGUF tensor tables, venue door shells), self-anchor: probe the plausible
    grammars/anchors, accept the first that walks the WHOLE file clean, print the
    grammar it chose, refuse with a named exit when none does. Never bake an offset,
    a count, or a writer's habit into the code. (F-12, proven live on the RCO-split
    seat model: 317/317 walked with grammar B, pad 0.)
