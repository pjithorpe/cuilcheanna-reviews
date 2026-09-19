"""Lean regression tests: enough to catch a FreeToBook markup change or a
merge bug. The fixture is a real /reviews/get fragment captured 2026-09-19."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scrape  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "reviews_fragment.html")


def review(name, date, comment, rating=5.0):
    return {
        "name": name,
        "date": date,
        "date_iso": scrape.iso_date(date),
        "rating": rating,
        "comment": comment,
    }


class ParseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(FIXTURE, encoding="utf-8") as f:
            cls.parsed = scrape.parse_reviews(f.read())
        cls.commented = [r for r in cls.parsed if r["comment"]]

    def test_finds_every_review_and_the_commented_subset(self):
        self.assertEqual(len(self.parsed), 45)
        self.assertEqual(len(self.commented), 35)

    def test_empty_reviews_have_no_comment_text(self):
        # "No comment submitted." must become "", not leak through as a comment.
        self.assertEqual(len(self.parsed) - len(self.commented), 10)
        for r in self.parsed:
            self.assertNotIn("No comment submitted", r["comment"])

    def test_hidden_detail_block_does_not_leak_into_comments(self):
        for r in self.commented:
            for leaked in ("Ratings", "Cleanliness", "Staff/Service", "Tips"):
                self.assertNotIn(leaked, r["comment"], msg=r["comment"][:120])

    def test_fields_are_populated(self):
        for r in self.commented:
            self.assertTrue(r["name"].startswith("Guest from"))
            self.assertIsNotNone(r["date_iso"], msg=r["date"])
            self.assertIsInstance(r["rating"], float)

    def test_five_star_reviews_exist_for_the_front_end_filter(self):
        # The site shows 5.0-only, so a parse that lost ratings must not pass.
        five_star = [r for r in self.commented if r["rating"] == 5.0]
        self.assertGreaterEqual(len(five_star), 20)


class MergeTests(unittest.TestCase):
    def test_accumulates_dedups_and_sorts_newest_first(self):
        dropped = review("Guest from London", "27th December, 2025", "Older stay.")
        current = [
            review("Guest from Penrith", "27th August, 2026", "Superb views."),
            review("Guest from Edinburgh", "1st February, 2026", "Immaculate."),
        ]

        merged, added = scrape.merge([dropped], current)

        self.assertEqual(added, 2)
        self.assertEqual([r["date_iso"] for r in merged],
                         ["2026-08-27", "2026-02-01", "2025-12-27"])

    def test_is_idempotent(self):
        current = [review("Guest from Mull", "3rd September, 2026", "Lovely.")]
        once, _ = scrape.merge([], current)
        twice, added = scrape.merge(once, current)

        self.assertEqual(added, 0)
        self.assertEqual(once, twice)

    def test_backfills_date_iso_on_legacy_records(self):
        legacy = {
            "name": "Guest from Oban",
            "date": "1st February, 2026",
            "rating": 5.0,
            "comment": "Written before date_iso existed.",
        }
        merged, _ = scrape.merge([legacy], [])
        self.assertEqual(merged[0]["date_iso"], "2026-02-01")


class WriteTests(unittest.TestCase):
    """main() must not rewrite the file when the reviews are unchanged --
    otherwise the 'updated' timestamp alone produces a commit every day."""

    def setUp(self):
        self._saved = (scrape.HTML_FILE, scrape.OUT_PATH)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        scrape.HTML_FILE = FIXTURE
        scrape.OUT_PATH = os.path.join(self.tmp.name, "reviews.json")

    def tearDown(self):
        scrape.HTML_FILE, scrape.OUT_PATH = self._saved

    def test_second_run_is_a_no_op(self):
        self.assertEqual(scrape.main(), 0)
        first = open(scrape.OUT_PATH, encoding="utf-8").read()
        self.assertEqual(json.loads(first)["count"], 35)

        self.assertEqual(scrape.main(), 0)
        self.assertEqual(open(scrape.OUT_PATH, encoding="utf-8").read(), first)


class DateTests(unittest.TestCase):
    def test_parses_and_tolerates_junk(self):
        self.assertEqual(scrape.iso_date("18th September, 2026"), "2026-09-18")
        self.assertEqual(scrape.iso_date("3rd September, 2026"), "2026-09-03")
        self.assertIsNone(scrape.iso_date("who knows"))
        self.assertIsNone(scrape.iso_date(""))


if __name__ == "__main__":
    unittest.main()
