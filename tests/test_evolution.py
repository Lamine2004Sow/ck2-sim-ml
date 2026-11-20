import unittest

from ck2sim.extract import add_evolution


def realm(date, n, holder="h1", dyn="d1", wars=0):
    return {"realm": "k_x", "snapshot_date": date, "n_counties": n, "holder": holder,
            "holder_dynasty": dyn, "wars_as_attacker": wars, "wars_as_defender": 0}


class EvolutionTest(unittest.TestCase):
    def test_ten_year_deltas_use_only_the_past(self):
        rows = [realm("1230.1.1", 10), realm("1235.1.1", 12, wars=2),
                realm("1240.1.1", 15, holder="h2", wars=1)]
        hist = [{"title": "k_x", "year": 1238.5}, {"title": "k_x", "year": 1100.0}]
        add_evolution(rows, hist)
        first, _, last = rows
        self.assertFalse(first["has_past_10y"])          # nothing 10 years before 1230
        self.assertIsNone(first["n_counties_change_10y"])
        self.assertTrue(last["has_past_10y"])
        self.assertEqual(last["n_counties_change_10y"], 5)
        self.assertEqual(last["n_counties_growth_10y"], 0.5)
        self.assertFalse(last["same_holder_10y"])
        self.assertTrue(last["same_dynasty_10y"])
        self.assertEqual(last["holder_changes_10y"], 1)   # 1238.5 only
        self.assertEqual(last["wars_attacker_mean_10y"], 1.5)  # 1235 and 1240
        self.assertEqual(last["years_observed"], 10)


if __name__ == "__main__":
    unittest.main()
