"""report.py: the leadership brief and the technical report, from one collection.

Everything printed is escaped. Nothing here reads a store; it renders what
collect.run() measured, which is counts only.
"""

import html

from . import dossier

E = html.escape


def _val(m):
    if not m["measured"]:
        return "<em>not measured</em>"
    if m["groups"] is not None:
        items = sorted(m["groups"].items(), key=lambda kv: -(kv[1] or 0))
        return "<br>".join("%s: %s" % (E(str(k)), E(str(v if v is not None else "not measured")))
                           for k, v in items)
    return E(str(m["value"]))


def _page(title, body):
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>%s</title><link rel='stylesheet' href='/static/report.css'></head>"
            "<body><button class='print' id='print'>Print or save as PDF</button>%s"
            "<script src='/static/report.js'></script></body></html>") % (E(title), body)


def _findings_list(F, detail=False, M=None):
    if not F:
        return "<p>No findings fired. Read the open questions before treating that as clear.</p>"
    out = []
    for f in F:
        ev = ""
        if detail and M:
            rows = []
            for mid in f["evidence"]:
                m = M.get(mid)
                if m:
                    rows.append("<tr><td><code>%s</code></td><td>%s</td><td>%s</td></tr>"
                                % (E(mid), E(m["title"]), _val(m)))
            if rows:
                ev = "<table><tr><th>Measurement</th><th>What</th><th>Value</th></tr>%s</table>" % "".join(rows)
        out.append("<section class='finding'><h3><span class='sev'>%s</span> %s %s</h3>"
                   "<p><strong>Impact.</strong> %s</p><p><strong>Action.</strong> %s</p>%s</section>"
                   % (E(f["severity"]), E(f["id"]), E(f["title"]), E(f["impact"]), E(f["action"]), ev))
    return "".join(out)


def brief(d):
    M = {m["id"]: m for m in d["measurements"]}
    cov = d["coverage"]
    measured = sum(1 for c in cov if c["status"] in ("measured", "partly measured"))
    present = sum(1 for c in cov if c["present"])
    counts = {}
    for f in d["findings"]:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    tally = ", ".join("%d %s" % (counts[s], s) for s in ("High", "Medium", "Low", "Note") if s in counts) or "none"
    def v(mid):
        m = M.get(mid)
        return E(str(m["value"])) if m and m["measured"] else "not measured"
    body = """
<h1>What this Mac knows: brief</h1>
<p class='meta'>iKestrel %(ver)s, %(gen)s. Read from %(mode)s.</p>
<h2>In short</h2>
<p>macOS keeps a personal knowledge graph and a set of derived views under
<code>~/Library/IntelligencePlatform</code>. This review read %(present)d of %(known)d known
stores and measured %(measured)d. Findings: %(tally)s.</p>
<ul>
<li>People in the graph: %(people)s. Communication interactions logged: %(inter)s, from
%(devs)s other device(s).</li>
<li>People given a relationship score: %(scored)s. Face clusters linked to people: %(faces)s.</li>
<li>Wi-Fi networks in the connect history: %(wifi)s.</li>
</ul>
<p>Every number in this brief is a count. It names no person, number, address, network or message.</p>
<h2>Findings</h2>%(findings)s
<h2>What joining the stores reveals</h2><ul>%(chainbrief)s</ul>
<h2>What this brief cannot tell you</h2><ul>%(open)s</ul>
""" % {"ver": E(d["version"]), "gen": E(d["generated"]), "mode": "a copy" if d["mode"] == "copy" else "this Mac, live",
       "present": present, "known": len(cov), "measured": measured, "tally": E(tally),
       "people": E(str((M["graph.classes"]["groups"] or {}).get("people", "not measured")) if M["graph.classes"]["measured"] else "not measured"),
       "inter": v("comms.interactions"), "devs": v("comms.remote_devices"), "scored": v("rel.scored"),
       "faces": v("photos.face_links"), "wifi": v("ctx.wifi_networks"),
       "findings": _findings_list(d["findings"]),
       "chainbrief": "".join("<li>%s: %s.</li>" % (E(c["title"]), E(", then ".join(
           "%s %s" % ("not measured" if s["count"] is None else s["count"], s["label"].lower()) for s in c["steps"])))
           for c in (d.get("linkage") or {}).get("chains", [])) or "<li>Not measured.</li>",
       "open": "".join("<li>%s</li>" % E(q) for q in d["open"])}
    return _page("iKestrel brief", body)


