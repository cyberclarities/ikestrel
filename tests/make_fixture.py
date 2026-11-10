"""make_fixture.py: a small, entirely made-up IntelligencePlatform folder with known answers.

Every name, number, address and network here is invented. The tests check that
none of the strings in SECRETS reaches either report or the summary API.
"""

import json
import os
import sqlite3

SECRETS = ["Zebulon Quartermain", "+15550100777", "555) 010-0777", "nobody@elsewhere.test", "5550100777", "zeb@quartermain.test", "77 Fictional Lane",
           "Hidden Clinic WiFi", "Juniper Ashgrove", "juniper@ashgrove.test", "com.secretcorp.tool"]

TRIPLE = ("subject INTEGER, predicate TEXT, relationshipId INTEGER, relationshipPredicate TEXT, "
          "object TEXT, sources INTEGER, confidence DOUBLE, sourceDuplicates TEXT, timestamp DOUBLE")
SUB = "subject INTEGER, predicate TEXT, relationshipId INTEGER, relationshipPredicate TEXT, object TEXT"


def _db(root, rel, script):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    c = sqlite3.connect(p)
    c.executescript(script)
    c.commit()
    return c


def build(root):
    # graph: 2 people, 1 org, 1 app; one address
    g = _db(root, "graph.db", "create table stable_graph(%s); create table event_graph(%s); "
            "create table graph_state(key TEXT, value ANY);" % (TRIPLE, TRIPLE))
    rows = [
        (1, "PS1", 0, "", "SB104", 1, 1, "", 0), (1, "PS33", 0, "", "Zebulon Quartermain", 1, 1, "", 0),
        (1, "PS317", 9, "PS316", "77 Fictional Lane", 1, 1, "", 0), (1, "PS37", 0, "", "1970-01-01", 1, 1, "", 0),
        (2, "PS1", 0, "", "SB104", 33, 1, "", 0), (2, "PS33", 0, "", "Juniper Ashgrove", 32, 1, "", 0),
        (3, "PS1", 0, "", "SB10", 1, 1, "", 0), (4, "PS1", 0, "", "SB144", 32768, 1, "", 0),
    ]
    g.executemany("insert into stable_graph values (?,?,?,?,?,?,?,?,?)", rows)
    g.execute("insert into event_graph values (10,'PS1',0,'','SB472',256,1,'',0)")
    g.execute("insert into graph_state values ('buildFromScratchTimestamp', 808345538.0)")
    g.commit()

    # siri remembers: 5 interactions, 4 from another device; 3 private-messenger sends
    r = _db(root, "Artifacts/siri/remembers/view.db",
            "create table interactions(rowid INTEGER PRIMARY KEY, type TEXT, bundleId TEXT, startDate DOUBLE, remoteDeviceId TEXT);"
            "create table entities(rowid INTEGER PRIMARY KEY, id TEXT, type TEXT, fields TEXT);"
            "create table interactionEntities(interactionRowid INTEGER, entityRowid INTEGER, parameter TEXT);")
    ints = [(1, "INSendMessageIntent", "ph.telegra.Telegraph", 800000000, "DEV-A"),
            (2, "INSendMessageIntent", "ph.telegra.Telegraph", 800000100, "DEV-A"),
            (3, "INSendMessageIntent", "ph.telegra.Telegraph", 800000200, "DEV-A"),
            (4, "INStartCallIntent", "com.secretcorp.tool", 800000300, "DEV-A"),
            (5, "WeatherIntent", "com.apple.weather", 800000400, "")]
    r.executemany("insert into interactions values (?,?,?,?,?)", ints)
    r.executemany("insert into entities values (?,?,?,?)", [
        (1, "p1", "Person", json.dumps({"name": "Zebulon Quartermain"})),
        (2, "p2", "Person", json.dumps({"name": "Juniper Ashgrove"})),
        (3, "m1", "Message", json.dumps({"identifier": "m1"})),
        (4, "+1 (555) 010-0777", "PersonHandle", json.dumps({"type": "phone"})),
        (5, "nobody@elsewhere.test", "PersonHandle", json.dumps({"type": "email"}))])
    r.executemany("insert into interactionEntities values (?,?,?)",
                  [(1, 1, "recipients"), (2, 1, "recipients"), (3, 1, "recipients"), (4, 2, "recipients")])
    r.commit()

    # internal views: handles, wifi
    v = _db(root, "Artifacts/internal/views.db",
            "create table handle_id(handle TEXT, id INTEGER);"
            "create table wifiContextEvents(behaviorType INTEGER, behaviorIdentifier TEXT, timestamp REAL, timeSincePreviousEvent REAL);"
            "create table photosObservedAges(id INTEGER, entityIdentifier TEXT, interactionDate REAL, observedAge INTEGER);")
    v.executemany("insert into handle_id values (?,?)",
                  [("+15550100777", 1), ("zeb@quartermain.test", 1), ("juniper@ashgrove.test", 2)])
    v.executemany("insert into wifiContextEvents values (10,?,?,null)",
                  [("Connect:Hidden Clinic WiFi", 800000000), ("Disconnect:Hidden Clinic WiFi", 800003600),
                   ("Connect:Home Net", 800086400)])
    # an FTS table with Apple's private tokenizer, which stock SQLite cannot load
    v.executescript("create virtual table entity_alias_fts using fts5(alias);"
                    "pragma writable_schema=1;"
                    "update sqlite_master set sql=replace(sql,'fts5(alias)','fts5(alias, tokenize=\"unicode61wrapper\")') "
                    "where name='entity_alias_fts';"
                    "pragma writable_schema=0;")
    v.commit()

    t = _db(root, "Artifacts/entityTagging/entityTagging.db",
            "create table entity_tagging(mdid TEXT, mother DOUBLE, father DOUBLE, parent DOUBLE, sister DOUBLE, brother DOUBLE, "
            "sibling DOUBLE, family DOUBLE, friend DOUBLE, familyAndFriends DOUBLE, partner DOUBLE, coworker DOUBLE, alumni DOUBLE, "
            "child DOUBLE, son DOUBLE, daughter DOUBLE, myself DOUBLE, unknown DOUBLE, eventid INTEGER);")
    t.execute("insert into entity_tagging values ('1',0,0,0,0,0,0,0,0.9,0,0,0,0,0,0,0,0,0,0)")
    t.execute("insert into entity_tagging values ('2',0,0,0,0,0,0,0,0,0,0.7,0,0,0,0,0,0,0,0)")
    t.commit()

    k = _db(root, "keyvalue.db", "create table keyvalue(domain TEXT, key TEXT, value BLOB);")
    k.execute("insert into keyvalue values ('VisionSignalsEntityToVision','face-1',x'00')")
    k.commit()
    return root
