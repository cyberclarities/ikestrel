"""reveal.py: real values, for the local browser only.

Everything else in iKestrel is counts only. This module is the exception, and
it is fenced:

  * It is reached only through /api/reveal/*, which needs the session token
    and an X-Kestrel-Reveal: 1 header that only the app's own pages send.
  * Nothing here is used by the reports or the CSV. Those stay counts only.
  * Nothing is logged, cached to disk, or written anywhere. Every store still
    opens read-only.

Direction of a Siri interaction is read from who is listed on it, not from
the direction code. On real data the code runs opposite to Apple's documented
enum: rows that name a sender are messages received, rows that name only
recipients are messages sent.
"""

import datetime
import json
import plistlib

from . import db, linkage
from .stores import BY_ID, STORES

R = lambda sid: BY_ID[sid][1]  # noqa: E731
TIME_COLS = {"timestamp", "startDate", "occurredAt", "interactionDate", "createdAt", "updatedAt",
             "biomeEventTimestamp", "modifiedTimestamp", "updatedTimestamp", "starttime", "endtime"}
MAX_TEXT = 600


def _iso(apple):
    try:
        v = float(apple)
    except (TypeError, ValueError):
        return None
    if not (1e8 < v < 2e9):
        return None
    return (datetime.datetime(2001, 1, 1) + datetime.timedelta(seconds=v)).strftime("%Y-%m-%d %H:%M:%S")


def _labels():
    o = db.rows("ontology.db", "select id, label from predicate") or []
    c = db.rows("ontology.db", "select id, label from class") or []
    d = dict(o)
    d.update(dict(c))
    return d


def _md(x):
    s = str(x)
    return s[3:] if s.startswith("md:") else s


def _keyed_value(blob):
    """Decode an NSKeyedArchiver plist to its plain value, or describe it."""
    try:
        d = plistlib.loads(blob)
    except Exception:
        return "<%d bytes>" % len(blob)
    if isinstance(d, dict) and "$objects" in d:
        objs = d["$objects"]

        def res(v, depth=0):
            if isinstance(v, plistlib.UID):
                v = objs[v.data]
            if depth > 4:
                return v
            if isinstance(v, dict):
                if "value" in v:
                    return res(v["value"], depth + 1)
                if "NS.string" in v:
                    return v["NS.string"]
                return {k: res(x, depth + 1) for k, x in v.items() if not k.startswith("$")}
            return v
        root = d.get("$top", {}).get("root")
        try:
            v = res(root)
        except Exception:
            v = None
        return v if isinstance(v, (int, float, str, bool)) or v is None else json.dumps(v, default=str)[:MAX_TEXT]
    return json.dumps(d, default=str)[:MAX_TEXT]


def _cell(col, v):
    if isinstance(v, bytes):
        return _keyed_value(v) if v[:6] == b"bplist" else "<%d bytes>" % len(v)
    if isinstance(v, str) and len(v) > MAX_TEXT:
        return v[:MAX_TEXT] + "…"
    return v


def _datecomp(s):
    """Calendar values are JSON date components."""
    try:
        d = json.loads(s)
        return "%04d-%02d-%02d %02d:%02d" % (d.get("year", 0), d.get("month", 0), d.get("day", 0),
                                              d.get("hour", 0), d.get("minute", 0))
    except Exception:
        return s


# --- names ----------------------------------------------------------------

def names_for(ids):
    ids = [str(i) for i in ids]
    out = {}
    if not ids or not db.has_table("graph.db", "stable_graph"):
        return out
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        q = ("select subject, predicate, object from stable_graph where subject in (%s) "
             "and predicate in ('PS33','PS312','PS441') and relationshipPredicate=''" % ",".join("?" * len(chunk)))
        parts = {}
        for s, p, o in db.rows("graph.db", q, chunk) or []:
            parts.setdefault(str(s), {})[p] = o
        for s, p in parts.items():
            out[s] = p.get("PS33") or " ".join(x for x in (p.get("PS312"), p.get("PS441")) if x) or None
    return out


# --- people search ----------------------------------------------------------

