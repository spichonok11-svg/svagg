from django.test import TestCase, override_settings


@override_settings(
    GO_PARSER_URL="http://127.0.0.1:1/parse",
    TOUR_CACHE_TTL_SECONDS=3600,
    LIVE_PARSER_ENABLED=False,
)
class TourApiTests(TestCase):
    def test_health_endpoint(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(payload["toursInCache"], 1)
        self.assertIn("queryCacheHits", payload)
        self.assertIn("queryCacheMisses", payload)
        self.assertIn("queryCacheSize", payload)

    def test_price_and_category_filter(self):
        response = self.client.get(
            "/api/tours",
            {"pricePerPerson": "7000", "category": "mountains"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["count"], 1)
        for item in payload["tours"]:
            self.assertEqual(item["pricePerPerson"], 7000)
            self.assertIn("mountains", item["categories"])

    def test_search_sort_and_pagination(self):
        response = self.client.get(
            "/api/tours",
            {"q": "weekend", "sort": "days_desc", "limit": "1", "offset": "0"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["returned"], 1)
        self.assertGreaterEqual(payload["count"], 1)

        next_response = self.client.get(
            "/api/tours",
            {"q": "weekend", "sort": "days_desc", "limit": "1", "offset": "1"},
        )
        self.assertEqual(next_response.status_code, 200)
        next_payload = next_response.json()
        self.assertEqual(next_payload["returned"], 1)

    def test_stats_endpoint(self):
        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["totalTours"], 1)
        self.assertIsNotNone(payload["priceMin"])
        self.assertIsNotNone(payload["priceMax"])
        self.assertIn("topRegions", payload)

    def test_invalid_query_params_are_safely_handled(self):
        response = self.client.get(
            "/api/tours",
            {
                "sort": "unknown_value",
                "limit": "bad",
                "offset": "bad",
                "minPrice": "9000",
                "maxPrice": "5000",
                "category": "unknown_category",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("tours", payload)
        self.assertIn("count", payload)

    def test_city_suggestions_and_price_options(self):
        cities_response = self.client.get("/api/cities", {"q": "м"})
        self.assertEqual(cities_response.status_code, 200)
        cities_payload = cities_response.json()
        self.assertIn("cities", cities_payload)
        self.assertIsInstance(cities_payload["cities"], list)

        prices_response = self.client.get("/api/price-options")
        self.assertEqual(prices_response.status_code, 200)
        prices_payload = prices_response.json()
        self.assertEqual(prices_payload["options"][0], 5000)
        self.assertEqual(prices_payload["options"][-1], 100000)
