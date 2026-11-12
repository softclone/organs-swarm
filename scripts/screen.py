# Single source of truth for the venue body screens (wave-6 W6-04/05/20 cures, deleg_5185ca9e).
# ship_queue_20261111, ship_post_20261111 and preflight_1f916 import THIS module: one grammar, no drift.
# Grammar note (W6-20): the bare word 'secret' IS screened (leading word-boundary, over-block direction).
# The consented way out for a false positive is a named hygiene disclosure on the record -- never a grammar loosening.
# Escape law (CATCH 239): this file's patterns are proof-fired in-suite; control-byte scan green.
import re
BAD = re.compile(r"(?:\b(?:api[_-]?key|secret|resident_key)\b|\bbearer\s|\b[A-Za-z0-9+/_=-]{40,}\b)", re.I)
SCREENS = [
    ("keyword", BAD),
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("ipv4", re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
    ("home-path", re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/][\w/. -]{4,}|/c/Users/[\w-]+/", re.I)),
    ("bearer-secret", re.compile(r"(Bearer\s+[A-Za-z0-9_\-]{12,})|sk-[A-Za-z0-9]{16,}")),
    ("long-token", re.compile(r"\b[A-Za-z0-9+/_=-]{40,}\b")),
    ("invisible-unicode", re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff]")),
    ("ansi", re.compile(r"\x1b\[")),
]
