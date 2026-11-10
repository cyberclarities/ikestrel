"""measure.py: every measurement, counts only.

A measurement returns either one number, or counts grouped by a label that is
not personal: a source name, an intent type, a category, a month, a device
ordinal. No query here selects a name, number, address, network name or
message. Labels that come from the stores (bundle ids) pass through
catalog.display before they leave this module.

Each result carries the SQL behind it, so the technical report can print it.
"""

from . import catalog
from . import db

SOURCE_BITS = [(1, "Contacts"), (32, "Photos"), (256, "Calendar"),
               (8192, "Family Sharing"), (32768, "Installed apps")]

CLASS = {"SB104": "people", "SB10": "organizations", "SB152": "places",
         "SB144": "apps", "SB2": "groups"}

REMOTE = "coalesce(nullif(remoteDeviceId,''),'this Mac')"

_REG = []


def m(mid, store, title):
    def wrap(fn):
        _REG.append((mid, store, title, fn))
        return fn
    return wrap


def _scalar(store, sql, params=()):
    return {"value": db.scalar(db_path(store), sql, params), "sql": sql}


def _groups(store, sql, label=lambda x: x, params=()):
    rs = db.rows(db_path(store), sql, params)
    if rs is None:
        return {"groups": None, "sql": sql}
    out = {}
    for k, n in rs:
        lab = label(k)
        out[lab] = out.get(lab, 0) + (n or 0)
    return {"groups": out, "sql": sql}


def db_path(store):
    from .stores import BY_ID
    return BY_ID[store][1]


def _ok(store, table):
    if db.has_table(db_path(store), table):
        return True
    if db.connect(db_path(store)) is not None:
        db.gap(db_path(store), "table %s missing on this macOS version" % table)
    return False


# --- knowledge graph --------------------------------------------------------

@m("graph.entities", "graph", "Entities in the knowledge graph")
def _():
    if not _ok("graph", "stable_graph"):
        return None
    return _scalar("graph", "select count(distinct subject) from stable_graph")


@m("graph.classes", "graph", "Entities by kind")
def _():
    if not _ok("graph", "stable_graph"):
        return None
    return _groups("graph", "select object, count(distinct subject) from stable_graph "
                   "where predicate='PS1' and relationshipPredicate='' group by object",
                   lambda c: CLASS.get(c, "other kinds"))


@m("graph.by_source", "graph", "Facts by the source they came from")
def _():
    if not _ok("graph", "stable_graph"):
        return None
    sql = "select count(*) from stable_graph where (sources & ?) != 0"
    out = {}
    for bit, name in SOURCE_BITS:
        out[name] = db.scalar(db_path("graph"), sql, (bit,))
    known = sum(b for b, _ in SOURCE_BITS)
    out["Other source bits"] = db.scalar(db_path("graph"),
        "select count(*) from stable_graph where (sources & ~?) != 0", (known,))
    return {"groups": out, "sql": sql + "   -- once per source bit"}


@m("graph.addresses", "graph", "Postal addresses held")
def _():
    if not _ok("graph", "stable_graph"):
        return None
    return _scalar("graph", "select count(distinct relationshipId) from stable_graph where predicate='PS317'")


@m("graph.birthdays", "graph", "People with a birthday or imputed birthday")
def _():
    if not _ok("graph", "stable_graph"):
        return None
    return _scalar("graph", "select count(distinct subject) from stable_graph "
                   "where predicate in ('PS37','nm_imputedBirthday')")


@m("graph.calendar_events", "graph", "Calendar events in the event graph")
def _():
    if not _ok("graph", "event_graph"):
        return None
    return _scalar("graph", "select count(distinct subject) from event_graph where predicate='PS1'")


@m("graph.rebuilt", "graph", "Graph last rebuilt from scratch (date)")
def _():
    if not _ok("graph", "graph_state"):
        return None
    v = db.scalar(db_path("graph"), "select value from graph_state where key='buildFromScratchTimestamp'")
    return {"value": db.apple_date(v), "sql": "select value from graph_state where key='buildFromScratchTimestamp'"}


@m("graph.free_ratio", "graph", "Share of graph.db pages on the free list (percent)")
def _():
    pc = db.scalar(db_path("graph"), "pragma page_count")
    fc = db.scalar(db_path("graph"), "pragma freelist_count")
    v = None if not pc or fc is None else round(100.0 * fc / pc)
    return {"value": v, "sql": "pragma freelist_count; pragma page_count"}


# --- communications ---------------------------------------------------------

