"""web.py: the spider map. You at the centre, and everyone the Mac links to you.

One builder, two modes:

  real=False  safe for a screen share. People are "Person 1", "Person 2" in order
              of how much the Mac holds on them; employers are "Employer A".
              No names, numbers, addresses or ids leave this module, and app
              ids pass through catalog.display.
  real=True   names, places, aliases and apps as stored. Only ever served
              through /api/reveal/web.

Every line on the map is a link the Mac itself holds or computed:

  messages     Siri history synced from your devices names this person as a
               sender or recipient. Weight: interactions.
  scored       the Mac's relationship score names a relation at 0.5 or more.
  family       iCloud Family Sharing membership.
  household    the features store flags a shared home address.
  flagged      a favorite, an emergency contact, or a relationship label.
  employer     the graph holds an employment statement (person to employer).

Direction comes from who is listed on each interaction, not Siri's direction
code: a row naming them as sender is a message you received; a row naming them
only as recipient, with no sender on the row, is one you sent; a recipient on a
row that also names a sender is a group message they were in.
"""

import datetime
import math

from . import catalog, db, linkage
from .stores import BY_ID

R = lambda sid: BY_ID[sid][1]  # noqa: E731

TAGS = ["mother", "father", "parent", "sister", "brother", "sibling", "family", "partner",
        "child", "son", "daughter", "friend", "coworker", "alumni"]
FAMILY = {"mother", "father", "parent", "sister", "brother", "sibling", "family", "child", "son", "daughter"}

ROLES = [
    ("you", "You, the owner of this Mac"),
    ("partner", "Scored as your partner"),
    ("family", "Family, by score or Family Sharing"),
    ("friend", "Scored as a friend"),
    ("coworker", "Scored as a coworker"),
    ("talk", "Someone you message or call"),
    ("marked", "Marked by you or sharing your home, no messages"),
    ("known", "Known to the Mac, no link to you"),
    ("org", "An employer"),
]
KINDS = [
    ("messages", "Messages and calls in your Siri history"),
    ("scored", "The Mac's relationship score, 0.5 or more"),
    ("family", "iCloud Family Sharing"),
    ("household", "Flagged as sharing your home address"),
    ("flagged", "Favorite, emergency contact, or labeled"),
    ("employer", "Works at, per the graph"),
]
SCORE_CUT = 0.5


def _iso(t):
    try:
        return (datetime.datetime(2001, 1, 1) + datetime.timedelta(seconds=float(t))).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        return None


def _md(x):
    s = str(x)
    return s[3:] if s.startswith("md:") else s


def _norm_contact(x):
    s = str(x or "")
    if s.startswith("cnContact:"):
        s = s[10:]
    return s.split(":")[0].upper()


def _rows(sid, table, sql, params=()):
    if not db.has_table(R(sid), table):
        return None
    return db.rows(R(sid), sql, params)


def _people_and_owner():
    rs = _rows("graph", "stable_graph", "select distinct subject from stable_graph where predicate='PS1' "
               "and relationshipPredicate='' and object='SB104'") or []
    people = set(str(r[0]) for r in rs)
    return people - linkage._owner(), (sorted(linkage._owner()) or [None])[0]


