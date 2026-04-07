import unittest
from types import SimpleNamespace
from unittest.mock import patch

import app as app_module
from city_labels import assign_labels


class FakeCursor:
    def __init__(self, rows):
        self.description = [
            ("id",),
            ("city",),
            ("country",),
            ("state",),
            ("lat",),
            ("lng",),
        ]
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeCon:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, _sql, _params):
        return FakeCursor(self.rows)


class SearchOrderTests(unittest.TestCase):
    def test_assign_labels_preserves_input_order(self):
        rows = [
            {"id": "2", "city": "Paris", "country": "France", "state": "", "lat": 48.85, "lng": 2.35},
            {"id": "1", "city": "Aenon Town", "country": "Jamaica", "state": "", "lat": 18.2, "lng": -77.4},
        ]
        out = assign_labels(rows)
        self.assertEqual(out[0]["city"], "Paris")
        self.assertEqual(out[1]["city"], "Aenon Town")

    def test_api_cities_keeps_db_relevance_order(self):
        fake_rows = [
            ("2", "Paris", "France", "", 48.85, 2.35),
            ("1", "Aenon Town", "Jamaica", "", 18.2, -77.4),
        ]
        cfg = SimpleNamespace(
            CATALOG_ALIAS="iceberg_catalog",
            CITIES_TABLE_FQN="iceberg_catalog.liewyousheng_geolocation.cities",
            CITY_COLUMNS={},
        )

        with (
            patch.object(app_module, "get_db", return_value=(FakeCon(fake_rows), cfg)),
            app_module.app.test_client() as client,
        ):
            res = client.get("/api/cities?q=paris&limit=10")
            self.assertEqual(res.status_code, 200)
            cities = res.get_json()["cities"]
            self.assertGreaterEqual(len(cities), 2)
            self.assertEqual(cities[0]["city"], "Paris")


if __name__ == "__main__":
    unittest.main()
