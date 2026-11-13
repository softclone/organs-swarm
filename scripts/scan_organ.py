"""Canonical scan organ — copy this definition into ship/admission calls, never retype from memory (erosion pass 55 law: scan organs copy from canonical definition in same call family).

Usage:
    import sys; sys.path.insert(0, <dir containing scan_organ.py>)
    from scan_organ import gate
    hits = gate(text)          # returns [] on clean prose
    if hits: raise SystemExit("GATE: " + str(hits))   # gate BEFORE any upload (pass 119 law)

Scope laws baked in:
- Secrets gate on UNION of raw + stripped surfaces (privacy).
- Estimate-shape gates on STRIPPED surface only (quoted specimens are evidence, firing #170).
- Nonlatin net admits: Latin-1 accents in proper names, typographic symbols (en/em dash, curly quotes, arrows, math symbols incl. U+2212 minus), native-script proper-name citations (erosion pass 67 scope amendment).
"""
import re

# 30+ runs must contain a digit (amended 2026-10-21 per agency-agents scan datum):
# long all-letter runs are identifiers (FGameplayEffectModCallbackData fired SECRET x4 on
# Unreal class names); real base64/hex tokens carry digits. Hex runs get HASH64 exemption upstream.
SECRET_PATTERNS = [r'(?=[A-Za-z0-9]*[0-9])[A-Za-z0-9]{30,}', r'\bBearer\s+[A-Za-z0-9_\-\.\+/=]{20,}', r'\bsk-[A-Za-z0-9]']
# chr(66)+chr(101)+chr(97)+chr(114)+chr(101)+chr(114)+chr(32)tightening 2026-10-20T23:24Z (scan-scope datum): prose documentation ABOUT the shape
# ("chr(66)+chr(101)+chr(97)+chr(114)+chr(101)+chr(114)+chr(32)header", "chr(66)+chr(101)+chr(97)+chr(114)+chr(101)+chr(114)+chr(32)scheme") fired the old {1,} pattern. Real tokens measured 57/73 chars;
# the floor is 20 - prose words never reach it, tokens always do.
ESTIMATE_PATTERNS = [r'~\d', r'(?<![\d:])\d{1,2}:\d{1,2}x']  # second pattern: estimate-shape only; lookbehind added 2026-10-18 (fires on real timestamps followed by 'x', e.g. "Ship-1029 landed at 02:32" + "xZ")
# Prose-scar net (erosion pass 182, 2026-10-19): composition scars pass every numeric organ.
# Self-interruptions ('... correction', '… correction —') and placeholder stamps ('NN:MMxZ' caught by EST;
# 'TBD', 'XXX', 'TODO') are composition scars, not artifacts. A shipped row must read as the reader sees it.
# Timestamp-placeholder scar added 2026-10-19T03:53:20Z (GOAL.md edit-log firing): named as a SCAR class
# so reports label it as a scar, not an estimate.
SCAR_PATTERNS = [r'(\.\.\.|…)\s*correction', r'\bTBD\b', r'\bTODO\b', r'\bXXX\b', r'\d{1,2}:\d{1,2}xZ',
    r'\?\s*(No|no|Wait|wait)\s*[\u2014-]',  # author self-interruption (pass-182 class)
    r'(\.\.\.|…)\s*\(',  # dangling reference: ellipsis before parenthetical (LAWS pass-185 firing)
]

# Admitted non-ASCII: typographic + Latin-1 letters + arrows/delta/math symbols.
ADMITTED_NONASCII = (
    '\u2013\u2014'            # en/em dash
    '\u2018\u2019\u201c\u201d'  # curly quotes
    '\u00C0-\u024F'           # Latin-1/Latin Extended letters (proper names)
    '\u2192\u2190\u2194\u0394'  # arrows, delta
    '\u2212\u00D7\u00F7\u00B1'  # minus, times, divide, plus-minus
    '\u2264\u2265\u2260\u2248\u221A'  # le, ge, ne, approx, sqrt (ne added 2026-10-17 per pass-67 typographic-scope clause)
    '\u220E\u221E\u222B\u2208\u2209\u2282\u2283\u222A\u2229'  # QED, infinity, integral, element-of/not, subset, union, intersect (added 2026-10-18 per pass-67 math-typographic clause)
)

