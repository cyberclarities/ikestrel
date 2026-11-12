import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import make_fixture  # noqa: E402
from kestrel import collect, db, report  # noqa: E402


class Kestrel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        make_fixture.build(cls.tmp)
        db.configure(copy=cls.tmp)
        cls.d = collect.run(["quartermain.test"], hashes=True)
        cls.M = {m["id"]: m for m in cls.d["measurements"]}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def v(self, mid):
        return self.M[mid]["value"]

    def g(self, mid):
        return self.M[mid]["groups"]

    def test_counts(self):
        self.assertEqual(self.v("graph.entities"), 4)
        self.assertEqual(self.g("graph.classes"), {"people": 2, "organizations": 1, "apps": 1})
        self.assertEqual(self.g("graph.by_source")["Photos"], 2)
        self.assertEqual(self.v("graph.addresses"), 1)
        self.assertEqual(self.v("comms.interactions"), 6)
        self.assertEqual(self.v("comms.remote_devices"), 1)
        self.assertEqual(self.g("comms.by_device"), {"other device 1": 5, "this Mac": 1})
        self.assertEqual(self.g("comms.by_category")["Private messenger"], 3)
        self.assertEqual(self.v("comms.top_share"), 75)
        self.assertEqual(self.v("comms.message_bodies"), 0)
        self.assertEqual(self.v("ctx.wifi_networks"), 2)
        self.assertEqual(self.v("rel.scored"), 2)
        self.assertEqual(self.g("rel.confident")["friend"], 1)
        self.assertEqual(self.d["watch"], {"quartermain.test": 1})

    def test_linkage(self):
        L = self.d["linkage"]
        self.assertEqual(L["bridge"]["phone_history_to_graph_people"], 1)
        e = {(x["space"], x["a"], x["b"]): x for x in L["edges"]}
        self.assertEqual(e[("entity", "entityTagging", "graph")]["overlap"], 2)
        self.assertEqual(e[("handle", "internalViews", "siriRemembers")]["overlap"], 1)
        self.assertFalse(e[("contact", "graph", "siriResolver")]["measured"])  # resolver store absent
        self.assertIn("K-13", {f["id"] for f in self.d["findings"]})

    def test_chains(self):
        C = {c["id"]: [s["count"] for s in c["steps"]] for c in self.d["linkage"]["chains"]}
        self.assertEqual(C["C1"], [1, 1, 1, 1])   # bridged -> named -> has a place -> friend 0.9
        self.assertEqual(C["C2"], [2, 2, 1, 1])   # two confident scores; both have handles; one has a place
        self.assertEqual(C["C5"], [1, 1, 1])      # employer, birthday
        self.assertEqual(C["C3"][0], 0)           # no face links in the graph fixture
        for c in self.d["linkage"]["chains"]:
            self.assertEqual(len(c["hops"]), len(c["path"]) - 1)

    def test_every_store_has_a_dossier(self):
        from kestrel import dossier, stores
        self.assertEqual(dossier.missing([s[0] for s in stores.STORES]), [])
        tech = report.technical(self.d)
        self.assertIn("What each store can give away", tech)
        self.assertIn("What can be ascertained", tech)

    def test_dossier_examples_are_invented(self):
        import re
        from kestrel import dossier
        text = json.dumps(dossier.D)
        for email in re.findall(r"[\w.+-]+@[\w.-]+", text):
            self.assertTrue(email.endswith("example.org"), email)
        for phone in re.findall(r"\+1 \d{3} \d{3} \d{4}", text):
            self.assertRegex(phone, r"^\+1 555 01\d")

    def test_sheet(self):
        import csv, io
        from kestrel import sheet, stores
        rs = sheet.rows(self.d)
        self.assertEqual(len(rs), len(stores.STORES))
        g = {r["store"]: r for r in rs}
        self.assertEqual(g["graph"]["ids_entity"], 4)
        self.assertEqual(g["internalViews"]["ids_handle"], 3)
        self.assertIn("C1", g["siriRemembers"]["chains"])
        self.assertEqual(rs[0]["sensitivity"], "High")       # sorted by sensitivity first
        text = sheet.to_csv(rs)
        self.assertTrue(text.startswith("\ufeff"))
        parsed = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
        self.assertEqual(len(parsed), len(rs) + 1)
        self.assertEqual(len(parsed[0]), len(sheet.COLUMNS))
        for s in make_fixture.SECRETS:
            self.assertNotIn(s, text, s)

    def test_csv_formula_injection_guard(self):
        from kestrel import sheet
        for bad in ("=1+1", "+cmd", "-2", "@SUM(A1)", "\tx", "\rx"):
            self.assertTrue(sheet._safe(bad).startswith("'"), bad)
        self.assertEqual(sheet._safe("plain"), "plain")
        self.assertEqual(sheet._safe(5), "5")

    def test_reveal_values(self):
        from kestrel import reveal
        db.begin()
        try:
            ppl = reveal.people()
            names = {p["name"] for p in ppl["people"]}
            self.assertEqual(ppl["total"], 2)
            self.assertIn("Zebulon Quartermain", names)
            P = reveal.person("1")
            self.assertEqual(P["name"], "Zebulon Quartermain")
            self.assertIn("+15550100777", P["handles"])
            self.assertEqual(P["relationship_scores"].get("friend"), 0.9)
            c = P["communications"]
            self.assertEqual((c["total"], c["sent"], c["received"], c["group"]), (4, 3, 1, 0))
            self.assertEqual(c["by_app"], {"ph.telegra.Telegraph": 3, "com.apple.MobileSMS": 1})
            self.assertEqual([m["name"] for m in reveal.chain("C1", 0)], ["Zebulon Quartermain"])
            self.assertIsNone(reveal.chain("C1", 99))
            T = reveal.timeline(limit=50)
            wifi = [e["detail"] for e in T["events"] if e["source"] == "Wi-Fi"]
            self.assertIn("Hidden Clinic WiFi", wifi)
            sms = [e for e in T["events"] if e["app"] == "com.apple.MobileSMS"][0]
            self.assertEqual(sms["direction"], "received")
            self.assertEqual(sms["detail"], "Zebulon Quartermain")   # handle resolved to a name
            b = reveal.browse("graph", "stable_graph", 0, 10)
            self.assertEqual(b["total"], 10)
            self.assertIn("timestamp", b["columns"])
            self.assertIsNone(reveal.browse("graph", "nope", 0, 10))
        finally:
            db.close()

    def test_reports_never_carry_real_values(self):
        from kestrel import sheet
        out = report.brief(self.d) + report.technical(self.d) + json.dumps(self.d) + sheet.to_csv(sheet.rows(self.d))
        for s in ("Zebulon Quartermain", "Juniper Ashgrove", "Hidden Clinic WiFi", "+15550100777", "77 Fictional Lane"):
            self.assertNotIn(s, out, s)

    def test_spider_map(self):
        from kestrel import web
        db.begin()
        try:
            W = web.build(real=False)
            safe = json.dumps(W)
            for s in make_fixture.SECRETS + ["DEV-A"]:
                self.assertNotIn(s, safe, s)
            by = {n["label"]: n for n in W["nodes"]}
            self.assertEqual(sorted(by), ["Employer A", "Person 1", "Person 2", "You"])
            self.assertEqual(by["Person 1"]["role"], "friend")    # friend 0.9, and the one with messages ranks first
            self.assertEqual(by["Person 2"]["role"], "partner")   # partner 0.7
            m = [l for l in W["links"] if l["kind"] == "messages"]
            self.assertEqual(len(m), 1)
            self.assertEqual(m[0]["count"], 4)
            self.assertIn("3 you sent, 1 you received", m[0]["tip"])
            self.assertEqual(sorted(l["kind"] for l in W["links"]), ["employer", "messages", "scored", "scored"])
            self.assertIsNone(by["Person 1"]["profile"])
            R = web.build(real=True)
            names = {n["label"] for n in R["nodes"]}
            self.assertIn("Zebulon Quartermain", names)
            z = [n for n in R["nodes"] if n["label"] == "Zebulon Quartermain"][0]
            self.assertEqual(z["profile"], "1")
            self.assertTrue(any("Zebulon Quartermain" in s for s in z["story"]))
            self.assertEqual(web._cap("finley Kestrow"), "Finley Kestrow")
        finally:
            db.close()

    def test_unknown_app_is_withheld(self):
        apps = self.g("comms.by_app")
        self.assertNotIn("com.secretcorp.tool", apps)
        self.assertEqual(apps.get("unlisted app"), 1)

    def test_missing_store_is_not_zero(self):
        m = self.M["comms.resolver_events"]
        self.assertFalse(m["measured"])
        self.assertIsNone(m["value"])
        self.assertTrue(any(g["store"].endswith("defaultResolverInteractions/view.db") for g in self.d["gaps"]))

    def test_findings(self):
        ids = {f["id"] for f in self.d["findings"]}
        for fid in ("K-01", "K-02", "K-03", "K-04", "K-05", "K-06", "K-11"):
            self.assertIn(fid, ids)

    def test_nothing_personal_leaks(self):
        out = report.brief(self.d) + report.technical(self.d) + json.dumps(self.d)
        for s in make_fixture.SECRETS:
            self.assertNotIn(s, out, s)
        self.assertNotIn("DEV-A", out)

    def test_read_only_leaves_stores_unchanged(self):
        before = {f: db.sha256(f) for f in db.store_files() if not f.endswith("-shm")}
        collect.run(hashes=True)
        after = {f: db.sha256(f) for f in db.store_files() if not f.endswith("-shm")}
        self.assertEqual(before, after)

    def test_server_requires_token(self):
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        p = subprocess.Popen([sys.executable, "-I", "-u", os.path.join(ROOT, "server.py"), "--copy", self.tmp,
                              "--port", str(port)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            line = ""
            for _ in range(50):
                line = p.stdout.readline()
                if "?t=" in line:
                    break
            token = line.strip().split("?t=")[1]
            base = "http://127.0.0.1:%d" % port
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(base + "/api/summary")
            self.assertEqual(e.exception.code, 403)
            r = urllib.request.urlopen(base + "/api/summary?t=" + token)
            self.assertEqual(r.status, 200)
            self.assertIn("default-src 'none'", r.headers["Content-Security-Policy"])
            for path in ("/map", "/api/linkage", "/static/map.js", "/sheet", "/api/sheet", "/static/sheet.js"):
                self.assertEqual(urllib.request.urlopen(base + path + "?t=" + token).status, 200)
            r = urllib.request.urlopen(base + "/export/stores.csv?t=" + token)
            self.assertIn("attachment", r.headers["Content-Disposition"])
            self.assertIn("text/csv", r.headers["Content-Type"])
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(base + "/export/stores.csv")
            for path in ("/person", "/timeline", "/browse", "/static/reveal.js", "/static/person.js",
                         "/web", "/static/web.js", "/static/force.js"):
                self.assertEqual(urllib.request.urlopen(base + path + "?t=" + token).status, 200)
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(base + "/api/reveal/people?t=" + token)   # no reveal header
            self.assertEqual(e.exception.code, 403)
            req = urllib.request.Request(base + "/api/reveal/people?t=" + token, headers={"X-Kestrel-Reveal": "1"})
            self.assertIn("Zebulon Quartermain", urllib.request.urlopen(req).read().decode())
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(urllib.request.Request(base + "/api/reveal/people", headers={"X-Kestrel-Reveal": "1"}))
            self.assertEqual(e.exception.code, 403)                                # header without token
            safe = urllib.request.urlopen(base + "/api/web?t=" + token).read().decode()
            for s in make_fixture.SECRETS:
                self.assertNotIn(s, safe, s)
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(base + "/api/reveal/web?t=" + token)        # real names need the header
            self.assertEqual(e.exception.code, 403)
            body = urllib.request.urlopen(base + "/api/linkage?t=" + token).read().decode()
            for s in make_fixture.SECRETS:
                self.assertNotIn(s, body, s)
        finally:
            p.terminate(); p.wait(5); p.stdout.close(); p.stderr.close()


if __name__ == "__main__":
    unittest.main()
