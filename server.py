#!/usr/bin/env python3
"""iKestrel server: local only, one process, standard library only.

  python3 server.py                     read this Mac's live stores
  python3 server.py --copy PATH         read a copied IntelligencePlatform folder

Bound to 127.0.0.1. A fresh token at every start; every request must carry it.
Every store opens read-only. Nothing is written to disk.
"""

import argparse
import http.cookies
import http.server
import json
import os
import secrets
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from kestrel import collect, db, report  # noqa: E402
from kestrel.version import VERSION  # noqa: E402

PUBLIC = os.path.join(HERE, "public")
STATIC = {"app.js": "text/javascript", "app.css": "text/css", "report.css": "text/css",
          "report.js": "text/javascript", "logo.svg": "image/svg+xml"}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
TOKEN = secrets.token_urlsafe(24)
WATCHLIST_FILE = os.path.join(HERE, "watchlist.txt")


def file_watchlist():
    try:
        with open(WATCHLIST_FILE, encoding="utf-8") as fh:
            return [l.strip() for l in fh if l.strip() and not l.startswith("#")]
    except OSError:
        return []


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "iKestrel/" + VERSION
    sys_version = ""

    def log_message(self, fmt, *args):  # no request log: paths can carry watchlist terms
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8", cookie=None):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self, q):
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            return False  # DNS rebinding guard
        if secrets.compare_digest((q.get("t") or [""])[0], TOKEN):
            return True
        c = http.cookies.SimpleCookie(self.headers.get("Cookie") or "")
        return "kestrel" in c and secrets.compare_digest(c["kestrel"].value, TOKEN)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if not self._authorized(q):
            return self._send(403, "Forbidden. Open the link the server printed.", "text/plain; charset=utf-8")
        cookie = "kestrel=%s; HttpOnly; SameSite=Strict; Path=/" % TOKEN if "t" in q else None
        watch = file_watchlist() + [t for t in (q.get("watch") or [""])[0].split(",") if t.strip()]
        try:
            if u.path == "/":
                with open(os.path.join(PUBLIC, "index.html"), "rb") as fh:
                    return self._send(200, fh.read(), cookie=cookie)
            if u.path.startswith("/static/"):
                name = u.path[len("/static/"):]
                if name not in STATIC:
                    return self._send(404, "Not found", "text/plain")
                with open(os.path.join(PUBLIC, name), "rb") as fh:
                    return self._send(200, fh.read(), STATIC[name])
            if u.path == "/api/summary":
                d = collect.run(watch)
                return self._send(200, json.dumps(d), "application/json")
            if u.path == "/report/brief":
                return self._send(200, report.brief(collect.run(watch)), cookie=cookie)
            if u.path == "/report/technical":
                return self._send(200, report.technical(collect.run(watch, hashes=True)), cookie=cookie)
        except Exception as e:  # never leak a traceback with store contents
            sys.stderr.write("error on %s: %s\n" % (u.path, type(e).__name__))
            return self._send(500, "Internal error. See the terminal.", "text/plain")
        return self._send(404, "Not found", "text/plain")

    def do_POST(self):
        self._send(405, "Read-only.", "text/plain")


def main():
    ap = argparse.ArgumentParser(description="iKestrel: what this Mac's IntelligencePlatform holds, counts only.")
    ap.add_argument("--copy", help="a copied IntelligencePlatform folder (or its parent) instead of the live one")
    ap.add_argument("--port", type=int, default=0, help="port on 127.0.0.1 (default: any free port)")
    a = ap.parse_args()
    db.configure(copy=a.copy)
    if not os.path.isdir(db.ROOT):
        sys.exit("No IntelligencePlatform folder at %s" % db.ROOT)
    if not os.access(os.path.join(db.ROOT, "graph.db"), os.R_OK):
        sys.stderr.write("graph.db is not readable. On a live Mac, give the app you launched this from "
                         "Full Disk Access (System Settings > Privacy & Security), quit it fully, reopen.\n")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print("iKestrel %s reading %s (%s)" % (VERSION, db.ROOT, db.mode()))
    print("Open: http://127.0.0.1:%d/?t=%s" % (srv.server_address[1], TOKEN))
    print("Ctrl-C to stop. The token changes at every start.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
