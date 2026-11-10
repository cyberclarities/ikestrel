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
        self.assertEqual(self.v("comms.interactions"), 5)
        self.assertEqual(self.v("comms.remote_devices"), 1)
        self.assertEqual(self.g("comms.by_device"), {"other device 1": 4, "this Mac": 1})
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
            for path in ("/map", "/api/linkage", "/static/map.js"):
                self.assertEqual(urllib.request.urlopen(base + path + "?t=" + token).status, 200)
            body = urllib.request.urlopen(base + "/api/linkage?t=" + token).read().decode()
            for s in make_fixture.SECRETS:
                self.assertNotIn(s, body, s)
        finally:
            p.terminate(); p.wait(5); p.stdout.close(); p.stderr.close()


if __name__ == "__main__":
    unittest.main()