def people(q="", limit=2000):
    if not db.has_table("graph.db", "stable_graph"):
        return []
    ids = [str(r[0]) for r in db.rows("graph.db", "select distinct subject from stable_graph where predicate='PS1' "
                                      "and relationshipPredicate='' and object='SB104'") or []]
    nm = names_for(ids)
    handles = {}
    if db.has_table(R("internalViews"), "handle_id"):
        for h, i in db.rows(R("internalViews"), "select handle, id from handle_id") or []:
            handles.setdefault(str(i), []).append(h)
    ql = (q or "").strip().lower()
    out = []
    for i in ids:
        n = nm.get(i) or ""
        hs = handles.get(i, [])
        if ql and ql not in n.lower() and not any(ql in h.lower() for h in hs) and ql != i:
            continue
        out.append({"id": i, "name": n or "(no name)", "handles": hs[:4], "n_handles": len(hs)})
    out.sort(key=lambda x: (x["name"] == "(no name)", x["name"].lower()))
    return {"total": len(ids), "matched": len(out), "people": out[:limit]}


# --- one person, across every store ---------------------------------------

def _triples(sid, table, subject, L, where="subject=?"):
    rs = db.rows(R(sid), "select predicate, relationshipId, relationshipPredicate, object from \"%s\" where %s"
                 % (table, where), (subject,)) if db.has_table(R(sid), table) else None
    if rs is None:
        return None
    flat, rel = [], {}
    for p, rid, rp, o in rs:
        if not rid:
            flat.append({"predicate": L.get(p, p), "value": o})
        else:
            g = rel.setdefault(rid, {"predicate": L.get(p, p), "fields": {}})
            g["fields"][L.get(rp, rp)] = o
    return {"facts": flat, "relations": list(rel.values())}


def _place(md_id, L):
    t = _triples("graph", "stable_graph", _md(md_id), L)
    if not t:
        return None
    out = {}
    for f in t["facts"]:
        if f["predicate"] in ("name",):
            out["name"] = f["value"]
    for r in t["relations"]:
        for k, v in r["fields"].items():
            if k not in ("is a",):
                out[k] = v
    return out or None


def _owner_ids():
    return linkage._owner()


def _norm_contact(x):
    s = str(x or "")
    if s.startswith("cnContact:"):
        s = s[10:]
    return s.split(":")[0].upper()


def person(pid):
    pid = _md(pid)
    L = _labels()
    P = {"id": pid}
    g = _triples("graph", "stable_graph", pid, L)
    if g:
        names = names_for([v["value"][3:] for r in g["relations"] for v in
                           [{"value": x} for x in r["fields"].values()] if str(v["value"]).startswith("md:")])
        for r in g["relations"]:
            for k, v in list(r["fields"].items()):
                if isinstance(v, str) and v.startswith("md:"):
                    r["fields"][k] = names.get(v[3:]) or v
                    pl = _place(v, L)
                    if pl:
                        r["place"] = pl
    P["graph"] = g
    P["name"] = names_for([pid]).get(pid)
    P["is_owner"] = pid in _owner_ids()

    hs = db.rows(R("internalViews"), "select handle from handle_id where id=?", (pid,)) \
        if db.has_table(R("internalViews"), "handle_id") else None
    P["handles"] = [h for (h,) in hs or []]

    if db.has_table(R("entityTagging"), "entity_tagging"):
        c = db.connect(R("entityTagging"))
        cur = c.execute("select * from entity_tagging where mdid=?", (pid,))
        row = cur.fetchone()
        if row:
            cols = [d[0] for d in cur.description]
            P["relationship_scores"] = {k: round(v, 3) for k, v in zip(cols, row)
                                        if k not in ("mdid", "eventid") and isinstance(v, float) and v > 0}

    if db.has_table(R("features"), "kv"):
        P["features"] = [{"view": v, "feature": f, "value": _keyed_value(x) if isinstance(x, bytes) else x,
                          "confidence": cf}
                         for v, f, x, cf in db.rows(R("features"), "select viewName, featureName, value, confidence from kv "
                                                    "where subidentifierName in (?, ?)", ("md:" + pid, pid)) or []]

    if db.has_table(R("importance"), "entityImportanceSignalsIDMap"):
        r = db.rows(R("importance"), "select isFavorite, isEmergencyContact, isICloudFamily, relationshipLabel "
                    "from entityImportanceSignalsIDMap where entityIdentifier in (?, ?)", ("md:" + pid, pid))
        if r:
            a, b, c, d = r[0]
            P["importance"] = {"favorite": bool(a), "emergency contact": bool(b), "iCloud family": bool(c),
                               "relationship label": d}

    if db.has_table(R("relevance"), "person_entity_longterm"):
        r = db.rows(R("relevance"), "select relevanceScore, explanation from person_entity_longterm where mdid in (?, ?)",
                    ("md:" + pid, pid))
        if r:
            try:
                ex = json.loads(r[0][1])
            except Exception:
                ex = r[0][1]
            P["relevance"] = {"score": r[0][0], "explanation": ex}

    if db.has_table(R("ecr"), "entity_summary"):
        c = db.connect(R("ecr"))
        cur = c.execute("select * from entity_summary where MD_ID in (?, ?)", ("md:" + pid, pid))
        row = cur.fetchone()
        if row:
            d = {k[0]: _cell(k[0], v) for k, v in zip(cur.description, row) if v not in (None, "")}
            if isinstance(d.get("neighbor_signals"), str):
                try:
                    d["neighbor_signals"] = json.loads(d["neighbor_signals"])
                except Exception:
                    pass
            P["siri_summary"] = d
    if db.has_table(R("ecr"), "asr_entity_alias"):
        P["spoken_aliases"] = [{"alias": a, "signal": s} for a, s in
                               db.rows(R("ecr"), "select alias, signal_type from asr_entity_alias where MD_ID in (?, ?)",
                                       ("md:" + pid, pid)) or []]

    if db.has_table(R("internalViews"), "photosObservedAges"):
        P["observed_ages"] = [{"date": _iso(t), "age": a} for t, a in
                              db.rows(R("internalViews"), "select interactionDate, observedAge from photosObservedAges "
                                      "where entityIdentifier in (?, ?)", ("md:" + pid, pid)) or []]

    P["communications"] = _comms(pid, P["handles"], g)
    return P