@m("comms.interactions", "siriRemembers", "Interactions in Siri's history")
def _():
    if not _ok("siriRemembers", "interactions"):
        return None
    return _scalar("siriRemembers", "select count(*) from interactions")


@m("comms.span", "siriRemembers", "Date range of Siri's history")
def _():
    if not _ok("siriRemembers", "interactions"):
        return None
    sql = "select min(startDate), max(startDate) from interactions"
    r = db.rows(db_path("siriRemembers"), sql)
    if not r:
        return {"value": None, "sql": sql}
    a, b = r[0]
    return {"value": "%s to %s" % (db.apple_date(a), db.apple_date(b)) if a else None, "sql": sql}


@m("comms.months_active", "siriRemembers", "Months with at least 100 interactions")
def _():
    if not _ok("siriRemembers", "interactions"):
        return None
    return _scalar("siriRemembers", "select count(*) from (select strftime('%Y-%m', "
                   "datetime(startDate+978307200,'unixepoch')) mth, count(*) n from interactions "
                   "group by mth having n >= 100)")


@m("comms.by_device", "siriRemembers", "Interactions by device of origin")
def _():
    if not _ok("siriRemembers", "interactions"):
        return None
    sql = ("select %s d, count(*) n from interactions group by d order by n desc" % REMOTE)
    rs = db.rows(db_path("siriRemembers"), sql)
    if rs is None:
        return {"groups": None, "sql": sql}
    out, i = {}, 0
    for d, n in rs:
        if d == "this Mac":
            out["this Mac"] = n
        else:
            i += 1
            out["other device %d" % i] = n
    return {"groups": out, "sql": sql + "   -- device ids replaced by ordinals"}


@m("comms.remote_devices", "siriRemembers", "Other devices whose history is on this Mac")
def _():
    if not _ok("siriRemembers", "interactions"):
        return None
    return _scalar("siriRemembers", "select count(distinct remoteDeviceId) from interactions "
                   "where coalesce(remoteDeviceId,'') != ''")


@m("comms.by_category", "siriRemembers", "Message and call interactions by app category")
def _():
    if not _ok("siriRemembers", "interactions"):
        return None
    return _groups("siriRemembers", "select bundleId, count(*) from interactions "
                   "where type in ('INSendMessageIntent','INStartCallIntent') group by bundleId",
                   catalog.classify)


@m("comms.by_app", "siriRemembers", "Message and call interactions by app")
def _():
    if not _ok("siriRemembers", "interactions"):
        return None
    return _groups("siriRemembers", "select bundleId, count(*) from interactions "
                   "where type in ('INSendMessageIntent','INStartCallIntent') group by bundleId",
                   catalog.display)


@m("comms.by_intent", "siriRemembers", "Interactions by intent type")
def _():
    if not _ok("siriRemembers", "interactions"):
        return None
    return _groups("siriRemembers", "select type, count(*) from interactions group by type",
                   lambda t: t if (t or "").replace("_", "").isalnum() and len(t or "") < 60 else "other")


@m("comms.counterparts", "siriRemembers", "Distinct people and handles on the other side")
def _():
    if not _ok("siriRemembers", "interactionEntities"):
        return None
    return _scalar("siriRemembers", "select count(distinct entityRowid) from interactionEntities "
                   "where parameter in ('sender','recipients','senderHandle','recipientHandles')")


@m("comms.top_share", "siriRemembers", "Share of person links that point at the single most frequent counterpart (percent)")
def _():
    if not _ok("siriRemembers", "interactionEntities"):
        return None
    sql = ("select max(n)*100/sum(n) from (select count(*) n from interactionEntities "
           "where parameter in ('sender','recipients') group by entityRowid)")
    return _scalar("siriRemembers", sql)


@m("comms.message_bodies", "siriRemembers", "Message entities holding more than an identifier")
def _():
    if not _ok("siriRemembers", "entities"):
        return None
    return _scalar("siriRemembers", "select count(*) from entities where type='Message' "
                   "and fields not like '{\"identifier\":%' ")


@m("comms.resolver_events", "siriResolver", "Siri contact-resolution events")
def _():
    if not _ok("siriResolver", "events"):
        return None
    return _scalar("siriResolver", "select count(*) from events")


@m("comms.resolver_candidates", "siriResolver", "Contacts and apps Siri has resolved to")
def _():
    if not _ok("siriResolver", "candidates"):
        return None
    return _scalar("siriResolver", "select count(*) from candidates")


# --- identity and context ---------------------------------------------------

