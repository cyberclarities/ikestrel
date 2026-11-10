"""linkage.py: how the stores join, measured as overlaps between identifier sets.

Five identifier spaces tie the stores together:

  entity   the graph's 64-bit entity id. About seventeen stores key on it, so
           it is drawn as a hub: each store links to graph.db, weighted by how
           many of its ids the graph also holds.
  contact  a Contacts UUID (any ":ABPerson" style suffix dropped). Contact UUIDs
           differ per device, so history synced from a phone matches poorly here.
  handle   a phone number (last ten digits) or an email address, lowercased.
           This is the bridge that joins a phone's history to people on the Mac.
  face     a Photos face-cluster id.
  device   a remote device UUID.

Identifier sets live only in memory for the length of one call. Nothing in the
result is an identifier: only store ids, space names, and counts.
"""

import re

from . import db
from .stores import BY_ID
from . import dossier

SPACES = [
    ("entity", "Entity id", "The graph's own id for a person, place, app or organization."),
    ("contact", "Contact UUID", "The Contacts record id. It differs between devices."),
    ("handle", "Phone or email", "Normalized phone numbers and email addresses."),
    ("face", "Face cluster", "A Photos face-cluster id."),
    ("device", "Device id", "The id of another device whose data is synced here."),
]

_PHONE = re.compile(r"\D")
_DEVICE = re.compile(r":remotes:([0-9A-Fa-f-]{36})")


def _n_text(v):
    return None if v is None else str(v)


def _n_md(v):
    if v is None:
        return None
    s = str(v)
    return s[3:] if s.startswith("md:") else s


def _n_contact(v):
    if not v:
        return None
    s = str(v)
    for p in ("cnContact:",):
        if s.startswith(p):
            s = s[len(p):]
    return s.split(":")[0].upper() or None


def _n_handle(v):
    s = (v or "").strip().lower()
    if not s:
        return None
    if "@" in s:
        return s
    d = _PHONE.sub("", s)
    return d[-10:] if len(d) >= 10 else None


def _n_device(v):
    if not v:
        return None
    m = _DEVICE.search(str(v))
    return (m.group(1) if m else str(v)).upper()


# (space, store, table, sql, normalizer)
MEMBERS = [
    ("entity", "graph", "stable_graph", "select distinct subject from stable_graph", _n_text),
    ("entity", "internalViews", "people_subgraph", "select distinct subject from people_subgraph", _n_text),
    ("entity", "ecr", "entity_summary", "select distinct MD_ID from entity_summary", _n_md),
    ("entity", "euclid", "attributes", "select distinct MD_ID from attributes", _n_md),
    ("entity", "entityTagging", "entity_tagging", "select distinct mdid from entity_tagging", _n_md),
    ("entity", "features", "kv", "select distinct subidentifierName from kv where subidentifierName != ''", _n_md),
    ("entity", "importance", "entityImportanceSignalsIDMap",
     "select distinct entityIdentifier from entityImportanceSignalsIDMap", _n_md),
    ("entity", "clients", "siriPerson", "select distinct subject from siriPerson", _n_text),
    ("entity", "visualIdentifier", "people", "select distinct subject from people", _n_text),
    ("entity", "photosAutonaming", "subgraph", "select distinct subject from subgraph", _n_text),
    ("entity", "lifeEvent", "lifeEvent_subgraph", "select distinct subject from lifeEvent_subgraph", _n_text),
    ("entity", "futureLifeEvent", "futureLifeEvent_subgraph",
     "select distinct subject from futureLifeEvent_subgraph", _n_text),
    ("contact", "graph", "stable_graph",
     "select object from stable_graph where predicate='PS102' and object like 'cnContact:%'", _n_contact),
    ("contact", "siriRemembers", "entities", "select id from entities where type='Person'", _n_contact),
    ("contact", "siriResolver", "candidates", "select uuid from candidates", _n_contact),
    ("contact", "ecr", "asr_entity_alias", "select distinct contact_identifier from asr_entity_alias", _n_contact),
    ("handle", "internalViews", "handle_id", "select handle from handle_id", _n_handle),
    ("handle", "siriRemembers", "entities", "select id from entities where type='PersonHandle'", _n_handle),
    ("face", "keyvalue", "keyvalue",
     "select key from keyvalue where domain='VisionSignalsEntityToVision'", _n_text),
    ("face", "visualIdentifier", "people",
     "select object from people where relationshipPredicate='nm_visualIdentifier'", _n_text),
    ("face", "graph", "stable_graph",
     "select object from stable_graph where relationshipPredicate='nm_visualIdentifier'", _n_text),
    ("face", "internalViews", "phperson_id_map", "select phPersonIdentifier from phperson_id_map", _n_text),
    ("device", "siriRemembers", "interactions",
     "select distinct remoteDeviceId from interactions where coalesce(remoteDeviceId,'') != ''", _n_device),
    ("device", "siriResolver", "events",
     "select distinct remoteDeviceId from events where coalesce(remoteDeviceId,'') != ''", _n_device),
    ("device", "views", "sourceState",
     "select sourceIdentifier from sourceState where sourceIdentifier like '%:remotes:%'", _n_device),
]

