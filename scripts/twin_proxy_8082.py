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

# twin_proxy_8082.py — the DNS-rebinding cure, rebuilt 2026-11-07 (honcho-selfhost-ops skill, proven shape):
# bind 127.0.0.1:8082 (LISTEN), forward to TARGET (seat target from ORGANS_SEAT_URL / organs.json seat_url, default :8080), rewrite Host header to localhost:<target-port>.
# strata-family engines reject Host: host.docker.internal (403 rebinding protection); honcho points BASE_URL at host.docker.internal:8082.
import socket, threading, re, sys

LOCAL = ("127.0.0.1", 8082)
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
HOST_RE = re.compile(rb"Host: [^\r\n]*", re.IGNORECASE)

def fwd(src, dst, rewrite=False):
    # MEDIUM cure (clean-room audit child, deleg_4fe7c3ad, 2026-11-11, PROVEN): the Host rewrite ran
    # HOST_RE.sub on EVERY chunk -- a body chunk containing 'Host: evil' got its body eaten
    # ({"note":"Host: evil"} -> {"note":"Host: localhost:<target-port>, JSON corruption mid-request).
    # Rewrite ONLY the request header block (up to the first blank line); bodies pass through byte-exact.
    # LOW cure (split headers): the header is buffered until the terminating CRLFCRLF, so 'Ho'+'st:'
    # chunk splits are rewritten, not missed.
    head_done = not rewrite
    buf = b""
    try:
        while True:
            b = src.recv(65536)
            if not b:
                break
            if not head_done:
                buf += b
                i = buf.find(b"\r\n\r\n")
                if i == -1:
                    if len(buf) > 65536:   # runaway/unheaded stream: pass what we hold, stop rewriting
                        dst.sendall(buf); buf = b""; head_done = True
                    continue
                head = HOST_RE.sub(b"Host: localhost:" + str(TARGET[1]).encode(), buf[:i+4], count=1)  # wave-4 F-12: follows config TARGET, no baked port
                dst.sendall(head + buf[i+4:])
                buf = b""; head_done = True
                continue
            dst.sendall(b)
        if buf:
            dst.sendall(buf)
    except OSError:
        pass
    finally:
        try: dst.shutdown(socket.SHUT_WR)
        except OSError: pass

def handle(conn):
    try:
        up = socket.create_connection(TARGET, timeout=60)
        # MEDIUM cure (deleg_4fe7c3ad): create_connection's connect timeout PERSISTS on recv
        # (proven: gettimeout()==30 after connect) -- slow LLM streams (long thinking pauses >60s)
        # were severed mid-response: the 'queue hammered, no output for 20 minutes' shape.
        # Connect-timeout for dialing only; stream reads unbounded.
        up.settimeout(None)
    except OSError:
        conn.close()
        return
    threading.Thread(target=fwd, args=(conn, up, True), daemon=True).start()
    threading.Thread(target=fwd, args=(up, conn, False), daemon=True).start()

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE if sys.platform == "win32" else socket.SO_REUSEADDR, 1)
    s.bind(LOCAL)
    s.listen(128)
    print(f"twin proxy 127.0.0.1:8082 -> {TARGET[0]}:{TARGET[1]} (Host-rewriting)", flush=True)
    while True:
        try:  # F-10 cure (deleg_b499ec12): transient accept OSError must NOT kill the proxy
            c, _ = s.accept()
        except OSError as _e:
            print(f"ACCEPT-ERR: {type(_e).__name__}: {_e} -- continuing", flush=True)
            continue
        threading.Thread(target=handle, args=(c,), daemon=True).start()

if __name__ == "__main__":
    main()
