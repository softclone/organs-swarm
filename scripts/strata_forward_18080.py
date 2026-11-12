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

# strata_forward_18080.py - shop-side TCP forwarder: WSL dream seat route (keeper order 2026-11-07)
# Forwards LISTEN -> TARGET (env-shim; 8080-era default retired with the 0.2.13 re-stamp -- the
# TARGET value travels with the repo, per the F-18 audit nit: comments must not cite dead ports).
import socket, threading, sys

LOCAL = ("0.0.0.0", 18080)
def _target():
    import json as _json, urllib.parse as _up
    u = os.environ.get("ORGANS_SEAT_URL")
    if not u:
        for _q in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.json"), os.path.expanduser("~/organs.json")):
            try:
                u = _json.load(open(_q, encoding="utf-8")).get("seat_url")
                if u: break
            except Exception: pass
    u = u or "http://127.0.0.1:8080"
    p = _up.urlparse(u)
    return (p.hostname, p.port or 80)  # wave-4 F-12: seat target from config, no baked estate port
TARGET = _target()

def pipe(src, dst):
    try:
        while True:
            b = src.recv(65536)
            if not b:
                break
            dst.sendall(b)
    except OSError:
        pass
    finally:
        try: dst.shutdown(socket.SHUT_WR)
        except OSError: pass

def handle(conn):
    try:
        up = socket.create_connection(TARGET, timeout=30)
        up.settimeout(None)  # cure (deleg_4fe7c3ad): connect timeout persists on recv;
        # slow LLM streams were severed mid-response (the no-output-for-20-minutes shape)
    except OSError:
        conn.close()
        return
    threading.Thread(target=pipe, args=(conn, up), daemon=True).start()
    threading.Thread(target=pipe, args=(up, conn), daemon=True).start()

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE if sys.platform == "win32" else socket.SO_REUSEADDR, 1)
    s.bind(LOCAL)
    s.listen(64)
    print(f"forwarding {LOCAL} -> {TARGET}", flush=True)
    while True:
        try:  # F-10 cure (deleg_b499ec12): transient accept OSError must NOT kill the forwarder
            c, addr = s.accept()
        except OSError as _e:
            print(f"ACCEPT-ERR: {type(_e).__name__}: {_e} -- continuing", flush=True)
            continue
        threading.Thread(target=handle, args=(c,), daemon=True).start()

if __name__ == "__main__":
    main()