def _comms(people):
    """Per person: sent, received, group, total, apps, first, last. One pass over Siri history."""
    out = {}
    if not db.has_table(R("siriRemembers"), "interactions"):
        return None
    hmap = {}
    for h, i in _rows("internalViews", "handle_id", "select handle, id from handle_id") or []:
        n = linkage._n_handle(h)
        if n and str(i) in people:
            hmap.setdefault(n, set()).add(str(i))
    cmap = {}
    for s, o in _rows("graph", "stable_graph", "select subject, object from stable_graph where predicate='PS102' "
                      "and object like 'cnContact:%'") or []:
        if str(s) in people:
            cmap.setdefault(_norm_contact(o), set()).add(str(s))
    ent = {}
    for rowid, eid, typ in db.rows(R("siriRemembers"), "select rowid, id, type from entities "
                                   "where type in ('Person','PersonHandle')") or []:
        pids = hmap.get(linkage._n_handle(eid)) if typ == "PersonHandle" else cmap.get(_norm_contact(eid))
        if pids:
            ent[rowid] = pids
    if not ent:
        return out
    has_sender = set(r[0] for r in db.rows(R("siriRemembers"), "select distinct interactionRowid from interactionEntities "
                                           "where parameter in ('sender','senderHandle')") or [])
    roles = {}
    meta = {}
    q = ("select x.interactionRowid, x.entityRowid, x.parameter, i.bundleId, i.startDate from interactionEntities x "
         "join interactions i on i.rowid=x.interactionRowid "
         "where x.parameter in ('sender','senderHandle','recipients','recipientHandles','contacts','contactHandles')")
    for irow, erow, param, app, t in db.rows(R("siriRemembers"), q) or []:
        pids = ent.get(erow)
        if not pids:
            continue
        for pid in pids:
            roles.setdefault((pid, irow), set()).add("s" if param.startswith("sender") else
                                                     ("r" if param.startswith("recipient") else "c"))
        meta[irow] = (app, t)
    for (pid, irow), rs in roles.items():
        o = out.setdefault(pid, {"sent": 0, "received": 0, "group": 0, "requests": 0, "total": 0, "apps": {},
                                 "first": None, "last": None})
        if "s" in rs:
            o["received"] += 1
        elif "r" not in rs:
            o["requests"] += 1
        elif irow in has_sender:
            o["group"] += 1
        else:
            o["sent"] += 1
        o["total"] += 1
        app, t = meta[irow]
        o["apps"][app] = o["apps"].get(app, 0) + 1
        if t is not None:
            o["first"] = t if o["first"] is None else min(o["first"], t)
            o["last"] = t if o["last"] is None else max(o["last"], t)
    return out


def _scores(people):
    out = {}
    if not db.has_table(R("entityTagging"), "entity_tagging"):
        return out
    c = db.connect(R("entityTagging"))
    cur = c.execute("select * from entity_tagging")
    cols = [d[0] for d in cur.description]
    for row in cur.fetchall():
        r = dict(zip(cols, row))
        pid = _md(r.get("mdid"))
        if pid in people:
            out[pid] = {t: round(float(r[t]), 3) for t in TAGS if isinstance(r.get(t), (int, float)) and r[t] > 0}
    return out


def _flags(people):
    out = {}
    for e, fav, emer, fam, lab in _rows("importance", "entityImportanceSignalsIDMap",
                                        "select entityIdentifier, isFavorite, isEmergencyContact, isICloudFamily, "
                                        "relationshipLabel from entityImportanceSignalsIDMap") or []:
        pid = _md(e)
        if pid in people:
            out[pid] = {"favorite": bool(fav), "emergency": bool(emer), "icloud_family": bool(fam),
                        "label": lab or None}
    return out


def _household(people):
    out = set()
    for (s,) in _rows("features", "kv", "select distinct subidentifierName from kv where featureName='sharesHomeAddress'") or []:
        if _md(s) in people:
            out.add(_md(s))
    return out


def _graph_bits(people):
    """Employers, places, birthdays, face links, and how many stores hold each person."""
    emp, places, bday, face = {}, {}, set(), set()
    for s, o in _rows("graph", "stable_graph", "select subject, object from stable_graph where predicate='PS500' "
                      "and relationshipPredicate='PS45'") or []:
        if str(s) in people:
            emp.setdefault(str(s), set()).add(_md(o))
    lab = {}
    for s, rid, o in _rows("graph", "stable_graph", "select subject, relationshipId, object from stable_graph "
                           "where predicate='PS225' and relationshipPredicate='PS733'") or []:
        lab[(str(s), rid)] = "home" if "Home" in str(o) else ("work" if "Work" in str(o) else "other")
    for s, rid, o in _rows("graph", "stable_graph", "select subject, relationshipId, object from stable_graph "
                           "where predicate='PS225' and relationshipPredicate='PS107'") or []:
        if str(s) in people:
            places.setdefault(str(s), []).append((lab.get((str(s), rid), "other"), _md(o)))
    for (s,) in _rows("graph", "stable_graph", "select distinct subject from stable_graph "
                      "where predicate in ('PS37','nm_imputedBirthday')") or []:
        bday.add(str(s))
    for (s,) in _rows("graph", "stable_graph", "select distinct subject from stable_graph "
                      "where predicate='nm_hasVisualIdentifier'") or []:
        face.add(str(s))
    sets, _ = linkage.load_sets()
    stores = {}
    for (space, store), s in sets.items():
        if space != "entity" or s is None:
            continue
        for pid in s & people:
            stores.setdefault(pid, set()).add(store)
    sets.clear()
    return emp, places, bday, face, stores


