import os
HOME = os.environ.get("ORGANS_HOME", os.path.expanduser("~/shop"))

# strata_forward_18080.py - shop-side TCP forwarder: WSL dream seat route (keeper order 2026-11-07)
# Forwards 0.0.0.0:18080 -> 127.0.0.1:8080 (strata). Shop-owned, stdlib, threaded.
import socket, threading, sys

LOCAL = ("0.0.0.0", 18080)
TARGET = ("127.0.0.1", 47831)

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
        c, addr = s.accept()
        threading.Thread(target=handle, args=(c,), daemon=True).start()

if __name__ == "__main__":
    main()
