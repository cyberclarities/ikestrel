"""sheet.py: one row per store, for the sheet page and the CSV download.

The page and the CSV are built from the same rows, so they cannot disagree.
Every value is a label, a count, or dossier text whose examples are invented.

CSV cells that start with = + - @ (or a tab or carriage return) are prefixed
with an apostrophe, so a spreadsheet app opens them as text, not formulas.
"""

import csv
import io

from . import dossier

KEYS = ["entity", "contact", "handle", "face", "device"]

COLUMNS = [
    ("store", "Store"), ("group", "Group"), ("sensitivity", "Sensitivity"),
    ("alone", "What it gives away"), ("worst", "Worst case"),
    ("headline", "Headline count"),
    ("ids_entity", "Entity ids"), ("ids_contact", "Contact ids"), ("ids_handle", "Phones and emails"),
    ("ids_face", "Face clusters"), ("ids_device", "Device ids"),
    ("joins", "Joins with overlap"), ("joined_to", "Joined to"), ("chains", "In chains"),
    ("status", "Status"), ("measured", "Measurements taken"), ("path", "Path"),
    ("holds", "What it holds"), ("example", "Example rows (invented)"),
]

SENS_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def _headline(ms):
    """The first measured single number for the store, with its title."""
    for m in ms:
        if m["measured"] and m["groups"] is None and isinstance(m["value"], (int, float)):
            return "%s: %s" % (m["title"], m["value"])
    for m in ms:
        if m["measured"] and m["groups"]:
            return "%s: %d" % (m["title"], sum(v or 0 for v in m["groups"].values()))
    return ""


def rows(d):
    L = d.get("linkage") or {}
    nodes = {n["id"]: n for n in L.get("nodes", [])}
    by_store = {}
    for m in d["measurements"]:
        by_store.setdefault(m["store"], []).append(m)
    out = []
    for c in d["coverage"]:
        sid = c["id"]
        n = nodes.get(sid, {})
        sp = n.get("spaces") or {}
        mine = [e for e in L.get("edges", []) if e["measured"] and e["overlap"] and sid in (e["a"], e["b"])]
        partners = sorted(set((e["b"] if e["a"] == sid else e["a"]) for e in mine))
        ch = [x["id"] for x in L.get("chains", []) if sid in x["path"]]
        ds = dossier.get(sid) or {}
        row = {
            "group": c["group"], "store": sid, "path": c["path"], "sensitivity": c["sensitivity"],
            "status": c["status"], "measured": "%d of %d" % (c["measured"], c["measurements"]),
            "headline": _headline(by_store.get(sid, [])),
            "joins": len(mine), "joined_to": ", ".join(partners), "chains": ", ".join(ch),
            "holds": c["holds"], "alone": ds.get("alone", ""), "worst": ds.get("worst", ""),
            "example": "\n".join(ds.get("example", [])),
        }
        for k in KEYS:
            v = sp.get(k)
            row["ids_" + k] = "" if k not in sp else ("not measured" if v is None else v)
        out.append(row)
    out.sort(key=lambda r: (SENS_ORDER.get(r["sensitivity"], 9), r["group"], r["store"]))
    return out


def _safe(v):
    s = "" if v is None else str(v)
    if s[:1] in ("=", "+", "-", "@", "\t", "\r"):
        s = "'" + s
    return s


def to_csv(rs):
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    w.writerow([label for _, label in COLUMNS])
    for r in rs:
        w.writerow([_safe(r.get(k)) for k, _ in COLUMNS])
    return "﻿" + buf.getvalue()  # BOM so Excel reads UTF-8