HUB = ("entity", "graph")

TAG_COLS = ["mother", "father", "parent", "sister", "brother", "sibling", "family", "partner",
            "child", "son", "daughter", "friend", "coworker"]

# What a join gives someone who holds both stores. Keyed by key type and store pair.
EDGE_NOTES = {
    ("handle", "internalViews", "siriRemembers"):
        "The bridge. The phone's history stores handles; this Mac maps handles to people. Together they "
        "put names, addresses, employers and relationship scores on the phone's contact timeline, and "
        "faces too once Photos ties them to contacts.",
    ("contact", "siriRemembers", "siriResolver"):
        "Both come from the same device, so contact ids match. Joined, they show which app the owner "
        "habitually uses for each person.",
    ("contact", "graph", "siriRemembers"):
        "Few matches, because Contacts gives each device its own ids. Do not read the low number as "
        "safety: the handle join does the same job.",
    ("contact", "graph", "ecr"):
        "Ties each contact to the spoken forms of their name Siri listens for.",
    ("entity", "entityTagging", "graph"):
        "Attaches a relationship score (parent, partner, friend, coworker) to every person in the graph.",
    ("entity", "features", "graph"):
        "Attaches the evidence behind the scores: shared surname, shared address, shared email domain, age.",
    ("entity", "importance", "graph"):
        "Marks favorites, emergency contacts and family on the graph's people.",
    ("entity", "visualIdentifier", "graph"):
        "Puts a Photos face cluster next to each person's name and contact details.",
    ("entity", "photosAutonaming", "graph"):
        "Proposes names for faces the owner never named.",
    ("entity", "clients", "graph"):
        "The Siri person view: names and employers per contact.",
    ("entity", "ecr", "graph"):
        "Apple's per-person summary of linked people, places and events.",
    ("entity", "futureLifeEvent", "graph"):
        "Geocoded addresses the system watches for life events.",
    ("face", "graph", "keyvalue"):
        "The face-to-person map. With the Photos library, it names everyone the system recognizes.",
    ("device", "siriRemembers", "views"):
        "Confirms which other devices feed this Mac, and when each last synced.",
}

SPACE_NOTES = {
    "entity": "Shares the graph's entity ids, so every fact in one store attaches to the same person in the other.",
    "contact": "Shares Contacts record ids. Matches well only when both stores come from the same device.",
    "handle": "Shares phone numbers and email addresses, which are the same on every device.",
    "face": "Shares Photos face-cluster ids.",
    "device": "Shares the ids of other devices synced to this Mac.",
}


def _note(space, a, b):
    k = (space,) + tuple(sorted((a, b)))
    for key, text in EDGE_NOTES.items():
        if (key[0],) + tuple(sorted(key[1:])) == k:
            return text
    return SPACE_NOTES.get(space, "")


def _ids(store, table, sql):
    rel = BY_ID[store][1]
    if not db.has_table(rel, table):
        return None
    rs = db.rows(rel, sql)
    return None if rs is None else set(_n_md(r[0]) for r in rs if r[0] is not None)


def _owner():
    """The Mac owner's entity id, so chains count the people the owner talks to, not the owner."""
    if not db.has_table("graph.db", "stable_graph"):
        return set()
    rs = db.rows("graph.db", "select distinct subject from stable_graph where predicate='nm_isCurrentUser'") or []
    return set(str(r[0]) for r in rs)


