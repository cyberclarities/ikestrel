"""findings.py: rules that turn measurements into findings.

Each finding states its severity as a word, the evidence (measurement ids and
their values), the impact, and what to do. Severity is a judgment and is
written down so it can be argued with. A rule whose measurements were not
taken does not fire; it is listed among the open questions instead, because
not measured is not zero.
"""

SEVERITY_ORDER = {"High": 0, "Medium": 1, "Low": 2, "Note": 3}


def _v(M, mid):
    r = M.get(mid)
    return None if not r or not r["measured"] else r["value"]


def _g(M, mid):
    r = M.get(mid)
    return None if not r or not r["measured"] else (r["groups"] or {})


def evaluate(M, live_checks=None, watch=None, linkage=None):
    F, open_q = [], []

    def add(fid, sev, title, evidence, impact, action):
        F.append({"id": fid, "severity": sev, "title": title, "evidence": evidence,
                  "impact": impact, "action": action})

    # 1. phone history on the Mac
    n, dev = _v(M, "comms.interactions"), _v(M, "comms.remote_devices")
    if n is None:
        open_q.append("Siri's interaction history could not be read, so cross-device communication logging is unknown.")
    elif n and dev:
        add("K-01", "High", "This Mac holds communication history from other devices",
            ["comms.interactions", "comms.remote_devices", "comms.by_device", "comms.span"],
            "%d message, call and app interactions are stored here, from %d other device(s), over %s. "
            "Anyone who can read this Mac's disk can rebuild who the owner contacts, when, and in which app, "
            "without ever touching the phone." % (n, dev, _v(M, "comms.span") or "an unknown span"),
            "Confirm FileVault is on. Treat this Mac as holding the phone's contact pattern when deciding "
            "who may administer it, back it up, or take it across a border. Reducing what is synced (Siri "
            "learning per app, iCloud Siri sync) is a candidate control, not yet tested.")

    # 2. private messenger metadata
    cat = _g(M, "comms.by_category")
    if cat is not None and (cat.get("Private messenger") or 0) > 0:
        add("K-02", "High", "Metadata from private messengers is logged by the operating system",
            ["comms.by_category", "comms.by_app"],
            "%d interactions come from apps people choose for privacy. The message text is not stored, "
            "but the pattern of who and when is, outside that app's own protections." % cat["Private messenger"],
            "Brief staff who rely on a private messenger for sensitive contacts that the device keeps its own "
            "record. Review that app's Siri and Suggestions setting on the phone.")

    # 3. bodies
    b = _v(M, "comms.message_bodies")
    if b is not None:
        if b == 0:
            add("K-03", "Note", "Message text is not stored in Siri's history",
                ["comms.message_bodies"],
                "Message entities carry only an identifier. The exposure is metadata, not content.",
                "Say this plainly in any brief, so the finding above is not overstated.")
        else:
            add("K-03", "High", "Some message entities hold more than an identifier",
                ["comms.message_bodies"], "%d message entities carry extra fields." % b,
                "Inspect the fields on this Mac before drawing conclusions.")

    # 4. concentration
    s = _v(M, "comms.top_share")
    if s is not None and s >= 20:
        add("K-04", "Medium", "One counterpart dominates the communication log",
            ["comms.top_share", "comms.counterparts"],
            "A single person accounts for about %d%% of person links among %s counterparts. A reader can "
            "identify the owner's closest relationship from counts alone." % (s, _v(M, "comms.counterparts")),
            "No action on the Mac; weigh this when the owner is a likely target.")

    # 5. relationship inference
    sc = _v(M, "rel.scored")
    if sc is None:
        open_q.append("Relationship scoring could not be read.")
    elif sc:
        conf = _g(M, "rel.confident") or {}
        strong = sum(v or 0 for v in conf.values())
        add("K-05", "Medium", "The Mac scores how each person is related to the owner",
            ["rel.scored", "rel.confident", "rel.cues"],
            "%d people carry relationship scores; %d confident labels (0.5 or higher) across family, partner, "
            "friend and coworker. The owner never entered most of these." % (sc, strong),
            "Treat relationship inference as personal data about third parties in privacy reviews.")

    # 6. wifi
    w, d = _v(M, "ctx.wifi_networks"), _v(M, "ctx.wifi_days")
    if w is None:
        open_q.append("Wi-Fi connect history could not be read.")
    elif w:
        add("K-06", "Medium", "Wi-Fi network names are kept with timestamps",
            ["ctx.wifi_networks", "ctx.wifi_events", "ctx.wifi_days"],
            "%d networks over about %s days. Network names often name the place, so the history can "
            "disclose visits (clinics, offices, homes) by itself." % (w, d),
            "Review the names on this Mac privately; do not export them into a report.")

    # 7. faces
    f = _v(M, "photos.face_links")
    if f:
        add("K-07", "Medium", "Faces in Photos are linked to people in the graph",
            ["photos.face_links", "photos.visual_people", "photos.observed_ages"],
            "%d face clusters are tied to entities, with ages estimated from faces for %s people."
            % (f, _v(M, "photos.observed_ages")),
            "Treat the Photos library and this folder as one exposure.")

    # 8. handles
    h = _g(M, "ctx.handles")
    if h:
        add("K-08", "Low", "Phone numbers and email addresses resolve to people",
            ["ctx.handles", "ctx.speech_aliases"],
            "%d handles map to graph people, and %s spoken-name aliases help Siri match them."
            % (sum(v or 0 for v in h.values()), _v(M, "ctx.speech_aliases")),
            "Expected behavior; it is what makes the other findings joinable.")

    # 9. residue
    fr = _v(M, "graph.free_ratio")
    if fr is not None and fr >= 25:
        add("K-09", "Note", "Much of graph.db is free pages left by earlier builds",
            ["graph.free_ratio", "graph.rebuilt"],
            "About %d%% of the file is on the free list. Older copies of facts may be recoverable by carving." % fr,
            "For an investigation, image the file; do not rely on the live rows alone.")

    # 10. health
    ht = _v(M, "pipe.health_trust")
    if ht:
        add("K-10", "Note", "HealthKit is a trusted source in the pipeline",
            ["pipe.health_trust"],
            "%d trust weights name HealthKit. No Health records were measured in these stores." % ht,
            "Check the phone's Health sharing settings if health data is in scope.")

    # 13. the bridge from phone history to people on this Mac
    reach = ((linkage or {}).get("bridge") or {}).get("phone_history_to_graph_people")
    if reach:
        add("K-13", "High", "Phone history joins to named people on this Mac",
            ["linkage.bridge", "comms.counterparts"],
            "Phone numbers and email addresses in the synced Siri history resolve to %d people in this "
            "Mac's graph through its handle map. Contact ids differ between devices, but handles do not, "
            "so the phone's contact pattern attaches to names, faces and relationship scores here." % reach,
            "Treat K-01 as identifying, not anonymous. See the connection map for every join.")

    # 11. watchlist
    if watch:
        hits = {k: v for k, v in watch.items() if v}
        if hits:
            add("K-11", "Medium", "Organization terms appear among people's handles",
                ["watchlist"], "%d watched term(s) match handles: %s." %
                (len(hits), ", ".join("%s (%d)" % (k, v) for k, v in sorted(hits.items()))),
                "These people are linked to the organization in the owner's graph.")

    # live checks
    lc = live_checks or {}
    fv = lc.get("filevault")
    if fv is None:
        open_q.append("FileVault status was not measured (a copy says nothing about the Mac it came from).")
    elif fv is False:
        add("K-12", "High", "FileVault is off", ["live.filevault"],
            "Every finding above is readable by anyone with the disk.", "Turn on FileVault.")

    open_q.append("This report covers one Mac. The phone and other devices hold their own copies.")
    F.sort(key=lambda x: (SEVERITY_ORDER[x["severity"]], x["id"]))
    return F, open_q
