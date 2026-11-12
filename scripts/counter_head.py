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

# counter_head.py — canonical Counter head: STRICT CONSECUTIVE PAIRS + backward walk
# (catch #219 cure, 2026-11-11, third form after two self-caught false instruments):
# v1 forward-chain-from-min: broke at 11 (era gap pairs are not a single +1 chain).
# v2 max-to-value: 16058 -- POISONED by the old era's arrow-form stamps inside row bodies.
# v3 (this file): canonical = pairs of the exact form N->N+1 only (the mint print grammar;
# old-era arrows like 16057->16058 ARE consecutive too, so v3 walks the LONGEST BACKWARD
# CHAIN from the highest v3-candidate and reports ALL surviving chain tails; the LIVE head
# = the chain-tail containing the LAST row's own pair print (rows carry their mint note in
# file order; the newest row's canonical pair anchors the live chain). Disclosed old pairs
# ride inside newer rows' bodies -> they are chain members of OLD chains, not the live one.
import re
_led = os.path.join(HOME, "ledgers/CORPUS.md")
if not os.path.exists(_led):
    print(f"COUNTER-HEAD: no ledger at {_led} -- reader advisory, exit 2 (wave-7 F18 cure: unguarded open printed a Traceback)")
    raise SystemExit(2)
txt = open(_led, encoding="utf-8").read()
rows = txt.splitlines()
pairs = [(int(a), int(b)) for a, b in re.findall(r"Counter (\d+)->(\d+)", txt)]
strict = {(a, b) for a, b in pairs if b == a + 1}
tos = {b for a, b in strict}
froms = {a for a, b in strict}
# last canonical pair printed by any row (file order = mint order; FIX/restatement rows re-cite)
last_pair = None
for line in reversed(rows):
    ms = re.findall(r"Counter (\d+)->(\d+)", line)
    cands = [(int(a), int(b)) for a, b in ms if int(b) == int(a) + 1]
    if cands:
        # Cure wave 2 (C5-16492, guest): intra-row order is not authority -- a FIX row may
        # re-cite an old pair AFTER its own head pair. Anchor on the HIGHEST candidate of
        # the last pair-bearing row, not its last-listed pair.
        last_pair = max(cands, key=lambda x: x[1])
        break
if not last_pair:
    print("no canonical pair on disk"); raise SystemExit(1)
head = last_pair[1]
# wave-7 F9 cure: contiguity walks PAIRS (a,b in strict with b==a+1), not global
# froms/tos membership -- scattered pairs welded a false 'contiguous' verdict.
contig = all((head - k - 1, head - k) in strict for k in range(5))
# Cure wave 2 (C5-16492): count ROWS printing the head pair, not whole-text occurrences
prints = sum(1 for line in rows if re.search(rf"Counter {head - 1}->{head}(?!\d)", line))
naive = pairs[-1][1]
all_tos = sorted(tos)
print(f"live head (last row canonical pair): {head} | tail-chain contiguous(5 back): {contig} | head-pair printed by {prints} row(s)"
      + ("  <-- same-pair race: earliest printer OWNS, disclose later" if prints > 1 else ""))
print(f"naive last-pair: {naive} | max any-pair to: {max(tos)} (old-era arrows ride disclosed inside newer rows -- not the live chain)")
