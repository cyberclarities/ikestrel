"""messaging.py: what the stores hold about each messaging app.

For every app in APPS, and any other app the catalog calls communication, this
reports what these stores keep:

  installed      the app is installed on this Mac (graph.db, from LaunchServices)
  history        Siri's interaction history: messages and calls, sent and
                 received, group chats, people, devices, first and last dates
  pairings       Siri's resolver: how many contact-and-app pairings it holds,
                 the record of which app you use for whom
  two-way        the recent two-way contact table

Message text is never in these stores. Messages covers iMessage and SMS
together; Siri's history does not say which.

Direction is read per interaction from who is listed on it, as everywhere in
iKestrel: a row naming a sender is a message received, a row naming only
recipients is one sent. Calls name the other party in a "contacts" slot instead,
so for a row with neither, the direction column decides, read with the same
test iOwl uses: the value that carries senders is incoming, the other value that
names recipients is outgoing. Apple's documented numbering is not assumed.

real=False returns counts only. real=True adds the people and group chat names
for each app; it is served only through /api/reveal/messaging.
"""

import datetime

from . import db, linkage
from .stores import BY_ID

R = lambda sid: BY_ID[sid][1]  # noqa: E731

PRIVATE, APPLE, SOCIAL, WORK = ("Private or encrypted messenger", "Apple Messages, Phone and FaceTime",
                                "Social and community chat", "Work collaboration")

# key, product, kind, bundle-id prefixes (lower case), always listed
APPS = [
    ("signal", "Signal", PRIVATE, ["org.whispersystems.signal"], True),
    ("whatsapp", "WhatsApp", PRIVATE, ["net.whatsapp.", "desktop.whatsapp", "whatsapp"], True),
    ("messages", "Messages (iMessage and SMS)", APPLE, ["com.apple.mobilesms", "com.apple.ichat", "com.apple.messages"], True),
    ("telegram", "Telegram", PRIVATE, ["ph.telegra.", "org.telegram.", "ru.keepcoder.telegram"], True),
    ("phone", "Phone calls", APPLE, ["com.apple.incallservice", "com.apple.mobilephone", "com.apple.telephonyutilities"], True),
    ("facetime", "FaceTime", APPLE, ["com.apple.facetime"], True),
    ("messenger", "Facebook Messenger", SOCIAL, ["com.facebook.messenger"], True),
    ("threema", "Threema", PRIVATE, ["ch.threema."], False),
    ("wire", "Wire", PRIVATE, ["com.wire.", "com.wearezeta."], False),
    ("element", "Element", PRIVATE, ["im.vector.", "im.riot.", "io.element."], False),
    ("session", "Session", PRIVATE, ["com.sessionmessenger.", "com.loki-project."], False),
    ("simplex", "SimpleX", PRIVATE, ["chat.simplex."], False),
    ("viber", "Viber", PRIVATE, ["com.viber."], False),
    ("line", "LINE", SOCIAL, ["jp.naver.line"], False),
    ("wechat", "WeChat", SOCIAL, ["com.tencent.xin"], False),
    ("kakao", "KakaoTalk", SOCIAL, ["com.iwilab.kakaotalk"], False),
    ("facebook", "Facebook", SOCIAL, ["com.facebook.facebook"], False),
    ("instagram", "Instagram", SOCIAL, ["com.burbn.instagram"], False),
    ("snapchat", "Snapchat", SOCIAL, ["com.toyopagroup.picaboo"], False),
    ("discord", "Discord", SOCIAL, ["com.hammerandchisel.discord", "com.hnc.discord", "com.discord"], False),
    ("x", "X", SOCIAL, ["com.atebits.tweetie2"], False),
    ("linkedin", "LinkedIn", SOCIAL, ["com.linkedin."], False),
    ("teams", "Microsoft Teams", WORK, ["com.microsoft.teams", "com.microsoft.skype.teams"], False),
    ("skype", "Skype", WORK, ["com.skype."], False),
    ("slack", "Slack", WORK, ["com.tinyspeck.", "com.slack."], False),
    ("zoom", "Zoom", WORK, ["us.zoom."], False),
    ("webex", "Webex", WORK, ["com.cisco.webex", "com.webex."], False),
    ("googlechat", "Google Chat", WORK, ["com.google.dynamite", "com.google.chat"], False),
]
KIND_ORDER = [PRIVATE, APPLE, SOCIAL, WORK]

NOTHING = ("No trace in these stores. That can mean the app is not on your devices, that it does not hand its "
           "activity to Siri, or that its Siri setting is off. These stores cannot tell which.")
IMESSAGE = ("Messages covers iMessage and SMS together. Siri's history does not say which service carried a "
            "message; iOwl can split them, because it also reads Messages' own database.")


