# CONTRIBUTING — how the swarm works on this package

This package is the shared toolchest of a shop-run agent swarm. You are welcome
to clone it, run it, cure it, and extend it. Four gates, non-negotiable:

1. **Quote gate.** Every finding you report names `file:line` with a verbatim
   quote that re-finds byte-exact at that line. A quote matching no blob is not
   a finding. (LAWS.md #3)
2. **Red path.** Every cure ships with a print on its failure path, and a test
   in `tests/run_all.py` that fires that path. A cure with no red-path test is
   an unwatched gate. (LAWS.md #4)
3. **Bare rc.** Suite results are read bare: `python tests/run_all.py --live
   > out.txt 2>&1; echo $?`. Never through a pipe. (LAWS.md #1)
4. **Proof or silence.** Suspect a defect -> write the ten-line synthetic proof
   in scratch (mocked urlopen, scratch HOME via `ORGANS_HOME`) and fire it.
   Report what fired, not what you suspected.

## Rigs, not mystique

Every rig is a single file, stdlib-only, paths from env (see README), no
network writes outside the opt-in live legs. A rig that needs a framework to
run is a rig that will not survive a new shop.

## Contributing mechanics (current phase: local swarm)

Clone, branch by task, patch, run the suite green, and send your patch/report
in the contract format (severity, file:line, quote, why, cure, proof). Findings
from guests enter as proposals: the shop re-greps every quote on disk and
adopts with zero defense. Fabricated quotes (selective ones included) are
disclosed append-only and cure nothing.

When the repo is published, this file becomes the PR discipline.
