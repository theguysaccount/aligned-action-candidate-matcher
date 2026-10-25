"""Tests: roll-call selection, bill records, quiz choice and a full site build, guarded."""
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import fixtures as F  # noqa: E402
from matcher import bills, build, common, fec, guard, og, rollcalls, select  # noqa: E402

NOW = datetime(2026, 10, 25, 21, 0, tzinfo=timezone.utc)
PRONOUNS = re.compile(r"\b(he|she|him|his|her|hers|himself|herself)\b", re.I)


def fixture_bills():
    out = {}
    for bill, xml in (("HR10", F.BILLSTATUS_HR10), ("SJRES2", F.BILLSTATUS_SJRES2)):
        rec = bills.parse(xml)
        typ, num = bills.split_bill(bill)
        rec["congress_gov"] = f"https://www.congress.gov/bill/119th-congress/{bills.TYPE_PATH[typ]}/{num}"
        rec["source"] = f"https://www.govinfo.gov/bulkdata/BILLSTATUS/119/{typ.lower()}/BILLSTATUS-119{typ.lower()}{num}.xml"
        out[bill] = rec
    return out


class RollcallTest(unittest.TestCase):
    def setUp(self):
        self.out = rollcalls.build(F.vote_texts())

    def test_keeps_only_contested_final_votes_on_bills(self):
        keys = sorted(self.out["rollcalls"])
        self.assertEqual(keys, ["H-1", "H-4", "H-5", "S-1", "S-3"], "no simple resolution, unanimous vote or nomination")

    def test_votes_and_tallies(self):
        r = self.out["rollcalls"]["H-4"]
        self.assertEqual(r["votes"]["B000002"], "9")
        self.assertEqual(r["party"], {"D": [2, 0], "R": [0, 2]})
        self.assertEqual(r["url"], "https://clerk.house.gov/Votes/202540")
        self.assertEqual(self.out["rollcalls"]["S-3"]["url"], "https://www.senate.gov/legislative/LIS/roll_call_votes/vote1192/vote_119_2_00005.htm")

    def test_members(self):
        m = self.out["members"]
        self.assertEqual(m["B000002"]["name"], "Bob Baker")
        self.assertTrue(m["N000005"]["delegate"])
        self.assertEqual(m["H000013"]["caucus"], "Democrat")
        self.assertEqual(m["A000001"]["fec_ids"], ["H6AA00001"])


class BillsTest(unittest.TestCase):
    def test_parse(self):
        b = bills.parse(F.BILLSTATUS_HR10)
        self.assertEqual(b["policy_area"], "Health")
        self.assertEqual(b["short_title"], "Example Act")
        self.assertEqual(b["law"], "Public Law 119-5")
        self.assertIn("No. 1 items", b["summary"], "the last listed summary is the most advanced text")
        self.assertNotIn("<p>", b["summary"])


class SelectTest(unittest.TestCase):
    def setUp(self):
        self.rc = rollcalls.build(F.vote_texts())
        self.items = select.items(self.rc, fixture_bills())

    def test_items_use_the_last_final_vote_per_chamber(self):
        it = self.items["HR10"]
        self.assertEqual(it["votes"], {"House": "H-4", "Senate": "S-1"})
        self.assertEqual(it["title"], "Example Act")
        self.assertEqual(it["headline"], "This bill requires the U.S. Department of Health to publish prices for No. 1 items.")

    def test_disapproval_names(self):
        it = self.items["SJRES2"]
        self.assertTrue(it["disapproval"])
        self.assertEqual(it["title"], "Overturn the Department of Energy rule “Energy Conservation Program: Efficiency Standards for Widgets”")

    def test_quiz_rules(self):
        q = select.choose_quiz(self.items, self.rc, F.CFG, date(2026, 10, 25))
        self.assertEqual([it["bill"] for it in q], ["HR10", "SJRES2"])
        cfg = json.loads(json.dumps(F.CFG))
        cfg["quiz"]["max_disapprovals"] = 0
        self.assertEqual([it["bill"] for it in select.choose_quiz(self.items, self.rc, cfg, date(2026, 10, 25))], ["HR10"])

    def test_headline_skips_title_line_and_abbreviations(self):
        self.assertEqual(select.headline("Secure Act\nThis act gives U.S. Customs and Border Protection $5. More.", "Secure Act"),
                         "This act gives U.S. Customs and Border Protection $5.")


