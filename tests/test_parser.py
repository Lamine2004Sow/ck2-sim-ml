import unittest

from ck2sim.extract import year_frac
from ck2sim.parser import Multi, as_list, parse

SAMPLE = b'''
# a comment = ignored
title=
{
	holder=42
	law="a"
	law="b"
	previous= { 1 2 3 }
	history= { 1066.9.15= { holder=1 } 1080.1.1= { holder= { who=2 type=election } } }
	name="Name with # inside"
}
'''


class ParserTest(unittest.TestCase):
    def setUp(self):
        self.t = parse(SAMPLE)["title"]

    def test_comments_are_skipped(self):
        self.assertEqual(list(parse(SAMPLE)), ["title"])

    def test_duplicate_keys_become_multi(self):
        self.assertIsInstance(self.t["law"], Multi)
        self.assertEqual(as_list(self.t["law"]), ["a", "b"])

    def test_bare_list_and_date_keys(self):
        self.assertEqual(self.t["previous"], ["1", "2", "3"])
        self.assertEqual(self.t["history"]["1080.1.1"]["holder"]["who"], "2")

    def test_hash_inside_string_is_kept(self):
        self.assertEqual(self.t["name"], "Name with # inside")

    def test_year_frac(self):
        self.assertEqual(year_frac("1066.1.1"), 1066.0)
        self.assertIsNone(year_frac(None))


if __name__ == "__main__":
    unittest.main()