def _linkage_rows(L):
    if not L:
        return "<tr><td colspan='5'>Not measured.</td></tr>"
    out = []
    for e in sorted(L["edges"], key=lambda e: (e["space"], e["a"], e["b"])):
        ov = "not measured" if not e["measured"] else "%d" % e["overlap"]
        out.append("<tr><td>%s</td><td><code>%s</code></td><td><code>%s</code></td><td>%s</td><td>%s / %s</td></tr>"
                   % (E(e["space"]), E(e["a"]), E(e["b"]), E(ov), E(str(e["a_size"])), E(str(e["b_size"]))))
    return "".join(out)


def _chains(L):
    out = []
    for c in (L or {}).get("chains", []):
        steps = "".join("<tr><td>%s</td><td>%s</td></tr>" % (E(s["label"]), E("not measured" if s["count"] is None else str(s["count"])))
                        for s in c["steps"])
        out.append("<h3>%s %s</h3><p class='meta'>Path: %s</p><table>%s</table><p>%s</p>"
                   % (E(c["id"]), E(c["title"]), E(" > ".join(c["path"])), steps, E(c["explains"])))
    return "".join(out) or "<p>Not measured.</p>"


def _dossiers(cov):
    out = []
    for c in cov:
        d = dossier.get(c["id"])
        if not d:
            continue
        ex = "".join("<li><code>%s</code></li>" % E(x) for x in d["example"])
        out.append("<h3><code>%s</code> (%s, %s)</h3><p><strong>Alone.</strong> %s</p>"
                   "<p><strong>Worst case.</strong> %s</p><ul>%s</ul>"
                   % (E(c["path"]), E(c["group"]), E(c["sensitivity"]), E(d["alone"]), E(d["worst"]), ex))
    return "".join(out)