def smart_apos(text: str) -> str:
    """Mechanism fix for the UNPAIRED-QUOTE net (armed 2026-10-22, pass-255 window).
    The strip regex pairs ASCII apostrophes; English possessives/contractions (shop's, don't)
    make the count odd and blind the strip to the tail. Letter-adjacent ASCII apostrophes are
    prose possessives: convert them to U+2019 (admitted non-ASCII, invisible to the strip).
    Quoted specimens keep their ASCII ' pairs untouched."""
    return re.sub(r"(?<=\w)'(?=\w)", "\u2019", text)

def gate(text: str):
    """Return list of gate hits; [] means clean. Gate the ship IN-CALL (pass 119)."""
    # strip replaces quoted spans with a SPACE, never empty string:
    # firing #156 family re-fire 2026-10-18 — unpaired apostrophe + empty-string strip
    # glued surviving words into a fake 30-char run (ScribeSirachTathagata...), manufacturing SECRET.
    text = smart_apos(text)  # possessive apostrophes -> U+2019 before any quote math (2026-10-22)
    stripped = re.sub(r'"[^"]*"', ' ', text)
    stripped = re.sub(r"'[^']*'", ' ', stripped)
    hits = []
    # Hash-exemption clause (added 2026-10-20T23:22Z per scan-scope datum): published SHA-256/SHA-1
    # integrity fingerprints (40/64-hex) are testimony receipts, not credentials. They are replaced
    # with a short token BEFORE the secrets net runs, so [A-Za-z0-9]{30,} cannot fire on them.
    text_x = re.sub(r'\b[0-9a-fA-F]{64}\b', 'HASH64', text)
    stripped_x = re.sub(r'\b[0-9a-fA-F]{64}\b', 'HASH64', stripped)
    for q in SECRET_PATTERNS:
        for surf in (text_x, stripped_x):      # secrets: UNION of raw + stripped (hash-exempted)
            if re.search(q, surf, re.I):
                hits.append("SECRET")
                break
    for q in ESTIMATE_PATTERNS:
        m = re.search(q, stripped)             # estimates: STRIPPED only (firing #170: quoted specimens exempt)
        if m:
            hits.append("EST:" + m.group(0))
    for q in SCAR_PATTERNS:                    # prose scars (pass 182): composition scars, STRIPPED surface
        m = re.search(q, stripped)
        if m:
            hits.append("SCAR:" + m.group(0)[:24])
    # Unpaired-quote detector (erosion pass 140, 2026-10-18): the strip swallows text between
    # quote boundaries; an ODD number of apostrophes means the strip ate prose up to a boundary
    # that does not exist — the estimate net goes blind to the swallowed region.
    # Specimen: "~280 years" inside a span eaten by "Kautilya's" — gate printed clean on prose
    # carrying a banned shape. When this fires, the author checks the swallowed region by hand.
    if text.count("'") % 2 == 1:
        hits.append("UNPAIRED-QUOTE: strip blind to tail; check estimates on raw surface by hand")
    net = '[^\x00-\x7F' + ADMITTED_NONASCII + ']'
    nl = re.findall(net, stripped)
    if nl:
        hits.append("NONLATIN:" + str(sorted(set(nl))[:6]))
    return hits

def dry_run():
    """Organ gets a dry-run on a known-clean string before it gates a ship (firing #156-family law)."""
    clean = ("The watts sit 5.07W above the mean (sum 8556.89 divided by 39 = 219.41W); "
             "René Descartes, \"丘濬\", \"王贞仪\" — arrows \u2192 and minus 260.06 \u2212 17.93 admitted. "
             "Math form: d \u2208 S, |d| = 14, \u221E rows between, proved \u220E")
    assert gate(clean) == [], "ORGAN LOOSE: dry-run fired on known-clean prose"
    dirty = "~157k and 12:3xZ and " + ("A"*40)
    assert len(gate(dirty)) >= 3, "ORGAN BLIND: dry-run missed planted defects"
    return True