@m("ctx.handles", "internalViews", "Phone numbers and email addresses mapped to people")
def _():
    if not _ok("internalViews", "handle_id"):
        return None
    return _groups("internalViews", "select case when handle like '%@%' then 'email' "
                   "else 'phone or other' end, count(*) from handle_id group by 1")


@m("ctx.wifi_networks", "internalViews", "Distinct Wi-Fi networks in the connect history")
def _():
    if not _ok("internalViews", "wifiContextEvents"):
        return None
    return _scalar("internalViews", "select count(distinct substr(behaviorIdentifier, "
                   "instr(behaviorIdentifier,':')+1)) from wifiContextEvents")


@m("ctx.wifi_events", "internalViews", "Wi-Fi connect and disconnect events")
def _():
    if not _ok("internalViews", "wifiContextEvents"):
        return None
    return _scalar("internalViews", "select count(*) from wifiContextEvents")


@m("ctx.wifi_days", "internalViews", "Days spanned by the Wi-Fi history")
def _():
    if not _ok("internalViews", "wifiContextEvents"):
        return None
    return _scalar("internalViews", "select cast(round((max(timestamp)-min(timestamp))/86400.0) as int) "
                   "from wifiContextEvents")


@m("ctx.speech_aliases", "ecr", "Spoken-name aliases Siri listens for")
def _():
    if not _ok("ecr", "asr_entity_alias"):
        return None
    return _scalar("ecr", "select count(*) from asr_entity_alias")


@m("ctx.entity_summaries", "ecr", "Entity summaries prepared for Siri")
def _():
    if not _ok("ecr", "entity_summary"):
        return None
    return _scalar("ecr", "select count(*) from entity_summary")


@m("ctx.name_vectors", "euclid", "Name embeddings in the vector index")
def _():
    if not _ok("euclid", "observations"):
        return None
    return _scalar("euclid", "select count(*) from observations")


# --- relationships ----------------------------------------------------------

TAGS = ["mother", "father", "parent", "sister", "brother", "sibling", "family", "friend",
        "partner", "coworker", "alumni", "child", "son", "daughter"]


@m("rel.scored", "entityTagging", "People given a relationship score")
def _():
    if not _ok("entityTagging", "entity_tagging"):
        return None
    return _scalar("entityTagging", "select count(*) from entity_tagging")


@m("rel.confident", "entityTagging", "People scored 0.5 or higher, by relationship")
def _():
    if not _ok("entityTagging", "entity_tagging"):
        return None
    sql = "select count(*) from entity_tagging where \"%s\" >= 0.5"
    out = {}
    for t in TAGS:
        out[t] = db.scalar(db_path("entityTagging"), sql % t)
    return {"groups": out, "sql": sql % "<relationship>" + "   -- once per relationship column"}


@m("rel.cues", "features", "Kinship cues computed, by cue")
def _():
    if not _ok("features", "kv"):
        return None
    return _groups("features", "select featureName, count(*) from kv "
                   "where viewName='personEntityTaggingFacts' and featureName != 'isCurrentUser' "
                   "group by featureName")


@m("rel.flags", "importance", "People flagged as favorite, emergency contact, or family")
def _():
    if not _ok("importance", "entityImportanceSignalsIDMap"):
        return None
    t = "entityImportanceSignalsIDMap"
    sql = ("select sum(isFavorite!=0), sum(isEmergencyContact!=0), sum(isICloudFamily!=0), "
           "sum(coalesce(relationshipLabel,'')!='') from " + t)
    r = db.rows(db_path("importance"), sql)
    if not r:
        return {"groups": None, "sql": sql}
    a, b, c, d = r[0]
    return {"groups": {"favorite": a, "emergency contact": b, "iCloud family": c,
                       "relationship label": d}, "sql": sql}


@m("rel.siri_people", "clients", "People in the view handed to Siri")
def _():
    if not _ok("clients", "siriPerson"):
        return None
    return _scalar("clients", "select count(distinct subject) from siriPerson")


# --- photos -----------------------------------------------------------------

@m("photos.face_links", "keyvalue", "Photos face clusters linked to graph entities")
def _():
    if not _ok("keyvalue", "keyvalue"):
        return None
    return _scalar("keyvalue", "select count(*) from keyvalue where domain='VisionSignalsEntityToVision'")


@m("photos.visual_people", "visualIdentifier", "People in the visual identifier view")
def _():
    if not _ok("visualIdentifier", "people"):
        return None
    return _scalar("visualIdentifier", "select count(distinct subject) from people")


