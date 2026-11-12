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
p = r"C:\models\Qwen\Qwen3-235B-A22B-Thinking-2507-GGUF\Qwen3-235B-A22B-Thinking-2507-Q3_K_L-00001-of-00003.gguf"
NAMES={0:"F32",1:"F16",2:"Q4_0",3:"Q4_1",6:"Q5_0",7:"Q5_1",8:"Q8_0",10:"Q2_K",11:"Q3_K",12:"Q4_K",13:"Q5_K",14:"Q6_K",16:"IQ2_XXS",17:"IQ2_XS",18:"IQ3_XXS",19:"IQ1_S",20:"IQ4_NL",21:"IQ3_S",22:"IQ2_S",23:"IQ4_XS",29:"IQ1_M",30:"BF16",39:"IQ2_S(39)",43:"MXFP4"}
def nm(t): return NAMES.get(t,"TYPE"+str(t))
f=open(p,"rb")
types=Counter(); samples=[]; prev=-1; mono=True; bad=[]; parsed=0
pos=5933262
for i in range(1131):
    f.seek(pos)
    l=struct.unpack("<I",f.read(4))[0]
    if not 4<=l<=80: bad.append((i,"len",l,pos)); break
    name=f.read(l).decode("ascii",errors="replace")
    nd=struct.unpack("<I",f.read(4))[0]
    ty=struct.unpack("<I",f.read(4))[0]
    off=struct.unpack("<Q",f.read(8))[0]
    dims=[struct.unpack("<I",f.read(4))[0] for _ in range(nd)]
    if not(1<=nd<=5 and ty<64 and all(0<d<10_000_000 for d in dims)):
        bad.append((i,"shape",nd,ty,dims,pos,name)); break
    if off<prev: mono=False
    prev=max(prev,off)
    types[ty]+=1
    if i<14: samples.append((name,dims[:3],nm(ty)))
    nxt = 5933262 + (((pos-5933262) + (4+l+4+4+8+4*nd) + 7)//8)*8  # F14 cure (C5-16486): round-UP needs +7; +1 rounded DOWN on 48/64 residues -> seek into previous record (alignment assumption 8; verify vs general.alignment before trusting)
    if nxt<=pos: bad.append((i,"no-advance",pos,nxt)); break
    pos=nxt
    parsed+=1  # N5 cure (C5-16484): full-tensor success counter; i+1 counted the FAILED tensor as parsed
f.close()
print("parsed:",parsed,"of 1131 | stop:",bad[:1],"| offsets monotonic:",mono,"| end:",pos)
print("tensor ggml-type histogram:")
for t,c in sorted(types.items()): print("  ",nm(t),":",c)
for s in samples: print(" sample:",s[0],s[1],s[2])
sys.exit(1 if bad else 0)  # N5 cure: a bad stop is not a clean parse
