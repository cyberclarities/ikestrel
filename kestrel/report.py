"""report.py: the leadership brief and the technical report, from one collection.

Everything printed is escaped. Nothing here reads a store; it renders what
collect.run() measured, which is counts only.
"""

import html

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
<h2>What this brief cannot tell you</h2><ul>%(open)s</ul>
""" % {"ver": E(d["version"]), "gen": E(d["generated"]), "mode": "a copy" if d["mode"] == "copy" else "this Mac, live",
       "present": present, "known": len(cov), "measured": measured, "tally": E(tally),
       "people": E(str((M["graph.classes"]["groups"] or {}).get("people", "not measured")) if M["graph.classes"]["measured"] else "not measured"),
       "inter": v("comms.interactions"), "devs": v("comms.remote_devices"), "scored": v("rel.scored"),
       "faces": v("photos.face_links"), "wifi": v("ctx.wifi_networks"),
       "findings": _findings_list(d["findings"]),
       "open": "".join("<li>%s</li>" % E(q) for q in d["open"])}
    return _page("iKestrel brief", body)


def technical(d):
    M = {m["id"]: m for m in d["measurements"]}
    cov_rows = "".join(
        "<tr><td>%s</td><td><code>%s</code></td><td>%s</td><td>%s</td><td>%d of %d</td><td>%s</td></tr>"
        % (E(c["group"]), E(c["path"]), E(c["sensitivity"]), E(c["status"]), c["measured"], c["measurements"],
           E("; ".join(c["reasons"])))
        for c in d["coverage"])
    extra = "".join("<li><code>%s</code></li>" % E(x) for x in d["uncatalogued"]) or "<li>None.</li>"
    meas = "".join("<tr><td><code>%s</code></td><td>%s</td><td>%s</td></tr>" % (E(m["id"]), E(m["title"]), _val(m))
                   for m in d["measurements"])
    sqls = "".join("<h4><code>%s</code> (%s)</h4><pre>%s</pre>" % (E(m["id"]), E(m["store"]), E(m["sql"] or "not run"))
                   for m in d["measurements"])
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
<h2>4. All measurements</h2>
<table><tr><th>Id</th><th>What</th><th>Value</th></tr>%(meas)s</table>
<h2>5. Watchlist</h2><p>Counts of handles containing each term. What matched is never shown.</p><ul>%(watch)s</ul>
<h2>6. Not measured, and why</h2><ul>%(gaps)s</ul>
<h2>7. Open questions</h2><ul>%(open)s</ul>
<h2>Appendix A. App categories</h2><p>Bundle ids outside these prefixes appear only as "unlisted app".</p><ul>%(cat)s</ul>
<h2>Appendix B. The SQL behind every number</h2>%(sqls)s
""" % {"ver": E(d["version"]), "gen": E(d["generated"]), "mode": E(d["mode"]), "root": E(d["root"]),
       "scope": scope or "<tr><td colspan='3'>Hashes not computed.</td></tr>", "cov": cov_rows, "extra": extra,
       "findings": _findings_list(d["findings"], True, M), "meas": meas, "watch": watch, "gaps": gaps,
       "open": "".join("<li>%s</li>" % E(q) for q in d["open"]), "cat": cat, "sqls": sqls}
    return _page("iKestrel technical report", body)
