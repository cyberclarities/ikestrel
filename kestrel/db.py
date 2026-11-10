"""db.py: read-only access to the IntelligencePlatform stores, live or from a copy.

Rules that hold everywhere in this package:

1. Every connection opens with mode=ro on a file: URI. SQLite refuses writes on
   such a handle, so no code path can change a store.
2. Connections are thread-local and closed at the end of each request.
3. Text decodes leniently; some columns hold bytes that are not valid UTF-8.
4. A store or statement that cannot run degrades to "not measured", and the
   reason goes into a per-request ledger. Empty is never reported as zero.
5. Full-text virtual tables are never touched. Apple builds them with a
   private tokenizer (unicode61wrapper) that stock SQLite lacks, so even a
   count against one raises. Their content tables carry the same rows.

Nothing here writes to disk.
"""

import hashlib
import os
import sqlite3
import threading
import urllib.parse

LIVE_ROOT = "~/Library/IntelligencePlatform"
APPLE_EPOCH = 978307200  # 2001-01-01 UTC in unix seconds

ROOT = os.path.expanduser(os.environ.get("KESTREL_ROOT") or LIVE_ROOT)
_MODE = "live"
_local = threading.local()


def configure(copy=None):
    """Point the app at a copied IntelligencePlatform folder instead of the live one."""
    global ROOT, _MODE
    if copy:
        p = os.path.abspath(os.path.expanduser(copy))
        nested = os.path.join(p, "IntelligencePlatform")
        if not os.path.exists(os.path.join(p, "graph.db")) and os.path.isdir(nested):
            p = nested
        ROOT, _MODE = p, "copy"


def mode():
    return _MODE


def path(rel):
    return os.path.join(ROOT, rel)


# --- the ledger: what this request could not read ---------------------------

def begin():
    _local.gaps = []


def gap(store, reason):
    g = getattr(_local, "gaps", None)
    if g is None:
        _local.gaps = g = []
    item = {"store": store, "reason": reason}
    if item not in g:
        g.append(item)


def gaps():
    return list(getattr(_local, "gaps", []))


# --- connections -------------------------------------------------------------

def _decode(b):
    return b.decode("utf-8", "replace")


def connect(rel):
    """A read-only handle on one store, or None (with a ledger entry) if it cannot open."""
    cache = getattr(_local, "conns", None)
    if cache is None:
        _local.conns = cache = {}
    if rel in cache:
        return cache[rel]
    p = path(rel)
    conn = None
    if not os.path.exists(p):
        gap(rel, "file not present")
    elif not os.access(p, os.R_OK):
        gap(rel, "not readable (Full Disk Access?)")
    else:
        try:
            uri = "file:" + urllib.parse.quote(p) + "?mode=ro"
            conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
            conn.text_factory = _decode
            conn.execute("select count(*) from sqlite_master").fetchone()
        except sqlite3.Error as e:
            gap(rel, "cannot open: %s" % e)
            conn = None
    cache[rel] = conn
    return conn


def close():
    for c in (getattr(_local, "conns", None) or {}).values():
        if c is not None:
            try:
                c.close()
            except sqlite3.Error:
                pass
    _local.conns = {}


def has_table(rel, table):
    c = connect(rel)
    if c is None:
        return False
    try:
        row = c.execute("select sql from sqlite_master where type='table' and name=?",
                        (table,)).fetchone()
    except sqlite3.Error:
        return False
    if row is None:
        return False
    if (row[0] or "").upper().startswith("CREATE VIRTUAL"):
        return False  # rule 5
    return True


def scalar(rel, sql, params=()):
    """One number from one store, or None with the reason in the ledger."""
    c = connect(rel)
    if c is None:
        return None
    try:
        row = c.execute(sql, params).fetchone()
        return None if row is None else row[0]
    except sqlite3.Error as e:
        gap(rel, "query failed: %s" % e)
        return None


def rows(rel, sql, params=()):
    c = connect(rel)
    if c is None:
        return None
    try:
        return c.execute(sql, params).fetchall()
    except sqlite3.Error as e:
        gap(rel, "query failed: %s" % e)
        return None


# --- scope: what files are in play, and their hashes -------------------------

def store_files():
    """Every database file under the root, with its WAL and SHM, relative paths."""
    out = []
    for dp, dn, fn in os.walk(ROOT):
        dn.sort()
        for f in sorted(fn):
            if f.endswith((".db", ".sql", ".db-wal", ".sql-wal", ".db-shm", ".sql-shm")):
                out.append(os.path.relpath(os.path.join(dp, f), ROOT))
    return out


def sha256(rel):
    h = hashlib.sha256()
    try:
        with open(path(rel), "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError as e:
        return "unreadable: %s" % e.strerror
    return h.hexdigest()


def apple_date(seconds):
    """Apple-epoch seconds to an ISO date (UTC). Dates are not personal on their own."""
    import datetime
    if seconds is None:
        return None
    try:
        return datetime.datetime.utcfromtimestamp(float(seconds) + APPLE_EPOCH).strftime("%Y-%m-%d")
    except (ValueError, OverflowError, OSError):
        return None