def _chains(sets, keep=None):
    """Funnels across stores. Each step is a count; identifiers never leave this function."""
    G = "select distinct subject from stable_graph where predicate"
    named = _ids("graph", "stable_graph", G + "='PS33'")
    # people point to a home or work place (PS225); the place carries the street address (PS317)
    addr = _ids("graph", "stable_graph", G + "='PS225'")
    face_matched = _ids("graph", "stable_graph",
                        "select distinct subject from stable_graph where relationshipPredicate='nm_associationReason' "
                        "and object != 'association:identifierNoMatch' union select distinct subject from stable_graph "
                        "where predicate='PS102' and object like 'cnContact:%' and subject in (select subject from "
                        "stable_graph where predicate='nm_hasVisualIdentifier')")
    faces = _ids("graph", "stable_graph", G + "='nm_hasVisualIdentifier'")
    bday = _ids("graph", "stable_graph", G + " in ('PS37','nm_imputedBirthday')")
    employer = _ids("graph", "stable_graph", G + "='PS500'")
    phone = _ids("graph", "stable_graph", G + "='PS520' and relationshipPredicate='PS407'")
    tagged = _ids("entityTagging", "entity_tagging", "select mdid from entity_tagging where max(%s) >= 0.5"
                  % ", ".join('"%s"' % c for c in TAG_COLS))
    flagged = _ids("importance", "entityImportanceSignalsIDMap",
                   "select entityIdentifier from entityImportanceSignalsIDMap where isFavorite or "
                   "isEmergencyContact or isICloudFamily or coalesce(relationshipLabel,'') != ''")
    handled = None
    hrows = None
    if db.has_table(BY_ID["internalViews"][1], "handle_id"):
        hrows = db.rows(BY_ID["internalViews"][1], "select handle, id from handle_id")
        if hrows is not None:
            handled = set(str(i) for _, i in hrows)
    sh = sets.get(("handle", "siriRemembers"))
    bridged = None
    if sh is not None and hrows is not None:
        bridged = set(str(i) for h, i in hrows if _n_handle(h) in sh) - _owner()

    def funnel(cid, title, path, start_label, start, steps, explains, hops=None):
        out = [{"label": start_label, "count": None if start is None else len(start)}]
        cur = start
        kept = [None if start is None else set(start)]
        for label, s in steps:
            cur = None if cur is None or s is None else cur & s
            out.append({"label": label, "count": None if cur is None else len(cur)})
            kept.append(None if cur is None else set(cur))
        if keep is not None:
            keep[cid] = kept
        return {"id": cid, "title": title, "path": path, "hops": hops or [], "steps": out, "explains": explains}

    C = [
        funnel("C1", "From the phone's contacts to a profile on this Mac",
               ["siriRemembers", "internalViews", "graph", "entityTagging"],
               "People in the phone's history, matched by phone or email", bridged,
               [("with a name", named), ("and a home or work address", addr),
                ("and a relationship score of 0.5 or higher", tagged)],
               "Starts from the communication history synced from another device. Each step adds one more "
               "store on this Mac. The numbers show how many of the people the owner talks to can be named, "
               "located and placed in the owner's family or social circle from this Mac alone."),
        funnel("C2", "Who the Mac thinks is family, and how to reach them",
               ["entityTagging", "graph", "internalViews", "siriRemembers"],
               "People with a relationship score of 0.5 or higher", tagged,
               [("with a phone number or email", handled), ("and a home or work address", addr),
                ("and in the phone's history", bridged)],
               "Relationship scores the owner never entered, joined to contact details. The last step shows "
               "which inferred relatives the owner actually talks to."),
        funnel("C3", "Faces with names and phone numbers",
               ["keyvalue", "visualIdentifier", "graph"],
               "Face clusters known to the graph", faces,
               [("matched to a contact", face_matched), ("with a phone number", phone)],
               "A recognized face, a name and a number in one place is enough to identify and contact someone "
               "from a photo. A zero at the second step means Photos has not tied any face to a contact on this "
               "Mac yet. The path exists; naming people in Photos fills it."),
        funnel("C4", "The people who matter most",
               ["importance", "graph", "internalViews", "siriRemembers"],
               "People flagged as favorite, emergency contact, family or labeled", flagged,
               [("with a phone number or email", handled), ("and in the phone's history", bridged)],
               "The owner's own markers of importance. These are the people an attacker would impersonate "
               "or approach first."),
        funnel("C5", "Where the people you message work",
               ["siriRemembers", "internalViews", "graph", "clients"],
               "People in the phone's history, matched by phone or email", bridged,
               [("with an employer on record", employer), ("and a birthday", bday)],
               "Maps the owner's day-to-day contacts onto organizations. Useful for pretexting and for "
               "working out the owner's professional network."),
    ]
    hops = {"C1": ["handle", "entity", "entity"], "C2": ["entity", "entity", "handle"], "C3": ["face", "face"],
            "C4": ["entity", "entity", "handle"], "C5": ["handle", "entity", "entity"]}
    for c in C:
        c["hops"] = hops.get(c["id"], [])
    for s in (named, addr, faces, face_matched, bday, employer, phone, tagged, flagged, handled, bridged):
        if s is not None:
            s.clear()
    return C