def app_of(bundle):
    b = (bundle or "").lower()
    for key, product, kind, prefixes, _ in APPS:
        if any(b.startswith(p) for p in prefixes):
            return key
    return None


def _iso(t):
    try:
        return (datetime.datetime(2001, 1, 1) + datetime.timedelta(seconds=float(t))).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        return None


def _has_col(sr, table, col):
    return any(r[1] == col for r in (db.rows(sr, 'pragma table_info("%s")' % table) or []))


def _directions(sr):
    """(incoming, outgoing) values of the direction column, measured by the sender test."""
    if not _has_col(sr, "interactions", "direction"):
        return None, None
    rs = db.rows(sr, "select i.direction, "
                 "sum(exists(select 1 from interactionEntities x where x.interactionRowid=i.rowid and x.parameter in ('sender','senderHandle'))), "
                 "sum(exists(select 1 from interactionEntities x where x.interactionRowid=i.rowid "
                 "and x.parameter in ('recipients','recipientHandles','contacts','contactHandles'))) "
                 "from interactions i group by 1") or []
    carriers = [r for r in rs if (r[1] or 0) > 0]
    inc = max(carriers, key=lambda r: r[1])[0] if carriers else None
    others = [r for r in rs if r[0] != inc and (r[2] or 0) > 0]
    out = max(others, key=lambda r: r[2])[0] if others else None
    return inc, out


def _blank(key, product, kind, watch):
    return {"key": key, "product": product, "kind": kind, "watch": watch, "bundles": set(),
            "installed": [], "interactions": 0, "messages": 0, "calls": 0, "other": 0,
            "sent": 0, "received": 0, "requests": 0, "in_groups": 0, "groups": set(),
            "people": set(), "named": set(), "devices": set(), "on_mac": 0,
            "first": None, "last": None, "pairings": 0, "pairing_events": 0, "two_way": 0,
            "by_person": {}, "by_group": {}}


