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

# fwd_18080.py — dream forwarder twin (banked 2026-11-07 for gateway-restart survival)
# The session-launched forwarder (proc_15894bad7415) dies with the gateway. Relaunch:
#   terminal(background=true): python HOME/scripts/fwd_18080.py
# Purpose: WSL2 (dream organ) reaches the Windows strata seat bound to loopback only.
# 0.0.0.0:18080 -> 127.0.0.1:8080. Stdlib only.
import socket, threading, sys

LISTEN = ("0.0.0.0", 18080)
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
    if p.scheme == "https":  # wave-6 W6-18: the pipe is RAW TCP -- dialing 443 with plaintext is a handshake failure wearing a success hat. Plaintext-only is disclosed, not silent.
        print("FORWARDER-HTTPS-UNSAFE: this forwarder splices raw TCP; an https seat needs a TLS terminator, not a port swap -- refusing (exit 2) (wave-6 W6-18)")
        sys.exit(2)
    return (p.hostname, p.port or 80)  # wave-5 W14 (scheme default) + wave-6 W6-18 (https refused; explicit ports honored) (was scheme-blind 80)
TARGET = _target()

def pipe(a, b):
    try:
        while True:
            d = a.recv(65536)
            if not d:
                break
            b.sendall(d)
    except OSError:
        pass
    finally:
        try: b.shutdown(socket.SHUT_WR)
        except OSError: pass

def serve(conn):
    try:
        up = socket.create_connection(TARGET, timeout=30)
        up.settimeout(None)  # cure (deleg_4fe7c3ad): connect timeout persists on recv;
        # slow LLM streams were severed mid-response (the no-output-for-20-minutes shape)
    except OSError:
        conn.close(); return
    threading.Thread(target=pipe, args=(conn, up), daemon=True).start()
    threading.Thread(target=pipe, args=(up, conn), daemon=True).start()

def main():
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE if sys.platform == "win32" else socket.SO_REUSEADDR, 1)
    s.bind(LISTEN); s.listen(64)
    print(f"fwd {LISTEN[0]}:{LISTEN[1]} -> {TARGET[0]}:{TARGET[1]} up", flush=True)
    while True:
        try:  # F-10 cure (deleg_b499ec12): transient accept OSError must NOT kill the forwarder
            c, _ = s.accept()
        except OSError as _e:
            print(f"ACCEPT-ERR: {type(_e).__name__}: {_e} -- continuing", flush=True)
            continue
        threading.Thread(target=serve, args=(c,), daemon=True).start()

if __name__ == "__main__":
    main()