@m("photos.autonaming", "photosAutonaming", "Entities in the Photos auto-naming view")
def _():
    if not _ok("photosAutonaming", "subgraph"):
        return None
    return _scalar("photosAutonaming", "select count(distinct subject) from subgraph")


@m("photos.observed_ages", "internalViews", "Ages estimated from faces")
def _():
    if not _ok("internalViews", "photosObservedAges"):
        return None
    return _scalar("internalViews", "select count(*) from photosObservedAges")


# --- pipeline ---------------------------------------------------------------

@m("pipe.views", "views", "Derived views configured")
def _():
    if not _ok("views", "viewConfigRecord"):
        return None
    return _scalar("views", "select count(*) from viewConfigRecord")


@m("pipe.view_errors", "views", "Views reporting an error")
def _():
    if not _ok("views", "viewState"):
        return None
    return _scalar("views", "select count(*) from viewState where coalesce(errorMessage,'') != ''")


@m("pipe.streams", "views", "Data streams the pipeline reads, by kind")
def _():
    if not _ok("views", "sourceState"):
        return None
    return _groups("views", "select sourceType, count(distinct sourceIdentifier) from sourceState group by sourceType")


@m("pipe.synced_streams", "views", "Streams synced from other devices")
def _():
    if not _ok("views", "sourceState"):
        return None
    return _scalar("views", "select count(distinct sourceIdentifier) from sourceState "
                   "where sourceIdentifier like '%:remotes:%'")


@m("pipe.health_trust", "sourceConfidence", "Trust weights that name HealthKit")
def _():
    if not _ok("sourceConfidence", "sourceConfidence"):
        return None
    return _scalar("sourceConfidence", "select count(*) from sourceConfidence where source like 'HealthKit%'")


@m("pipe.life_event_rows", "lifeEvent", "Rows in the life-event subgraph")
def _():
    if not _ok("lifeEvent", "lifeEvent_subgraph"):
        return None
    return _scalar("lifeEvent", "select count(*) from lifeEvent_subgraph")


@m("pipe.global_rows", "globalKnowledge", "Apple-shipped reference facts")
def _():
    if not _ok("globalKnowledge", "static_graph"):
        return None
    return _scalar("globalKnowledge", "select count(*) from static_graph")


# --- row counts, so every catalogued store carries at least one measurement --

ROW_COUNTS = [
    ("ontology", "predicate", "Predicates Apple defines"),
    ("aliases", "aliases", "Relationship words in the alias table"),
    ("state", "task_progress", "Pipeline tasks in progress"),
    ("eventLog", "events", "Pipeline events logged"),
    ("feedbackLog", "feedback", "Feedback records"),
    ("relevance", "person_entity_relevance", "People with a relevance ranking"),
    ("futureLifeEvent", "futureLifeEvent_subgraph", "Rows in the future-life-event subgraph"),
    ("appleMusicEvent", "appleMusicEvent_subgraph", "Rows in the Apple Music event subgraph"),
    ("donation", "donationSubgraph", "Rows in the donation subgraph"),
    ("topicsShort", "topics", "Short-term interest topics"),
    ("topicsLong", "topics", "Long-term interest topics"),
    ("inferredTriples", "languages", "Inferred language facts"),
    ("people", "people", "Rows in the people view"),
]


def _rowcount(store, table):
    def fn():
        if not _ok(store, table):
            return None
        return _scalar(store, 'select count(*) from "%s"' % table)
    return fn


for _s, _t, _title in ROW_COUNTS:
    _REG.append(("rows.%s" % _s, _s, _title, _rowcount(_s, _t)))


# --- watchlist --------------------------------------------------------------

def watchlist(terms):
    """Count how many handles end in each watched domain or contain each term. Never what matched."""
    out = {}
    if not terms or not db.has_table(db_path("internalViews"), "handle_id"):
        return out
    sql = "select count(*) from handle_id where lower(handle) like ?"
    for t in terms:
        t = t.strip().lower()
        if t:
            out[t] = db.scalar(db_path("internalViews"), sql, ("%" + t + "%",))
    return out


# --- run everything ---------------------------------------------------------

def run_all():
    results = []
    for mid, store, title, fn in _REG:
        try:
            r = fn()
        except Exception as e:  # a measurement must never take the run down
            db.gap(db_path(store), "measurement %s failed: %s" % (mid, e))
            r = None
        res = {"id": mid, "store": store, "title": title, "sql": None,
               "value": None, "groups": None, "measured": False}
        if r:
            res.update(r)
            res["measured"] = r.get("value") is not None or r.get("groups") is not None
        results.append(res)
    return results


def by_id(results):
    return {r["id"]: r for r in results}