def build(real=False):
    A = {k: _blank(k, p, kd, w) for k, p, kd, _, w in APPS}

    # installed on this Mac
    for (b,) in (db.rows("graph.db", "select distinct object from stable_graph where predicate='nm_bundleID'")
                 if db.has_table("graph.db", "stable_graph") else None) or []:
        k = app_of(b)
        if k:
            A[k]["installed"].append(b)
            A[k]["bundles"].add(b)

    # Siri history
    sr = R("siriRemembers")
    measured_history = db.has_table(sr, "interactions")
    if measured_history:
        owner = linkage._owner()
        hmap = {}
        if db.has_table(R("internalViews"), "handle_id"):
            for h, i in db.rows(R("internalViews"), "select handle, id from handle_id") or []:
                n = linkage._n_handle(h)
                if n and str(i) not in owner:
                    hmap.setdefault(n, set()).add(str(i))
        ents = {}
        for rowid, eid, typ, fields in db.rows(sr, "select rowid, id, type, fields from entities "
                                               "where type in ('Person','PersonHandle','MessageGroup')") or []:
            ents[rowid] = (typ, eid, fields)
        params = {}
        for irow, erow, p in db.rows(sr, "select interactionRowid, entityRowid, parameter from interactionEntities") or []:
            params.setdefault(irow, []).append((erow, p))
        inc, outg = _directions(sr)
        dcol = "direction" if _has_col(sr, "interactions", "direction") else "null"
        for irow, typ, bundle, t, dev, dirn in db.rows(sr, "select rowid, type, bundleId, startDate, "
                                                       "coalesce(nullif(remoteDeviceId,''),''), %s "
                                                       "from interactions" % dcol) or []:
            k = app_of(bundle)
            if not k:
                continue
            a = A[k]
            a["bundles"].add(bundle)
            a["interactions"] += 1
            if typ == "INSendMessageIntent":
                a["messages"] += 1
            elif typ == "INStartCallIntent":
                a["calls"] += 1
            else:
                a["other"] += 1
            if dev:
                a["devices"].add(dev)
            else:
                a["on_mac"] += 1
            if t is not None:
                a["first"] = t if a["first"] is None else min(a["first"], t)
                a["last"] = t if a["last"] is None else max(a["last"], t)
            ps = params.get(irow, [])
            names = [p for _, p in ps]
            has_sender = any(p.startswith("sender") for p in names)
            has_recip = any(p.startswith("recipient") for p in names)
            if has_sender:
                way = "received"
            elif has_recip:
                way = "sent"
            elif inc is not None and dirn == inc:
                way = "received"
            elif outg is not None and dirn == outg:
                way = "sent"
            else:
                way = "requests"
            a[way] += 1
            group = None
            for erow, p in ps:
                e = ents.get(erow)
                if not e:
                    continue
                etyp, eid, fields = e
                if etyp == "MessageGroup" and p == "speakableGroupName":
                    group = erow
                    a["groups"].add(erow)
                elif etyp in ("Person", "PersonHandle") and p in ("sender", "senderHandle", "recipients",
                                                                  "recipientHandles", "contacts", "contactHandles"):
                    a["people"].add(erow)
                    pids = hmap.get(linkage._n_handle(eid)) if etyp == "PersonHandle" else None
                    if pids:
                        a["named"] |= pids
                    if real:
                        key = ("pid", tuple(sorted(pids))) if pids else ("ent", erow)
                        c = a["by_person"].setdefault(key, {"sent": 0, "received": 0, "other": 0, "last": None,
                                                            "fields": fields, "eid": eid, "etyp": etyp})
                        mine = ("received" if p.startswith("sender") else "sent" if p.startswith("recipient")
                                else way if way in ("sent", "received") else "other")
                        c[mine] += 1
                        c["last"] = t if c["last"] is None else max(c["last"], t or 0)
            if group is not None:
                a["in_groups"] += 1
                if real:
                    g = a["by_group"].setdefault(group, {"count": 0, "last": None})
                    g["count"] += 1
                    g["last"] = t if g["last"] is None else max(g["last"], t or 0)

    # Siri's contact-and-app pairings
    rv = R("siriResolver")
    if db.has_table(rv, "candidates") and db.has_table(rv, "tupleCandidates"):
        for b, tuples in db.rows(rv, "select c.bundleId, count(distinct tc.tupleId) from tupleCandidates tc "
                                 "join candidates c on c.id=tc.candidateId where c.bundleId != '' group by 1") or []:
            k = app_of(b)
            if k:
                A[k]["pairings"] += tuples or 0
                A[k]["bundles"].add(b)
        if db.has_table(rv, "tupleInteractions"):
            for b, n in db.rows(rv, "select c.bundleId, count(*) from tupleInteractions ti join tupleCandidates tc "
                                "on tc.tupleId=ti.tupleId join candidates c on c.id=tc.candidateId "
                                "where c.bundleId != '' group by 1") or []:
                k = app_of(b)
                if k:
                    A[k]["pairing_events"] += n or 0

    # recent two-way contact
    iv = R("internalViews")
    if db.has_table(iv, "bidirectionalPersonInteractionMechanisms"):
        for b, n in db.rows(iv, "select bundleID, count(*) from bidirectionalPersonInteractionMechanisms group by 1") or []:
            k = app_of(b)
            if k:
                A[k]["two_way"] += n or 0

    names = {}
    if real:
        from . import reveal
        pids = set()
        for a in A.values():
            for key in a["by_person"]:
                if key[0] == "pid":
                    pids |= set(key[1])
        names = reveal.names_for(pids)
        gnames = {}
        for erow, (etyp, eid, fields) in (ents.items() if measured_history else []):
            if etyp == "MessageGroup":
                gnames[erow] = _field(fields, "name") or eid

    out = []
    for a in A.values():
        seen = bool(a["installed"] or a["interactions"] or a["pairings"] or a["two_way"])
        if not (seen or a["watch"]):
            continue
        app = {
            "key": a["key"], "product": a["product"], "kind": a["kind"], "watch": a["watch"], "seen": seen,
            "installed_on_mac": bool(a["installed"]),
            "bundles": sorted(a["bundles"]),
            "interactions": a["interactions"], "messages": a["messages"], "calls": a["calls"], "other": a["other"],
            "sent": a["sent"], "received": a["received"], "requests": a["requests"],
            "in_groups": a["in_groups"], "group_chats": len(a["groups"]),
            "people": len(a["people"]), "named_on_this_mac": len(a["named"]),
            "other_devices": len(a["devices"]), "from_this_mac": a["on_mac"],
            "first": _iso(a["first"]), "last": _iso(a["last"]),
            "pairings": a["pairings"], "pairing_events": a["pairing_events"], "two_way": a["two_way"],
            "status": _status(a, measured_history), "story": _story(a, measured_history),
        }
        if real:
            ppl = []
            for key, c in a["by_person"].items():
                if key[0] == "pid":
                    nm = " / ".join(sorted(set(names.get(p) or "(no name)" for p in key[1])))
                else:
                    nm = _field(c["fields"], "name") or c["eid"]
                ppl.append({"name": nm, "sent": c["sent"], "received": c["received"], "other": c["other"],
                            "total": c["sent"] + c["received"] + c["other"], "last": _iso(c["last"]),
                            "profile": key[1][0] if key[0] == "pid" and len(key[1]) == 1 else None})
            merged = {}
            for p in ppl:
                m = merged.setdefault((p["name"], p["profile"]), dict(p, sent=0, received=0, other=0, total=0, last=None))
                for f in ("sent", "received", "other", "total"):
                    m[f] += p[f]
                m["last"] = max(filter(None, [m["last"], p["last"]]), default=None)
            app["top_people"] = sorted(merged.values(), key=lambda x: -x["total"])[:25]
            app["group_names"] = sorted(({"name": gnames.get(g, "(unnamed)"), "count": v["count"], "last": _iso(v["last"])}
                                         for g, v in a["by_group"].items()), key=lambda x: -x["count"])[:25]
        if a["key"] == "messages":
            app["note"] = IMESSAGE
        out.append(app)
    out.sort(key=lambda x: (not x["watch"] and not x["interactions"], KIND_ORDER.index(x["kind"]), -x["interactions"]))
    total = sum(x["interactions"] for x in out)
    priv = [x for x in out if x["kind"] == PRIVATE and x["interactions"]]
    return {"real": bool(real), "apps": out, "measured_history": measured_history,
            "headline": _headline(out, total, priv, measured_history),
            "kinds": KIND_ORDER}