def _comms(pid, handles, g):
    """Siri interactions involving this person, joined by handle and by contact id."""
    if not db.has_table(R("siriRemembers"), "interactions"):
        return None
    hn = set(filter(None, (linkage._n_handle(h) for h in handles)))
    contacts = set()
    for f in (g or {}).get("facts", []):
        if f["predicate"] == "same as" and str(f["value"]).startswith("cnContact:"):
            contacts.add(_norm_contact(f["value"]))
    ents = db.rows(R("siriRemembers"), "select rowid, id, type from entities where type in ('Person','PersonHandle')") or []
    mine = set()
    via = {"handle": 0, "contact id": 0}
    for rowid, eid, typ in ents:
        if typ == "PersonHandle" and linkage._n_handle(eid) in hn:
            mine.add(rowid)
            via["handle"] += 1
        elif typ == "Person" and _norm_contact(eid) in contacts:
            mine.add(rowid)
            via["contact id"] += 1
    if not mine:
        return {"matched_entities": via, "total": 0, "items": []}
    ids = ",".join(str(int(r)) for r in mine)
    q = ("select i.rowid, i.startDate, i.type, i.bundleId, i.durationSeconds, coalesce(nullif(i.remoteDeviceId,''),'this Mac'), "
         "group_concat(distinct x.parameter), "
         "exists(select 1 from interactionEntities y where y.interactionRowid=i.rowid and y.parameter in ('sender','senderHandle')) "
         "from interactions i join interactionEntities x on x.interactionRowid=i.rowid "
         "where x.entityRowid in (%s) group by i.rowid order by i.startDate desc" % ids)
    rs = db.rows(R("siriRemembers"), q) or []
    is_owner = pid in _owner_ids()
    items, by_app, sent, recv, group = [], {}, 0, 0, 0
    for rid, t, typ, app, dur, dev, params, row_has_sender in rs:
        ps = set((params or "").split(","))
        theirs_sender = bool(ps & {"sender", "senderHandle"})
        theirs_recipient = bool(ps & {"recipients", "recipientHandles"})
        if is_owner:
            way = "sent by you" if theirs_sender else ("received by you" if theirs_recipient else "involves you")
            if theirs_sender:
                sent += 1
            elif theirs_recipient:
                recv += 1
        elif theirs_sender:
            way = "received from them"
            recv += 1
        elif theirs_recipient and not row_has_sender:
            way = "sent to them"
            sent += 1
        elif theirs_recipient:
            way = "group message, they were a recipient"
            group += 1
        else:
            way = "involves them"
        by_app[app] = by_app.get(app, 0) + 1
        if len(items) < 200:
            items.append({"when": _iso(t), "intent": typ, "app": app, "direction": way,
                          "duration_s": dur or None, "device": dev[:8] if dev != "this Mac" else dev})
    return {"matched_entities": via, "total": len(rs), "sent": sent, "received": recv, "group": group, "is_owner": is_owner,
            "first": items[-1]["when"] if items else None, "last": items[0]["when"] if items else None,
            "by_app": by_app, "items": items}


