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

import struct
import sys
from collections import Counter
import sys, os
NAMES={0:"F32",1:"F16",2:"Q4_0",3:"Q4_1",6:"Q5_0",7:"Q5_1",8:"Q8_0",10:"Q2_K",11:"Q3_K",12:"Q4_K",13:"Q5_K",14:"Q6_K",16:"IQ2_XXS",17:"IQ2_XS",18:"IQ3_XXS",19:"IQ1_S",20:"IQ4_NL",21:"IQ3_S",22:"IQ2_S",23:"IQ4_XS",29:"IQ1_M",30:"BF16",39:"IQ2_S(39)",43:"MXFP4"}
def nm(t): return NAMES.get(t,"TYPE"+str(t))
# F-12 cure (deleg_b499ec12): the rig was a shop artifact wearing a portable repo badge -- the model
# path (C:\models\...), the data-section offset 5933262, and the tensor count 1131 were all baked to
# one file. Path now comes from argv/env (no default: absent = named exit 2). Header is PARSED from
# the file: GGUF v3 layout magic(4)+ver(4)+n_tensors(8)+n_kv(8)+KV-pairs; the tensor-info table
# starts at align(KV_end, general.alignment default 32). Count/offset now travel with the file.
p = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ORGANS_GGUF_FILE")
if not p:
    print("GGUF-UNCONFIGURED: pass a .gguf path as argv (or set ORGANS_GGUF_FILE) -- exit 2, this rig parses the file you point it at")
    sys.exit(2)
f = open(p, "rb")
_hdr = f.read(16)  # wave-7 F23 cure: header LENGTH gate before any unpack -- a 4-byte 'GGUF' file passed magic then died with struct.error
if len(_hdr) < 16:
    print(f"GGUF-HEADER-TRUNCATED: only {len(_hdr)} of 16 header bytes at {p} -- refusing (exit 2)"); sys.exit(2)
if _hdr[:4] != b"GGUF":  # wave-4 F-06: gate is CODE (assert side-effect vanishes under -O)
    print("NOT A GGUF (magic):", p); sys.exit(2)
_ver = struct.unpack("<I", _hdr[4:8])[0]
n_tensors = struct.unpack("<Q", _hdr[8:16])[0]
if n_tensors == 0:  # wave-4 F-14: a zero-tensor file is not a walk (law 23: zero work is not green)
    print("ZERO tensors in header: refusing (exit 2)"); sys.exit(2)
n_kv = struct.unpack("<Q", f.read(8))[0]
if _ver < 3:  # wave-4 F-06b: code gate, not assert
    print(f"GGUF version {_ver} < 3: KV grammar differs"); sys.exit(2)

def _rd_str():
    ln = struct.unpack("<Q", f.read(8))[0]
    return f.read(ln).decode("utf-8", errors="replace")
def _rd_val(t):
    _arr = ("u8", "i8", "u16", "i16", "u32", "i32", "f32", "bool", "string", "array", "u64", "i64", "f64")
    if t <= 6: f.read(1 if t in (0, 1) else (2 if t in (2, 3) else (4 if t in (4, 5, 6) else 0)))
    elif t == 7: f.read(1)
    elif t == 8: _rd_str()
    elif t == 9:
        et = struct.unpack("<I", f.read(4))[0]; cnt = struct.unpack("<Q", f.read(8))[0]
        for _ in range(cnt): _rd_val(et)
    elif t in (10, 11, 12): f.read(8)
    else: raise ValueError(f"unknown KV type {t}")
# walk the KV pairs capturing general.alignment (typed reads; arrays skipped via _rd_val)
f.seek(24)
alignment = 32
for _ in range(n_kv):
    k = _rd_str(); t = struct.unpack("<I", f.read(4))[0]
    val = None
    if t == 4: val = struct.unpack("<I", f.read(4))[0]
    elif t == 5: val = struct.unpack("<i", f.read(4))[0]
    elif t == 6: val = struct.unpack("<f", f.read(4))[0]
    elif t == 7: val = struct.unpack("<B", f.read(1))[0]
    elif t == 0: val = struct.unpack("<B", f.read(1))[0]
    elif t == 1: val = struct.unpack("<b", f.read(1))[0]
    elif t == 2: val = struct.unpack("<H", f.read(2))[0]
    elif t == 3: val = struct.unpack("<h", f.read(2))[0]
    elif t == 10: val = struct.unpack("<Q", f.read(8))[0]
    elif t == 11: val = struct.unpack("<q", f.read(8))[0]
    elif t == 12: val = struct.unpack("<d", f.read(8))[0]
    elif t == 8: _rd_str()
    elif t == 9:
        et = struct.unpack("<I", f.read(4))[0]; cnt = struct.unpack("<Q", f.read(8))[0]
        for _ in range(cnt): _rd_val(et)
    if k == "general.alignment" and isinstance(val, (int, float)):
        alignment = int(val)
_hdr_end = f.tell()