def technical(d):
    M = {m["id"]: m for m in d["measurements"]}
    L = d.get("linkage") or {}
    M["linkage.bridge"] = {"id": "linkage.bridge", "title": "Graph people reachable from phone history through handles",
                           "measured": (L.get("bridge") or {}).get("phone_history_to_graph_people") is not None,
                           "value": (L.get("bridge") or {}).get("phone_history_to_graph_people"), "groups": None}
    cov_rows = "".join(
        "<tr><td>%s</td><td><code>%s</code></td><td>%s</td><td>%s</td><td>%d of %d</td><td>%s</td></tr>"
        % (E(c["group"]), E(c["path"]), E(c["sensitivity"]), E(c["status"]), c["measured"], c["measurements"],
           E("; ".join(c["reasons"])))
        for c in d["coverage"])
    extra = "".join("<li><code>%s</code></li>" % E(x) for x in d["uncatalogued"]) or "<li>None.</li>"
    meas = "".join("<tr><td><code>%s</code></td><td>%s</td><td>%s</td></tr>" % (E(m["id"]), E(m["title"]), _val(m))
                   for m in d["measurements"])
    sqls = "".join("<h4><code>%s</code> (%s)</h4><pre>%s</pre>" % (E(m["id"]), E(m["store"]), E(m["sql"] or "not run"))
                   for m in d["measurements"] if not m["id"].startswith("linkage."))
    sqls += "".join("<h4>linkage: %s key in <code>%s</code></h4><pre>%s</pre>" % (E(s["space"]), E(s["store"]), E(s["sql"]))
                    for s in L.get("sql", []))
    scope = "".join("<tr><td><code>%s</code></td><td>%d</td><td><code>%s</code></td></tr>"
                    % (E(s["file"]), s["bytes"], E(s["sha256"])) for s in d["scope"])
    gaps = "".join("<li><code>%s</code>: %s</li>" % (E(g["store"]), E(g["reason"])) for g in d["gaps"]) or "<li>None.</li>"
    watch = "".join("<li>%s: %s</li>" % (E(k), E(str(v))) for k, v in sorted(d["watch"].items())) or "<li>No watchlist given.</li>"
    cat = "".join("<li><strong>%s</strong>: %s</li>" % (E(c["category"]), E(", ".join(c["prefixes"]))) for c in d["catalog"])
    body = """
<h1>What this Mac knows: technical report</h1>
<p class='meta'>iKestrel %(ver)s, %(gen)s. Mode: %(mode)s. Root: <code>%(root)s</code>.</p>
<h2>1. Scope and integrity</h2>
<p>Every store was opened read-only (SQLite <code>mode=ro</code>). Hashes cover each database and its
write-ahead log. Shared-memory index files (<code>-shm</code>) are excluded: SQLite may rebuild them
when it reads a WAL, and they hold no rows.</p>
<table><tr><th>File</th><th>Bytes</th><th>SHA-256</th></tr>%(scope)s</table>
<h2>2. Store coverage</h2>
<table><tr><th>Group</th><th>Store</th><th>Sensitivity</th><th>Status</th><th>Measured</th><th>Reason</th></tr>%(cov)s</table>
<h3>Stores on disk this version does not yet catalogue</h3><ul>%(extra)s</ul>
<h2>3. Findings</h2>%(findings)s
<h2>3a. How the stores join</h2>
<p>Overlap counts between identifier sets. The identifiers themselves are never shown. Entity ids are drawn
as a hub on graph.db. Graph people reachable from the phone's history through handles: %(bridge)s.</p>
<table><tr><th>Key</th><th>Store</th><th>Store</th><th>Shared ids</th><th>Sizes</th></tr>%(link)s</table>
<h2>3b. What can be ascertained</h2>
<p>Each chain walks across stores and counts how many people remain in view at each step. Counts only.</p>%(chains)s
<h2>4. All measurements</h2>
<table><tr><th>Id</th><th>What</th><th>Value</th></tr>%(meas)s</table>
<h2>5. Watchlist</h2><p>Counts of handles containing each term. What matched is never shown.</p><ul>%(watch)s</ul>
<h2>6. Not measured, and why</h2><ul>%(gaps)s</ul>
<h2>7. Open questions</h2><ul>%(open)s</ul>
<h2>Appendix A. App categories</h2><p>Bundle ids outside these prefixes appear only as "unlisted app".</p><ul>%(cat)s</ul>
<h2>Appendix B. What each store can give away</h2>
<p>Every example value below is invented, in the shape of a real row. None of it comes from the Mac under review.</p>%(dossiers)s
<h2>Appendix C. The SQL behind every number</h2>%(sqls)s
""" % {"ver": E(d["version"]), "gen": E(d["generated"]), "mode": E(d["mode"]), "root": E(d["root"]),
       "scope": scope or "<tr><td colspan='3'>Hashes not computed.</td></tr>", "cov": cov_rows, "extra": extra,
       "findings": _findings_list(d["findings"], True, M), "meas": meas, "watch": watch, "gaps": gaps,
       "open": "".join("<li>%s</li>" % E(q) for q in d["open"]), "cat": cat, "sqls": sqls,
       "link": _linkage_rows(L), "chains": _chains(L), "dossiers": _dossiers(d["coverage"]), "bridge": E(str((L.get("bridge") or {}).get("phone_history_to_graph_people", "not measured")))}
    return _page("iKestrel technical report", body)