class FecTest(unittest.TestCase):
    def test_build_keeps_this_cycle_and_no_addresses(self):
        out = fec.build(F.CN_TEXT, 2026)
        self.assertEqual(list(out), ["H6AA00001"])
        self.assertNotIn("PRIVATE", json.dumps(out))


class SiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.data = os.path.join(cls.tmp, "data")
        os.makedirs(cls.data)
        rc = rollcalls.build(F.vote_texts(), versions={"H_votes": {"last_modified": "Thu, 01 Oct 2026 07:01:56 GMT"}})
        common.write_json(os.path.join(cls.data, "rollcalls.json"), rc)
        common.write_json(os.path.join(cls.data, "bills.json"), {"bills": fixture_bills()})
        common.write_json(os.path.join(cls.data, "candidates2026.json"), {"candidates": fec.build(F.CN_TEXT, 2026)})
        common.write_json(os.path.join(cls.data, "status.json"), {})
        cls.out = os.path.join(cls.tmp, "site")
        orig = build.load_config
        build.load_config = lambda: F.CFG
        try:
            cls.site = build.build(out=cls.out, site_url="https://example.test/aligned-action-candidate-matcher", env={}, now=NOW, data_dir=cls.data)
        finally:
            build.load_config = orig
        find = og.find_chrome
        og.find_chrome = lambda: None
        try:
            og.run(cls.out, cls.site.m)
        finally:
            og.find_chrome = find

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def read(self, rel):
        with open(os.path.join(self.out, rel), encoding="utf-8") as f:
            return f.read()

    def test_quiz_data(self):
        quiz = json.loads(self.read("data/quiz.json"))
        matrix = json.loads(self.read("data/matrix.json"))
        self.assertEqual([it["id"] for it in quiz["items"]], ["hr10", "sjres2"])
        house = matrix["House"]
        names = [m[1] for m in house["members"]]
        self.assertNotIn("Nell North", names, "delegates are not ranked")
        self.assertEqual(len(house["votes"]["hr10"]), len(names))
        alice = names.index("Alice Adams")
        bob = names.index("Bob Baker")
        self.assertEqual(house["votes"]["hr10"][alice], "Y")
        self.assertEqual(house["votes"]["hr10"][bob], "-", "missed vote")
        self.assertEqual(house["members"][alice][6], 1, "Alice is a 2026 statutory candidate")
        self.assertEqual(matrix["Senate"]["votes"]["sjres2"], "NYY")

    def test_pages_cite_sources(self):
        html = self.read("bills/h-r-10-example-act/index.html")
        self.assertIn("https://clerk.house.gov/Votes/202540", html)
        self.assertIn("Congressional Research Service", html)
        self.assertIn("Public Law 119-5", html)
        m = self.read("members/alice-adams-aa/index.html")
        self.assertIn("On the 2026 ballot for U.S. House", m)
        self.assertIn("../../bills/h-r-10-example-act/", m)

    def test_no_gendered_pronouns(self):
        for rel in ["index.html", "members/alice-adams-aa/index.html", "members/hal-hale-bb/index.html", "states/aa/index.html", "methodology/index.html"]:
            text, _ = guard.visible_text(self.read(rel))
            self.assertIsNone(PRONOUNS.search(text), rel)

    def test_guard_passes(self):
        saved = guard.MIN_BILLS, guard.MIN_MEMBERS, guard.MIN_QUIZ
        guard.MIN_BILLS, guard.MIN_MEMBERS, guard.MIN_QUIZ = 1, 1, 1
        try:
            errors, _ = guard.check(self.out)
        finally:
            guard.MIN_BILLS, guard.MIN_MEMBERS, guard.MIN_QUIZ = saved
        errors = [e for e in errors if "matrix House has" not in e and "matrix Senate has" not in e]
        self.assertEqual(errors, [])


@unittest.skipUnless(os.path.exists(os.path.join(common.DATA, "rollcalls.json")), "no committed data yet")
class CommittedDataTest(unittest.TestCase):
    def test_build_and_guard(self):
        tmp = tempfile.mkdtemp()
        try:
            site = build.build(out=tmp, env={})
            find = og.find_chrome
            og.find_chrome = lambda: None
            try:
                og.run(tmp, site.m)
            finally:
                og.find_chrome = find
            errors, counts = guard.check(tmp)
            self.assertEqual(errors, [])
            self.assertGreaterEqual(len(site.m.quiz), 10)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
