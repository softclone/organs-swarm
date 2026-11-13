# after_restart.py -- post-restart recovery organ (minted 2026-11-13 C5-16799 family).
# Run after ANY gateway restart (or estate reboot): probes the door family, RE-LITS the
# shop-side twin forwarders that die with the gateway, and reports. Core doors (docker
# honcho stack, seat host, embed sidecar) are REPORT-ONLY -- keeper lanes, shop fires
# zero docker/gateway actions. Practice: wake-net-organ-ops references/after-restart-organ.
# Exit 0 = all green (after relit); 2 = red doors remain.
# Flags: --probe-only (never relit; hermetic/suite mode), --json (machine-readable table).
# Door URLs honor env overrides (ORGANS_SEAT_URL / ORGANS_HONCHO_URL / ORGANS_EMBED_URL)
# so suite fixtures can drive the identical probe route.
import sys, os, json, time, socket, subprocess, urllib.request
from datetime import datetime, timezone

def _seat_url():
    u = os.environ.get("ORGANS_SEAT_URL")
    if u: return u
    for q in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"),
              os.path.expanduser("~/organs.json")):
        try:
            u = json.load(open(q, encoding="utf-8")).get("seat_url")
            if u: return u
        except Exception: pass
    return "http://127.0.0.1:8080"

SEAT = os.environ.get("ORGANS_SEAT_URL") or _seat_url()
HONCHO = os.environ.get("ORGANS_HONCHO_URL", "http://127.0.0.1:8000")
EMBED = os.environ.get("ORGANS_EMBED_URL", "http://127.0.0.1:8081")
HERE = os.path.dirname(os.path.abspath(__file__))
def _cfg_home():
    if os.environ.get("ORGANS_HOME"):
        return os.environ["ORGANS_HOME"]
    for q in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"),
              os.path.expanduser("~/organs.json")):
        try:
            return json.load(open(q, encoding="utf-8"))["home"]
        except Exception:
            pass
    return os.path.expanduser("~/shop")
def _cfg_handle():
    for q in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"),
              os.path.expanduser("~/organs.json")):
        try:
            return json.load(open(q, encoding="utf-8")).get("handle") or "peer"
        except Exception:
            pass
    return "peer"
SHOP = _cfg_home()
HANDLE = _cfg_handle()
LOG = os.path.join(SHOP, "data", "after-restart.log")

def _twins_spec():
    # Default family: the two seat forwarders. The WSL-adapter bridge (:18082) is estate-specific:
    # its upstream is a NAT adapter IP that changes per boot, so it is declared in the config chain
    # (local.json / ~/organs.json key "after_restart_extra": [[port, script, [host, port], advisory?]]),
    # never baked in. Upstream-dead forwarders are SKIPPED, not relit (phantom-success guard).
    spec = [
        (8082, "twin_proxy_8082.py", False, None),
        (18080, "fwd_18080.py", False, None),
    ]
    for q in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"),
              os.path.expanduser("~/organs.json")):
        try:
            for e in json.load(open(q, encoding="utf-8")).get("after_restart_extra", []):
                spec.append((int(e[0]), e[1], bool(e[3]) if len(e) > 3 else True, tuple(e[2])))
            if any(os.path.exists(x) for x in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"),)):
                break
        except Exception:
            pass
    return spec

TWINS = _twins_spec()

def probe_get(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read(80)
    except Exception as e:
        return None, repr(e)[:60]

def probe_honcho(timeout=5):
    body = json.dumps({"query": "recovery probe", "filters": {"observer": "hermes", "observed": HANDLE}, "limit": 1}).encode()
    req = urllib.request.Request(HONCHO + "/v3/workspaces/hermes/conclusions/query", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, len(json.loads(r.read()))
    except Exception as e:
        return None, repr(e)[:60]

def port_open(port, timeout=0.4, host="127.0.0.1"):
    s = socket.socket(); s.settimeout(timeout)
    try:
        s.connect((host, port)); return True
    except Exception:
        return False
    finally:
        s.close()

def docker_count():
    try:
        out = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=20).stdout
        return len([l for l in out.splitlines() if l.strip()])
    except Exception:
        return -1

def relit(port, script, target=None):
    path = os.path.join(HERE, script)
    if not os.path.exists(path):
        return "NO-SCRIPT"
    if target is not None:  # advisory forwarders: refuse to relit against a dead upstream (phantom-success guard)
        if not port_open(target[0], target[1]):
            return "SKIPPED-UPSTREAM-DEAD(advisory)"
    d = os.path.join(SHOP, "data", "after-restart")
    os.makedirs(d, exist_ok=True)
    logf = open(os.path.join(d, script + ".relit.log"), "a", encoding="utf-8")
    flags = 0
    if os.name == "nt":
        flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([sys.executable, path], stdout=logf, stderr=logf, cwd=HERE, creationflags=flags)
    for _ in range(20):
        time.sleep(0.5)
        if port_open(port):
            return "RELIT"
    return "RELIT-NO-LISTEN"

def main():
    probe_only = "--probe-only" in sys.argv
    as_json = "--json" in sys.argv
    rows = []

    st, _ = probe_get(SEAT + "/v1/models")
    rows.append(("seat-direct", "core", "PASS" if st == 200 else f"RED({st})"))
    st, n = probe_honcho()
    rows.append(("honcho-:8000", "core", "PASS" if st == 200 else f"RED({n})"))
    st, _ = probe_get(EMBED + "/v1/models")
    rows.append(("embed-:8081", "core", "PASS" if st == 200 else f"RED({_})"))
    if os.environ.get("ORGANS_SKIP_DOCKER"):
        rows.append(("docker-stack", "core", "SKIP(env)"))
    else:
        dc = docker_count()
        rows.append(("docker-stack", "core", "PASS" if dc >= 5 else f"RED(count={dc})"))

    for port, script, advisory, upstream in TWINS:
        cls = "twin*" if advisory else "twin"
        if port_open(port):
            st, _ = probe_get(f"http://127.0.0.1:{port}/v1/models", timeout=6)
            s = "PASS" if st == 200 else ("LISTEN-PASSTHROUGH-RED(advisory)" if advisory else "LISTEN-PASSTHROUGH-RED")
            rows.append((f"twin-:{port}", cls, s))
        elif probe_only:
            rows.append((f"twin-:{port}", cls, "DOWN(probe-only)"))
        else:
            res = relit(port, script, target=upstream)
            if res.startswith("SKIPPED"):
                rows.append((f"twin-:{port}", cls, res))
                continue
            time.sleep(1.0)
            st, _ = probe_get(f"http://127.0.0.1:{port}/v1/models", timeout=6)
            if st == 200:
                s = f"{res}+PASS"
            elif port_open(port):
                s = f"{res}+LISTEN-PASSTHROUGH-RED(advisory)" if advisory else f"{res}+LISTEN-PASSTHROUGH-RED"
            else:
                s = res
            rows.append((f"twin-:{port}", cls, s))

    reds = [r for r in rows if "RED" in r[2] and "advisory" not in r[2]]
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = stamp + " after_restart: " + " ".join(f"{n}={s}" for n, c, s in rows) + f" reds={len(reds)}"
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    if as_json:
        print(json.dumps({"stamp": stamp, "rows": rows, "reds": len(reds)}))
    else:
        print("AFTER-RESTART CENSUS " + stamp)
        for n, c, s in rows:
            print(f"  {n:<18} {c:<5} {s}")
        print(f"  reds={len(reds)}  probe_only={probe_only}")
    print("AFTER-RESTART-DONE", flush=True)
    return 2 if reds else 0

if __name__ == "__main__":
    sys.exit(main())