# --- chain drill-down ---------------------------------------------------------

def chain(cid, step):
    ids = linkage.chain_members(cid, step)
    if ids is None:
        return None
    ids = sorted(ids)
    nm = names_for(ids)
    out = [{"id": i, "name": nm.get(i) or "(no name)"} for i in ids]
    out.sort(key=lambda x: (x["name"] == "(no name)", x["name"].lower()))
    return out


# --- store browser --------------------------------------------------------------

def tables(sid):
    rel = R(sid)
    c = db.connect(rel)
    if c is None:
        return None
    out = []
    for (n,) in db.rows(rel, "select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name") or []:
        if not db.has_table(rel, n) or any(n.endswith(x) for x in ("_data", "_idx", "_docsize", "_config", "_content")):
            continue
        out.append({"table": n, "rows": db.scalar(rel, 'select count(*) from "%s"' % n.replace('"', '""'))})
    return out


def browse(sid, table, offset=0, limit=50):
    rel = R(sid)
    if not db.has_table(rel, table):
        return None
    c = db.connect(rel)
    cur = c.execute('select * from "%s" limit ? offset ?' % table.replace('"', '""'), (int(limit), int(offset)))
    cols = [d[0] for d in cur.description]
    L = _labels()
    rows = []
    for r in cur.fetchall():
        row = {}
        for k, v in zip(cols, r):
            v = _cell(k, v)
            row[k] = v
            if k in ("predicate", "relationshipPredicate", "object") and isinstance(v, str) and v in L:
                row[k + " (label)"] = L[v]
            if k in TIME_COLS:
                iso = _iso(v)
                if iso:
                    row[k + " (date)"] = iso
        rows.append(row)
    total = db.scalar(rel, 'select count(*) from "%s"' % table.replace('"', '""'))
    shown = []
    for r in rows:
        for k in r:
            if k not in shown:
                shown.append(k)
    return {"store": sid, "path": rel, "table": table, "columns": shown, "rows": rows,
            "offset": int(offset), "limit": int(limit), "total": total}


def stores_list():
    return [{"id": s[0], "path": s[1], "group": s[2], "sensitivity": s[4]} for s in STORES]


# --- timeline -----------------------------------------------------------------