def _names(ids):
    from . import reveal
    return reveal.names_for(ids)


def _place_text(md_id):
    from . import reveal
    p = reveal._place(md_id, reveal._labels()) or {}
    bits = [p.get(k) for k in ("full street address", "city", "administrative district", "postal code") if p.get(k)]
    return ", ".join(dict.fromkeys(bits)) or p.get("name")


def _aliases(people):
    out = {}
    for m, a in _rows("ecr", "asr_entity_alias", "select MD_ID, alias from asr_entity_alias") or []:
        pid = _md(m)
        if pid in people:
            out.setdefault(pid, []).append(a)
    return out


def _role(sc, fl, fam_member, comms, household=False):
    top = max(sc.items(), key=lambda kv: kv[1]) if sc else (None, 0)
    if sc.get("partner", 0) >= SCORE_CUT or (fl or {}).get("label") in ("Spouse", "Partner", "_$!<Spouse>!$_", "_$!<Partner>!$_"):
        return "partner"
    if fam_member or any(sc.get(t, 0) >= SCORE_CUT for t in FAMILY):
        return "family"
    if sc.get("friend", 0) >= SCORE_CUT:
        return "friend"
    if sc.get("coworker", 0) >= SCORE_CUT or sc.get("alumni", 0) >= SCORE_CUT:
        return "coworker"
    if comms:
        return "talk"
    if household or (fl and (fl["favorite"] or fl["emergency"] or fl["label"])):
        return "marked"
    return "known"


def _apps_text(apps, real):
    top = sorted(apps.items(), key=lambda kv: -kv[1])[:3]
    return ", ".join("%s (%d)" % (a if real else catalog.display(a), n) for a, n in top)


