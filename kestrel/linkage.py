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


def run():
    """Nodes, edges and bridge counts. Counts only."""
    sets = {}
    sql_of = {}
    for space, store, table, sql, norm in MEMBERS:
        s = _load(store, table, sql, norm)
        sets[(space, store)] = s
        sql_of[(space, store)] = sql

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
            reach = len(set(i for h, i in rs if _n_handle(h) in sh))

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

    sets.clear()  # identifiers do not outlive the call
    return {"spaces": [{"id": a, "label": b, "about": c} for a, b, c in SPACES],
            "nodes": sorted(nodes.values(), key=lambda n: (n["group"], n["id"])),
            "edges": edges,
            "bridge": {"phone_history_to_graph_people": reach},
            "sql": [{"space": sp, "store": st, "sql": q} for (sp, st), q in sql_of.items()]}
