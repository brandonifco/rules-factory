#!/usr/bin/env python3
"""An HTTPS allowlist proxy on a Unix socket, and the TCP bridge that reaches it from inside a network
namespace. RUNBOOK.md, "Network".

    allowlist-proxy.py serve  --socket PATH --allow FILE --log FILE
    allowlist-proxy.py bridge --socket PATH [--port 3128]

`serve` runs outside the namespace. It accepts HTTP CONNECT requests on the Unix socket, and opens
the tunnel only when the requested host is in the allowlist (exact names, or `.suffix` for a domain
and its subdomains) and the port is 443. Everything else is answered 403. Plain HTTP requests are
refused: every allowed host speaks HTTPS. Each request is one JSON line in the log, allowed or not.

`bridge` runs inside a namespace made with `unshare --user --map-root-user --net`, where the only
interface is loopback. It listens on 127.0.0.1:PORT and pipes each connection to the Unix socket,
which the namespace can still reach because the filesystem is shared. With no route out, the proxy
is the only way to the network, so HTTPS_PROXY is not a convention the session could ignore: a
process that ignores it reaches nothing.

Standard library only.
"""
import argparse
import json
import os
import socket
import sys
import threading
import time


def pipe(a: socket.socket, b: socket.socket) -> None:
    def one_way(src, dst):
        try:
            while data := src.recv(65536):
                dst.sendall(data)
        except OSError:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    threads = [threading.Thread(target=one_way, args=(a, b), daemon=True),
               threading.Thread(target=one_way, args=(b, a), daemon=True)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    a.close()
    b.close()


def allowed(host: str, rules: list[str]) -> bool:
    host = host.lower().rstrip(".")
    return any(host == r or (r.startswith(".") and (host.endswith(r) or host == r[1:])) for r in rules)


def serve(args) -> int:
    rules = [line.split("#", 1)[0].strip().lower() for line in open(args.allow, encoding="utf-8")]
    rules = [r for r in rules if r]
    if os.path.exists(args.socket):
        os.unlink(args.socket)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    # Bound under another name and renamed once listening, so the socket's path never exists before a
    # connection to it can succeed (callers wait for the path).
    pending = args.socket + ".pending"
    server.bind(pending)
    os.chmod(pending, 0o600)
    server.listen(64)
    os.rename(pending, args.socket)
    log = open(args.log, "a", encoding="utf-8", buffering=1)
    print(f"allowlist proxy on {args.socket}: {len(rules)} rule(s), log {args.log}", flush=True)

    def handle(client: socket.socket) -> None:
        head = b""
        while b"\r\n\r\n" not in head and len(head) < 65536:
            chunk = client.recv(4096)
            if not chunk:
                client.close()
                return
            head += chunk
        request = head.split(b"\r\n", 1)[0].decode("latin-1")
        parts = request.split()
        method, target = (parts[0], parts[1]) if len(parts) >= 2 else ("?", "?")
        host, _, port = target.rpartition(":") if method == "CONNECT" else (target, "", "")
        ok = method == "CONNECT" and port == "443" and allowed(host, rules)
        log.write(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "method": method,
                              "target": target, "allowed": ok}) + "\n")
        if not ok:
            client.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            client.close()
            return
        try:
            upstream = socket.create_connection((host, 443), timeout=30)
            upstream.settimeout(None)
        except OSError:
            client.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            client.close()
            return
        client.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
        rest = head.split(b"\r\n\r\n", 1)[1]
        if rest:
            upstream.sendall(rest)
        pipe(client, upstream)

    while True:
        client, _ = server.accept()
        threading.Thread(target=handle, args=(client,), daemon=True).start()


def bridge(args) -> int:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", args.port))
    listener.listen(64)
    print(f"bridge 127.0.0.1:{args.port} -> {args.socket}", flush=True)
    while True:
        client, _ = listener.accept()
        upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            upstream.connect(args.socket)
        except OSError:
            client.close()
            continue
        threading.Thread(target=pipe, args=(client, upstream), daemon=True).start()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--socket", required=True)
    s.add_argument("--allow", required=True)
    s.add_argument("--log", required=True)
    b = sub.add_parser("bridge")
    b.add_argument("--socket", required=True)
    b.add_argument("--port", type=int, default=3128)
    args = parser.parse_args(argv)
    return serve(args) if args.command == "serve" else bridge(args)


if __name__ == "__main__":
    sys.exit(main())