def build(real=False, scope="linked", limit=80):
    """scope: 'linked' (anyone with a line to you), 'talk' (only people in your Siri history), 'all'."""
    people, owner = _people_and_owner()
    comms = _comms(people)
    comms_measured = comms is not None
    comms = comms or {}
    scores = _scores(people)
    flags = _flags(people)
    house = _household(people)
    emp, places, bday, face, stores = _graph_bits(people)
    aliases = _aliases(people) if real else {}

    P = {}
    for pid in people:
        sc = scores.get(pid, {})
        fl = flags.get(pid)
        cm = comms.get(pid)
        strong = {k: v for k, v in sc.items() if v >= SCORE_CUT}
        flagged = bool(fl and (fl["favorite"] or fl["emergency"] or fl["label"]))
        fam = bool(fl and fl["icloud_family"])
        linked = bool(cm or strong or fam or flagged or pid in house)
        P[pid] = {"comms": cm, "scores": sc, "strong": strong, "flags": fl, "family": fam, "flagged": flagged,
                  "household": pid in house, "linked": linked, "role": _role(sc, fl, fam, cm, pid in house),
                  "stores": sorted(stores.get(pid, set())), "employers": sorted(emp.get(pid, set())),
                  "places": places.get(pid, []), "birthday": pid in bday, "face": pid in face}

    if scope == "talk":
        pool = [p for p in P if P[p]["comms"]]
    elif scope == "all":
        pool = list(P)
    else:
        pool = [p for p in P if P[p]["linked"]]

    def rank(pid):
        x = P[pid]
        named_tie = bool(x["strong"] or x["family"] or x["flagged"] or x["household"])
        return (named_tie, (x["comms"] or {}).get("total", 0), len(x["stores"]))
    pool.sort(key=rank, reverse=True)
    shown = pool[:max(1, int(limit))]

    names = _names(shown + [owner] + [o for p in shown for o in P[p]["employers"]]) if real else {}
    label = {}
    for i, pid in enumerate(shown):
        label[pid] = (names.get(pid) or "(no name)") if real else "Person %d" % (i + 1)
    orgs = sorted(set(o for p in shown for o in P[p]["employers"]))
    for i, o in enumerate(orgs):
        label["org:" + o] = (names.get(o) or "(unnamed employer)") if real else "Employer %s" % _letters(i)

    nid = (lambda pid: pid) if real else (lambda pid: "p%d" % (shown.index(pid) + 1))
    oid = (lambda o: "org:" + o) if real else (lambda o: "o%d" % (orgs.index(o) + 1))
    you = owner if real and owner else "you"

    nodes = [{"id": you, "label": (names.get(owner) or "You") if real else "You", "role": "you",
              "weight": max([len(P[p]["stores"]) for p in shown] + [1]) + 2, "kind": "you",
              "story": _owner_story(P, shown, comms_measured)}]
    links = []
    for pid in shown:
        x = P[pid]
        nodes.append({"id": nid(pid), "label": label[pid], "role": x["role"], "kind": "person",
                      "weight": len(x["stores"]) + 1,
                      "story": _story(pid, x, label, real, names, oid) + (
                          ["Siri listens for: %s." % ", ".join(sorted(set(aliases[pid]))[:8])] if real and aliases.get(pid) else []),
                      "profile": pid if real else None})
        cm = x["comms"]
        if cm:
            links.append({"source": you, "target": nid(pid), "kind": "messages", "count": cm["total"],
                          "weight": round(2 * math.log10(cm["total"] + 1), 2),
                          "tip": "%d interactions: %d you sent, %d you received, %d group, %d requests naming them" %
                                 (cm["total"], cm["sent"], cm["received"], cm["group"], cm["requests"])})
        if x["strong"]:
            k, v = max(x["strong"].items(), key=lambda kv: kv[1])
            links.append({"source": you, "target": nid(pid), "kind": "scored", "weight": round(v * 8, 2),
                          "tip": "Scored as %s, %.2f" % (k, v)})
        if x["family"]:
            links.append({"source": you, "target": nid(pid), "kind": "family", "weight": 6, "tip": "iCloud Family Sharing"})
        if x["household"]:
            links.append({"source": you, "target": nid(pid), "kind": "household", "weight": 6,
                          "tip": "Flagged as sharing your home address"})
        if x["flagged"]:
            f = x["flags"]
            what = [w for w, on in (("favorite", f["favorite"]), ("emergency contact", f["emergency"])) if on]
            if f["label"]:
                what.append("labeled" + (" " + _clean_label(f["label"]) if real else ""))
            links.append({"source": you, "target": nid(pid), "kind": "flagged", "weight": 6, "tip": ", ".join(what)})
        for o in x["employers"]:
            links.append({"source": nid(pid), "target": oid(o), "kind": "employer", "weight": 3, "tip": "Works at"})
    for o in orgs:
        n = sum(1 for p in shown if o in P[p]["employers"])
        nodes.append({"id": oid(o), "label": label["org:" + o], "role": "org", "kind": "org", "weight": n,
                      "story": ["%s of the people on this map work here, per the graph." % n]})

    linked_all = sum(1 for p in P if P[p]["linked"])
    talk_all = sum(1 for p in P if P[p]["comms"])
    return {
        "real": bool(real), "scope": scope, "limit": int(limit),
        "nodes": nodes, "links": links, "roles": [{"id": a, "label": b} for a, b in ROLES],
        "kinds": [{"id": a, "label": b} for a, b in KINDS],
        "counts": {"people": len(P), "linked": linked_all, "talk": talk_all, "pool": len(pool), "shown": len(shown),
                   "employers": len(orgs), "by_role": _by(P, shown, "role"),
                   "comms_measured": comms_measured},
        "headline": _headline(P, linked_all, talk_all, comms_measured),
    }


