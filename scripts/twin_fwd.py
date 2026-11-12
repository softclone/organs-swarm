import os
HOME = os.environ.get("ORGANS_HOME", os.path.expanduser("~/shop"))

#!/usr/bin/env python3
# twin_fwd.py -- TCP forwarder 127.0.0.1:18082 -> 127.0.0.1:8000 (honcho door beside the twin).
# Reborn 2026-11-11 (pipes recovery C5-2122, rebuilt after the 12:57 CST host hardlock destroyed
# the lane copy). Threaded relay, no timeouts on relay legs (streaming-safe).
import socket, threading, sys

LISTEN = ("127.0.0.1", 18082)
TARGET = ("127.0.0.1", 8000)

def relay(a, b):
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

def handle(c):
    try:
        u = socket.create_connection(TARGET, timeout=30)
    except OSError:
        c.close()
        return
    u.settimeout(None)  # connect timeout must NOT persist on recv (20-min sever class, C5-1849; re-born C5-16484)
    threading.Thread(target=relay, args=(c, u), daemon=True).start()
    threading.Thread(target=relay, args=(u, c), daemon=True).start()

def main():
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE if sys.platform == "win32" else socket.SO_REUSEADDR, 1)
    s.bind(LISTEN)
    s.listen(64)
    print("twin_fwd listening on 18082 -> 8000", flush=True)
    while True:
        try:
            c, _ = s.accept()
        except OSError as e:
            print("ACCEPT-ERR:", type(e).__name__, flush=True)  # F12 cure (C5-16486): transient accept failure must not kill the forwarder
            continue
        threading.Thread(target=handle, args=(c,), daemon=True).start()

if __name__ == "__main__":
    main()