def timeline(before=None, limit=200, sources=None):
    before = float(before) if before else 9e9
    want = set(sources or ["siri", "wifi", "calendar", "mechanisms", "faces"])
    ev = []
    sr = R("siriRemembers")
    handle_name = {}
    if db.has_table(R("internalViews"), "handle_id"):
        hrows = db.rows(R("internalViews"), "select handle, id from handle_id") or []
        nm = names_for(set(str(i) for _, i in hrows))
        for h, i in hrows:
            n = linkage._n_handle(h)
            if n and nm.get(str(i)):
                handle_name[n] = nm[str(i)]
    if "siri" in want and db.has_table(sr, "interactions"):
        q = ("select i.rowid, i.startDate, i.type, i.bundleId, i.durationSeconds, coalesce(nullif(i.remoteDeviceId,''),'this Mac'), "
             "group_concat(e.type || '|' || x.parameter || '|' || e.fields || '|' || e.id, char(30)) "
             "from interactions i left join interactionEntities x on x.interactionRowid=i.rowid "
             "left join entities e on e.rowid=x.entityRowid where i.startDate < ? "
             "group by i.rowid order by i.startDate desc limit ?")
        for rid, t, typ, app, dur, dev, ents in db.rows(sr, q, (before, limit)) or []:
            who, sender = [], False
            for part in (ents or "").split(chr(30)):
                bits = part.split("|", 3)
                if len(bits) < 4:
                    continue
                et, param, fields, eid = bits
                if param in ("sender", "senderHandle"):
                    sender = True
                if et == "Person":
                    try:
                        n = json.loads(fields).get("name")
                    except Exception:
                        n = None
                    if n and n not in who:
                        who.append(n)
                elif et == "PersonHandle" and not who:
                    who.append(handle_name.get(linkage._n_handle(eid)) or eid)
                elif et == "MessageGroup" and param == "speakableGroupName":
                    try:
                        gname = json.loads(fields).get("name")
                    except Exception:
                        gname = None
                    if gname:
                        who.append("group: " + gname)
            way = "received" if sender else ("sent" if who else "")
            ev.append({"t": t, "when": _iso(t), "source": "Siri history", "what": typ, "app": app,
                       "detail": ", ".join(who[:6]), "direction": way, "duration_s": dur or None,
                       "device": dev if dev == "this Mac" else dev[:8]})
    iv = R("internalViews")
    if "wifi" in want and db.has_table(iv, "wifiContextEvents"):
        for t, b in db.rows(iv, "select timestamp, behaviorIdentifier from wifiContextEvents where timestamp < ? "
                            "order by timestamp desc limit ?", (before, limit)) or []:
            act, _, ssid = (b or "").partition(":")
            ev.append({"t": t, "when": _iso(t), "source": "Wi-Fi", "what": act, "app": "", "detail": ssid,
                       "direction": "", "duration_s": None, "device": "this Mac"})
    if "mechanisms" in want and db.has_table(iv, "bidirectionalPersonInteractionMechanisms"):
        rs = db.rows(iv, "select interactionDate, entityIdentifier, communicationMechanism, bundleID from "
                     "bidirectionalPersonInteractionMechanisms where interactionDate < ? order by interactionDate desc limit ?",
                     (before, limit)) or []
        nm = names_for([_md(r[1]) for r in rs])
        for t, e, mech, app in rs:
            ev.append({"t": t, "when": _iso(t), "source": "Two-way contact", "what": "mechanism %s" % mech, "app": app or "",
                       "detail": nm.get(_md(e)) or e, "direction": "", "duration_s": None, "device": ""})
    if "faces" in want and db.has_table(iv, "photosObservedAges"):
        rs = db.rows(iv, "select interactionDate, entityIdentifier, observedAge from photosObservedAges where interactionDate < ? "
                     "order by interactionDate desc limit ?", (before, limit)) or []
        nm = names_for([_md(r[1]) for r in rs])
        for t, e, age in rs:
            ev.append({"t": t, "when": _iso(t), "source": "Photos", "what": "age read from face: %s" % age, "app": "",
                       "detail": nm.get(_md(e)) or e, "direction": "", "duration_s": None, "device": ""})
    if "calendar" in want and db.has_table("graph.db", "event_graph"):
        rs = db.rows("graph.db", "select subject, relationshipPredicate, object, predicate from event_graph "
                     "where (relationshipPredicate in ('PS29','PS30') or predicate='PS33')") or []
        evs = {}
        for s, rp, o, p in rs:
            e = evs.setdefault(s, {})
            if p == "PS33":
                e["name"] = o
            elif rp == "PS29":
                e["start"] = o
            elif rp == "PS30":
                e["end"] = o
        for s, e in evs.items():
            st = _datecomp(e.get("start", ""))
            try:
                dt = datetime.datetime.strptime(st, "%Y-%m-%d %H:%M")
                t = (dt - datetime.datetime(2001, 1, 1)).total_seconds()
            except Exception:
                continue
            if t >= before:
                continue
            ev.append({"t": t, "when": st, "source": "Calendar", "what": "event", "app": "",
                       "detail": e.get("name", ""), "direction": "", "duration_s": None, "device": "",
                       "end": _datecomp(e.get("end", "")) if e.get("end") else None})
    ev.sort(key=lambda x: -(x["t"] or 0))
    ev = ev[:limit]
    nxt = ev[-1]["t"] if len(ev) == limit else None
    return {"events": ev, "next_before": nxt}