def _cap(s):
    """Capitalize the first letter only, so a name keeps its own casing."""
    s = str(s)
    return s[:1].upper() + s[1:]


def _letters(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _by(P, shown, key):
    out = {}
    for p in shown:
        out[P[p][key]] = out.get(P[p][key], 0) + 1
    return out


def _clean_label(lab):
    s = str(lab or "")
    return s.replace("_$!<", "").replace(">!$_", "").lower()


def _headline(P, linked, talk, measured):
    total = sum((P[p]["comms"] or {}).get("total", 0) for p in P)
    if not measured:
        return ("Your Mac knows %d people. %d of them it links to you. Your Siri history could not be read, "
                "so who you message is not measured." % (len(P), linked))
    return ("Your Mac knows %d people. It links %d of them to you, and %d of those appear in your message and call "
            "history: %d interactions in all." % (len(P), linked, talk, total))


def _owner_story(P, shown, measured):
    talk = [p for p in shown if P[p]["comms"]]
    s = ["This is you. Every line from here is a link your Mac holds between you and someone else."]
    if measured:
        s.append("%d of the people on this map are in your message and call history." % len(talk))
    strong = sum(1 for p in shown if P[p]["strong"])
    if strong:
        s.append("The Mac has scored %d of them as family, a partner, a friend or a coworker, mostly without "
                 "you ever saying so." % strong)
    return s


def _story(pid, x, label, real, names, oid):
    """The plain-language explanation for one person. Counts in safe mode, values in real mode."""
    who = label[pid] if real else "this person"
    s = []
    cm = x["comms"]
    if cm:
        span = ""
        if cm["first"] and cm["last"]:
            span = " between %s and %s" % (_iso(cm["first"]), _iso(cm["last"]))
        s.append("Your phone's history, synced to this Mac, logs %d interactions with %s%s: %d you sent, "
                 "%d you received, %d group messages they were in, and %d requests that named them "
                 "(\"call\", \"find\", \"share with\")." %
                 (cm["total"], who, span, cm["sent"], cm["received"], cm["group"], cm["requests"]))
        s.append("Mostly in: %s." % _apps_text(cm["apps"], real))
    else:
        s.append("Nothing in your message and call history is joined to %s." % who)
    if x["strong"]:
        parts = ", ".join("%s %.2f" % (k, v) for k, v in sorted(x["strong"].items(), key=lambda kv: -kv[1]))
        s.append("The Mac scores %s as: %s. You did not enter this; it inferred it." % (who, parts))
    elif x["scores"]:
        k, v = max(x["scores"].items(), key=lambda kv: kv[1])
        s.append("The Mac's strongest guess about %s is %s, at %.2f, below the 0.5 line." % (who, k, v))
    if x["family"]:
        s.append("%s is in your iCloud Family Sharing group." % _cap(who))
    if x["household"]:
        s.append("The Mac flags %s as sharing your home address." % who)
    if x["flagged"]:
        f = x["flags"]
        bits = [w for w, on in (("a favorite", f["favorite"]), ("an emergency contact", f["emergency"])) if on]
        if f["label"]:
            bits.append("labeled %s" % _clean_label(f["label"]) if real else "given a relationship label")
        s.append("You marked %s as %s." % (who, " and ".join(bits)))
    if x["places"]:
        if real:
            for kind, md in x["places"][:3]:
                t = _place_text(md)
                if t:
                    s.append("%s address on file: %s." % (kind.capitalize(), t))
        else:
            s.append("The Mac holds %d address(es) for this person: %s." %
                     (len(x["places"]), ", ".join(sorted(set(k for k, _ in x["places"])))))
    if x["employers"]:
        if real:
            s.append("Works at: %s." % ", ".join(names.get(o) or "(unnamed)" for o in x["employers"]))
        else:
            s.append("The graph names an employer for this person.")
    if x["birthday"]:
        s.append("It holds a birthday, real or estimated.")
    if x["face"]:
        s.append("Photos holds a face cluster linked to %s." % who)
    s.append("%s appears in %d store(s) on this Mac: %s." % (_cap(who), len(x["stores"]), ", ".join(x["stores"]) or "none"))
    return s
