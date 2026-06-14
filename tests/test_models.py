import unittest

from citybuilder.models import BuildingType, CityStats, Tile, ZoneType
from citybuilder.settings import MAX_TAX_RATE, MIN_TAX_RATE


class TileTests(unittest.TestCase):
    def test_clear_resets_tile_to_empty_defaults(self) -> None:
        tile = Tile(
            zone=ZoneType.COMMERCIAL,
            building=BuildingType.SCHOOL,
            has_road=True,
            has_power_line=True,
            has_water_pipe=True,
            development=0.8,
            residents=5,
            jobs=12,
            land_value=1.2,
            powered=True,
            watered=True,
            police_coverage=True,
            fire_coverage=True,
            education_coverage=True,
        )

        tile.clear()

        self.assertEqual(tile.zone, ZoneType.EMPTY)
        self.assertEqual(tile.building, BuildingType.NONE)
        self.assertFalse(tile.has_road)
        self.assertFalse(tile.has_power_line)
        self.assertFalse(tile.has_water_pipe)
        self.assertEqual(tile.development, 0.0)
        self.assertEqual(tile.residents, 0)
        self.assertEqual(tile.jobs, 0)
        self.assertEqual(tile.land_value, 1.0)
        self.assertFalse(tile.powered)
        self.assertFalse(tile.watered)
        self.assertFalse(tile.police_coverage)
        self.assertFalse(tile.fire_coverage)
        self.assertFalse(tile.education_coverage)
        self.assertTrue(tile.is_empty)


class CityStatsTests(unittest.TestCase):
    def test_new_city_starts_paused(self) -> None:
        stats = CityStats()

        self.assertTrue(stats.paused)
        self.assertIn("paused", stats.messages[0])

    def test_tax_rate_is_clamped_to_allowed_range(self) -> None:
        stats = CityStats()

        stats.change_tax_rate(100)
        self.assertEqual(stats.tax_rate, MAX_TAX_RATE)

        stats.change_tax_rate(-100)
        self.assertEqual(stats.tax_rate, MIN_TAX_RATE)

    def test_advance_month_rolls_into_next_year(self) -> None:
        stats = CityStats(year=3, month=12)

        stats.advance_month()

        self.assertEqual(stats.year, 4)
        self.assertEqual(stats.month, 1)

    def test_add_message_skips_duplicates_and_keeps_latest_five(self) -> None:
        stats = CityStats(messages=[])

        for message in ["A", "A", "B", "C", "D", "E", "F"]:
            stats.add_message(message)

        self.assertEqual(stats.messages, ["B", "C", "D", "E", "F"])

    def test_demand_for_returns_zone_demand(self) -> None:
        stats = CityStats(demand_residential=70, demand_commercial=40, demand_industrial=55)

        self.assertEqual(stats.demand_for(ZoneType.RESIDENTIAL), 70)
        self.assertEqual(stats.demand_for(ZoneType.COMMERCIAL), 40)
        self.assertEqual(stats.demand_for(ZoneType.INDUSTRIAL), 55)
        self.assertEqual(stats.demand_for(ZoneType.EMPTY), 0)


if __name__ == "__main__":
    unittest.main()