def _load(store, table, sql, norm):
    rel = BY_ID[store][1]
    if not db.has_table(rel, table):
        if db.connect(rel) is not None:
            db.gap(rel, "table %s missing on this macOS version" % table)
        return None
    rs = db.rows(rel, sql)
    if rs is None:
        return None
    out = set()
    for (v,) in rs:
        n = norm(v)
        if n:
            out.add(n)
    return out


def load_sets():
    sets, sql_of = {}, {}
    for space, store, table, sql, norm in MEMBERS:
        sets[(space, store)] = _load(store, table, sql, norm)
        sql_of[(space, store)] = sql
    return sets, sql_of


def chain_members(cid, step):
    """The entity ids still in view at one step of one chain. For the local reveal view only."""
    sets, _ = load_sets()
    keep = {}
    _chains(sets, keep)
    sets.clear()
    steps = keep.get(cid) or []
    if step < 0 or step >= len(steps) or steps[step] is None:
        return None
    return steps[step]


def run():
    """Nodes, edges and bridge counts. Counts only."""
    sets, sql_of = load_sets()

    edges = []

    def edge(a, b, space):
        A, B = sets.get((space, a)), sets.get((space, b))
        measured = A is not None and B is not None
        edges.append({"a": a, "b": b, "space": space, "measured": measured,
                      "overlap": len(A & B) if measured else None,
                      "a_size": None if A is None else len(A),
                      "b_size": None if B is None else len(B)})

    for (space, store) in sets:
        if space == "entity" and store != "graph":
            edge(store, "graph", "entity")
    for space, _, _ in SPACES:
        if space == "entity":
            continue
        members = [st for (sp, st) in sets if sp == space]
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                edge(members[i], members[j], space)

    # the bridge: how many graph entities a phone's history reaches through handles
    reach = None
    sh = sets.get(("handle", "siriRemembers"))
    if sh is not None and db.has_table(BY_ID["internalViews"][1], "handle_id"):
        rs = db.rows(BY_ID["internalViews"][1], "select handle, id from handle_id")
        if rs is not None:
            reach = len(set(str(i) for h, i in rs if _n_handle(h) in sh) - _owner())

    nodes = {}
    for (space, store), s in sets.items():
        n = nodes.setdefault(store, {"id": store, "group": BY_ID[store][2],
                                     "sensitivity": BY_ID[store][4], "spaces": {}})
        n["spaces"][space] = None if s is None else len(s)
    for sid, (_, path, group, holds, sens) in BY_ID.items():
        if sid not in nodes:
            nodes[sid] = {"id": sid, "group": group, "sensitivity": sens, "spaces": {}}
        nodes[sid]["path"] = path
        nodes[sid]["holds"] = holds
        nodes[sid]["dossier"] = dossier.get(sid)

    chains = _chains(sets)
    for e in edges:
        e["note"] = _note(e["space"], e["a"], e["b"])
    sets.clear()  # identifiers do not outlive the call
    return {"spaces": [{"id": a, "label": b, "about": c} for a, b, c in SPACES],
            "nodes": sorted(nodes.values(), key=lambda n: (n["group"], n["id"])),
            "edges": edges,
            "bridge": {"phone_history_to_graph_people": reach},
            "chains": chains,
            "sql": [{"space": sp, "store": st, "sql": q} for (sp, st), q in sql_of.items()]}
