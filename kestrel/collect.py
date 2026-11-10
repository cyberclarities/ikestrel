"""collect.py: one pass over everything, shared by the UI and both reports."""

import datetime
import os

from . import catalog, db, findings, live, measure, stores
from .version import VERSION


def _display_root():
    home = os.path.expanduser("~")
    return db.ROOT.replace(home, "~", 1) if db.ROOT.startswith(home) else db.ROOT


def coverage(results):
    by_store = {}
    for r in results:
        by_store.setdefault(r["store"], []).append(r)
    known_paths = set(p for _, p, _, _, _ in stores.STORES)
    gaps = {}
    for g in db.gaps():
        gaps.setdefault(g["store"], []).append(g["reason"])
    rows = []
    for s in stores.as_dicts():
        ms = by_store.get(s["id"], [])
        present = os.path.exists(db.path(s["path"]))
        n_ok = sum(1 for m in ms if m["measured"])
        if not present:
            status = "absent"
        elif ms and n_ok == len(ms):
            status = "measured"
        elif ms and n_ok:
            status = "partly measured"
        elif ms:
            status = "not measured"
        else:
            status = "inventoried"
        rows.append(dict(s, present=present, measurements=len(ms), measured=n_ok,
                         status=status, reasons=gaps.get(s["path"], [])))
    extra = []
    for rel in db.store_files():
        if rel.endswith((".db", ".sql")) and rel not in known_paths and "fullRebuild" not in rel:
            extra.append(rel)
    return rows, extra


def run(watch_terms=None, hashes=False):
    db.begin()
    try:
        results = measure.run_all()
        M = measure.by_id(results)
        watch = measure.watchlist(watch_terms or [])
        lc = live.checks()
        F, open_q = findings.evaluate(M, lc, watch)
        cov, extra = coverage(results)
        scope = []
        if hashes:
            for rel in db.store_files():
                if not rel.endswith("-shm"):
                    scope.append({"file": rel, "sha256": db.sha256(rel),
                                  "bytes": os.path.getsize(db.path(rel))})
        return {
            "version": VERSION, "mode": db.mode(), "root": _display_root(),
            "generated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "measurements": results, "findings": F, "open": open_q,
            "coverage": cov, "uncatalogued": extra, "gaps": db.gaps(),
            "watch": watch, "live": lc, "scope": scope,
            "catalog": [{"category": c, "prefixes": p} for c, p in catalog.CATEGORIES],
        }
    finally:
        db.close()