def _field(fields, key):
    import json
    try:
        return json.loads(fields or "{}").get(key)
    except Exception:
        return None


def _status(a, measured):
    if a["interactions"]:
        return "logged"
    if a["installed"] or a["pairings"] or a["two_way"]:
        return "present, nothing logged"
    return "no trace" if measured else "not measured"


def _n(n, one, many=None):
    return "%d %s" % (n, one if n == 1 else (many or one + "s"))


def _story(a, measured):
    s = []
    if not measured:
        s.append("Siri's history could not be read, so activity is not measured.")
    if a["interactions"]:
        where = []
        if a["devices"]:
            where.append("from %s" % _n(len(a["devices"]), "other device"))
        if a["on_mac"]:
            where.append("%d from this Mac" % a["on_mac"])
        s.append("Siri's history on this Mac holds %s for %s between %s and %s, %s." % (
            _n(a["interactions"], "interaction"), a["product"], _iso(a["first"]), _iso(a["last"]), ", ".join(where)))
        parts = [x for x in (_n(a["messages"], "message") if a["messages"] else None,
                             _n(a["calls"], "call") if a["calls"] else None,
                             _n(a["other"], "other request") if a["other"] else None) if x]
        tail = ", and %d with no direction" % a["requests"] if a["requests"] else ""
        s.append("That is %s: %d outgoing and %d incoming%s." % (" and ".join(parts), a["sent"], a["received"], tail))
        if a["received"] and not a["sent"]:
            s.append("Every row is incoming. Nothing you sent in %s reached these stores, only what you received."
                     % a["product"])
        elif a["sent"] and not a["received"]:
            s.append("Every row is outgoing. Nothing you received in %s reached these stores." % a["product"])
        if a["groups"]:
            share = round(100.0 * a["in_groups"] / a["interactions"])
            s.append("%d%% of it is in %s. Siri keeps each group's name." % (share, _n(len(a["groups"]), "group chat")))
        elif a["messages"]:
            s.append("None of it is tagged to a group chat.")
        s.append("It names %s; %s of them resolve to a named person on this Mac." % (
            _n(len(a["people"]), "person or handle", "people or handles"), len(a["named"])))
    if a["pairings"]:
        s.append("Siri holds %s pairing a contact with %s, used %d times. That is its record of which app you use "
                 "for whom." % (_n(a["pairings"], "pairing"), a["product"], a["pairing_events"]))
    if a["two_way"]:
        s.append("The recent two-way contact table has %s through it." % _n(a["two_way"], "row"))
    if a["installed"]:
        s.append("Installed on this Mac.")
    if not (a["interactions"] or a["pairings"] or a["two_way"]):
        s.append(NOTHING if not a["installed"] else
                 "Installed, but nothing it did reached these stores. It may not hand its activity to Siri, or its "
                 "Siri setting may be off. These stores cannot tell which.")
    return s


def _headline(apps, total, priv, measured):
    if not measured:
        return "Siri's history could not be read, so messaging activity is not measured."
    logged = [a for a in apps if a["interactions"]]
    s = "Siri's history on this Mac holds %d messaging and calling interactions across %s." % (
        total, _n(len(logged), "app"))
    if priv:
        s += " Private messengers: " + ", ".join("%s %d" % (a["product"], a["interactions"]) for a in priv) + "."
    quiet = [a["product"] for a in apps if a["watch"] and not a["seen"]]
    if quiet:
        s += " No trace of " + ", ".join(quiet) + "."
    return s
