#!/usr/bin/env python3
# cage_probe — distill of the _cagemap* family (12 copies, comparative cage battery draws).
# verbs: probe --prompt FILE [--draw NAME] [--out DIR]  -> one seat draw, raw dump keep-first.
# Family habits cured IN CODE (not comments):
#   1. max_tokens floor 131072 — the family rode 2000; probe() clamps every budget up.
#   2. bare-base seat_url (empty path) gets /v1/chat/completions appended (_door).
#   3. named refusals rc2 BEFORE any door call: verb, args, prompt file, config chain.
#   4. door non-JSON / choices-less shells land as {ok:false, door_shell:...} in the raw
#      record — never a crash; HTTPError -> {ok:false, http, body[:600]}; other
#      exceptions -> {ok:false, error: "Type: msg"}.
#   5. keep-first raw file via O_EXCL: collision = named refusal, first copy intact.
# Config chain: ORGANS_SEAT_URL env > local.json beside rig > ORGANS_HOME/organs.json
#   > ~/organs.json (first file with a seat_url wins; unreadable/corrupt files skipped).
# Seat model: ORGANS_SEAT_MODEL env > seat_model config > portable default 'local-seat'.
# No secrets ride this organ: the seat door is unauthenticated; config is never
# printed wholesale (only the seat URL rides the raw record).
import json, os, sys, time, urllib.request, urllib.error
from urllib.parse import urlsplit, urlunsplit

MAXTOK_FLOOR = 131072

def _cfg():
    env_url = os.environ.get("ORGANS_SEAT_URL", "")
    if env_url:
        return {"seat_url": env_url,
                "seat_model": os.environ.get("ORGANS_SEAT_MODEL") or "local-seat"}
    here = os.path.dirname(os.path.abspath(__file__))
    for d in (here, os.environ.get("ORGANS_HOME", ""), os.path.expanduser("~")):
        if not d:
            continue
        p = os.path.join(d, "local.json" if d == here else "organs.json")
        try:
            with open(p, encoding="utf-8") as f:
                c = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(c, dict) and c.get("seat_url"):
            if os.environ.get("ORGANS_SEAT_MODEL"):
                c["seat_model"] = os.environ["ORGANS_SEAT_MODEL"]
            return c
    print("REFUSE: no seat_url in config chain (rc2)")
    raise SystemExit(2)

def _door(base):
    u = urlsplit(base)
    if u.path in ("", "/"):
        u = u._replace(path="/v1/chat/completions")
    return urlunsplit(u)

def probe(prompt_text, cfg, maxtok=None, model=None):
    mt = max(int(maxtok or MAXTOK_FLOOR), MAXTOK_FLOOR)  # keeper floor: never below
    body = json.dumps({"model": model or cfg.get("seat_model") or "local-seat",
                       "max_tokens": mt, "temperature": 0.9,
                       "messages": [{"role": "user", "content": prompt_text}]}).encode("utf-8")
    req = urllib.request.Request(_door(cfg["seat_url"]), data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=180)
        raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try:
            excerpt = e.read().decode("utf-8", "replace")[:600]
        except Exception:
            excerpt = ""
        return {"ok": False, "http": e.code, "body": excerpt}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    try:
        d = json.loads(raw)
        text = d["choices"][0]["message"]["content"]
        if not isinstance(text, str):
            raise KeyError("content not text")
        return {"ok": True, "text": text, "model": d.get("model")}
    except (KeyError, IndexError, TypeError, ValueError):
        return {"ok": False, "door_shell": raw[:600]}

def main(argv):
    if len(argv) < 2 or argv[1] != "probe":
        print("REFUSE: verb probe required (rc2)")
        return 2
    args = argv[2:]
    prompt_file, draw, out_dir = None, "draw", None
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--prompt", "--draw", "--out"):
            if i + 1 >= len(args):
                print(f"REFUSE: {a} without value (rc2)"); return 2
            if a == "--prompt": prompt_file = args[i + 1]
            elif a == "--draw": draw = args[i + 1]
            else: out_dir = args[i + 1]
            i += 2
        else:
            print(f"REFUSE: unknown arg {a} (rc2)"); return 2
    if not prompt_file or not os.path.isfile(prompt_file):
        print("REFUSE: --prompt FILE required and must exist (rc2)"); return 2
    try:
        with open(prompt_file, encoding="utf-8") as f:
            prompt_text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"REFUSE: prompt unreadable {type(e).__name__} (rc2)"); return 2
    cfg = _cfg()
    t0 = time.time()
    res = probe(prompt_text, cfg)
    out_dir = out_dir or os.path.join(os.path.dirname(os.path.abspath(prompt_file)), "census")
    os.makedirs(out_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    raw_path = os.path.join(out_dir, f"cageprobe-{draw}-{stamp}.json")
    rec = {"draw": draw, "stamp": stamp, "elapsed_s": round(time.time() - t0, 2),
           "seat": cfg["seat_url"], "maxtok_floor": MAXTOK_FLOOR, "result": res}
    try:
        fd = os.open(raw_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        print(f"REFUSE: keep-first collision {raw_path} -- first copy intact (rc2)")
        return 2
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print(f"draw={draw} ok={res.get('ok')} stamp={stamp} raw={raw_path}")
    if res.get("ok"):
        print("TEXT:", res["text"][:300])
    return 0 if res.get("ok") else 3

if __name__ == "__main__":
    sys.exit(main(sys.argv))
