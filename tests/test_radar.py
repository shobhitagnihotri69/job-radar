import os
import tempfile
import unittest

from radar import pipeline
from radar.score import score
from radar.sources import HN_TITLE

KW = {"sandbox": 5, "inference": 4, "agents?\\b": 1}


class ScoreTest(unittest.TestCase):
    def test_matches_one_liner_and_industries(self):
        row = {"one_liner": "Cheapest sandbox for AI agents", "description": "", "industries": "Infrastructure"}
        total, hits = score(row, KW)
        self.assertEqual(total, 6)
        self.assertEqual(sorted(hits), sorted(["sandbox", "agents?\\b"]))

    def test_no_match(self):
        row = {"one_liner": "Freight brokerage", "description": "", "industries": "Logistics"}
        self.assertEqual(score(row, KW), (0, []))


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "pipeline.csv")

    def test_track_updates_existing_row(self):
        pipeline.track(self.path, "Acme", "contacted", channel="email")
        pipeline.track(self.path, "acme", "replied")
        rows = pipeline.load(self.path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["stage"], "replied")
        self.assertEqual(rows[0]["channel"], "email")

    def test_rejects_unknown_stage(self):
        with self.assertRaises(ValueError):
            pipeline.track(self.path, "Acme", "hired-maybe")

    def test_funnel_reply_rate(self):
        pipeline.track(self.path, "A", "contacted")
        pipeline.track(self.path, "B", "replied")
        pipeline.track(self.path, "C", "call")
        pipeline.track(self.path, "D", "contacted")
        out = pipeline.funnel(self.path)
        self.assertIn("reply rate: 2/4 = 50%", out)
        self.assertIn("call rate:  1/4 = 25%", out)


class HNTitleTest(unittest.TestCase):
    def test_launch_hn_with_batch(self):
        m = HN_TITLE.match("Launch HN: Maritime (YC F26) \u2013 A managed cloud for production AI agents")
        self.assertEqual((m.group("name"), m.group("batch")), ("Maritime", "YC F26"))
        self.assertEqual(m.group("tag"), "A managed cloud for production AI agents")

    def test_show_hn_without_batch(self):
        m = HN_TITLE.match("Show HN: Tiny VM - microVMs that boot in 50ms")
        self.assertEqual((m.group("name"), m.group("batch"), m.group("tag")),
                         ("Tiny VM", None, "microVMs that boot in 50ms"))


class PolicyPhraseTest(unittest.TestCase):
    def test_detects_closed_policies(self):
        from radar.github import CLOSED_PHRASES
        for text in ["Herdr does not accept unsolicited pull requests",
                     "We are not accepting external contributions right now",
                     "This project won't accept PRs"]:
            self.assertTrue(CLOSED_PHRASES.search(text), text)

    def test_open_policy_not_flagged(self):
        from radar.github import CLOSED_PHRASES
        self.assertIsNone(CLOSED_PHRASES.search("We happily accept pull requests! Open an issue first."))


if __name__ == "__main__":
    unittest.main()