# SELF-ANCHORING walk (RCO proof-fire 2026-11-12, guest seat model (operator-supplied path) 
# split file): the tensor-info start is writer-dependent -- llama.cpp places it directly at KV
# end; RCO-split writers pad a few bytes; older tooling aligned it. Records are CONTIGUOUS (gguf
# spec: tensor info carries no per-record padding -- the old 8-byte stride was a Qwen-era fiction
# that only survived because that writer padded names). The rig probes: from KV end, try each
# offset in the first 4 KiB, walk ALL n_tensors records contiguously, accept the first anchor
# wave-4 F-15: alignment gate at PARSE time (was below the anchor walk: alignment 0 reached the
# walk's arithmetic and died as NO-ANCHOR rc1 before the gate could speak).
if not (1 <= alignment <= 1048576) or (alignment & (alignment - 1)):  # wave-4 F-15: alignment 0 ZeroDivision, 3 = nonsense; power-of-2 in range
    print(f"NONSENSE general.alignment={alignment}: refusing (exit 2)"); sys.exit(2)
# that walks clean. The data blob starts at align(end-of-table, alignment).
def _walk(anchor, grammar):
    # grammar A = llama.cpp gguf: name(u64len) nd(u32) ty(u32) off(u64) dims(u64 x nd)
    # grammar B = RCO split writer (proof-decoded 2026-11-12 on guest seat model byte-by-byte):
    #             name(u64len) nd(u32) dims(u64 x nd) ty(u64) off(u32)
    f.seek(anchor)
    prev = -1; mono = True; tys = []; infos = []
    def _rd(fmt):
        n = struct.calcsize(fmt)
        b = f.read(n)
        if len(b) < n: return None   # probe anchor ran into EOF -- this anchor is not the table
        return struct.unpack(fmt, b)[0]
    for i in range(n_tensors):
        l = _rd("<Q")
        if l is None or not 1 <= l <= 80: return None  # wave-4 F-07: 1-char tensor names are legal; 4 was writer habit
        name = f.read(l)
        if len(name) < l or not all(32 <= c < 127 for c in name): return None
        nd = _rd("<I")
        if nd is None or not (1 <= nd <= 5): return None
        if grammar == "A":
            ty = _rd("<I"); off = _rd("<Q")
            if ty is None or off is None or ty >= 64 or off >= 2**50: return None
            dims = [_rd("<Q") for _ in range(nd)]
        else:
            dims = [_rd("<Q") for _ in range(nd)]
            flags = _rd("<Q"); off = _rd("<I")
            # RCO/ik_llama imatrix writer packs the ggml type in a byte of the u64 field; the
            # byte position is per-record (proof-decode 2026-11-12 guest seat model: rec0 type 13
            # = Q5_K in the TOP byte, rec5 = token_embd type 21 = IQ4_XS in the LOW byte; the
            # remaining bits are quant-data/size metadata). Heuristic, disclosed: take the TOP byte
            # when it is a valid ggml type, else the LOW byte; refuse if neither is.
            if flags is None: return None
            t_hi, t_lo = flags >> 56, flags & 0xFF
            ty = t_hi if t_hi < 64 else (t_lo if t_lo < 64 else None)
            if ty is None or off is None: return None
        # dims gate: RCO writers put byte-sizes in embedding dims (per_layer_token_embd carries
        # dims[1]=320,001,536 on the guest seat model) -- bound is u32-range, not shop-sized 10M
        if any(d is None or not (0 < d < 2**32) for d in dims): return None
        if off < prev: mono = False
        prev = max(prev, off)
        tys.append(ty); infos.append((name.decode("ascii"), dims, off))
    return f.tell(), mono, tys, infos
anchor = None; res = None; grammar = None
for g in ("A", "B"):
    for delta in range(0, 4097):
        res = _walk(_hdr_end + delta, g)
        if res is not None:
            anchor = _hdr_end + delta; grammar = g
            break
    if anchor is not None:
        break
if anchor is None:
    print(f"NO-ANCHOR: no clean {n_tensors}-record walk in grammar A/B within 4096 of KV end {_hdr_end} -- exit 1 (table grammar unknown, not guessed)")
    sys.exit(1)
pos, mono, tys, infos = res
if not (1 <= alignment <= 1048576) or (alignment & (alignment - 1)):  # wave-4 F-15: alignment 0 ZeroDivision, 3 = nonsense; power-of-2 in range
    print(f"NONSENSE general.alignment={alignment}: refusing (exit 2)"); sys.exit(2)
data_start = (pos + alignment - 1) // alignment * alignment
print(f"header: n_tensors={n_tensors} n_kv={n_kv} alignment={alignment} table_start={anchor} (KV end {_hdr_end}, pad {anchor - _hdr_end}) grammar={grammar} data_start={data_start}")
types = Counter(tys)
samples = infos[:14]
parsed = len(infos)
f.close()
print(f"parsed: {parsed} of {n_tensors} | stop: [] | offsets monotonic: {mono} | end: {pos}")
print("tensor ggml-type histogram:")
for t, c in sorted(types.items()): print("  ", nm(t), ":", c)
for idx, s in enumerate(infos[:14]): print(" sample:", s[0], s[1][:3], nm(tys[idx]))
sys.exit(0)  # a full clean walk is the success bar; NO-ANCHOR above is the named failure
