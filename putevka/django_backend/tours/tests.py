from django.test import TestCase, override_settings

from .services import (
    _extract_live_offers_from_html,
    filter_tours,
    get_city_suggestions,
)


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

        queries_response = self.client.get("/api/search-suggestions", {"q": "week"})
        self.assertEqual(queries_response.status_code, 200)
        queries_payload = queries_response.json()
        self.assertIn("queries", queries_payload)
        self.assertIsInstance(queries_payload["queries"], list)

        prices_response = self.client.get("/api/price-options")
        self.assertEqual(prices_response.status_code, 200)
        prices_payload = prices_response.json()
        self.assertEqual(prices_payload["options"][0], 5000)
        self.assertEqual(prices_payload["options"][-1], 100000)

    def test_city_suggestion_count_matches_filter_results(self):
        suggestions = get_city_suggestions(limit=1)
        self.assertEqual(len(suggestions), 1)

        city = suggestions[0]["city"]
        expected_count = suggestions[0]["count"]
        tours, _meta, total_count = filter_tours(city=city, limit=200)

        self.assertGreaterEqual(len(tours), 1)
        self.assertEqual(total_count, expected_count)

    def test_city_suggestions_respect_other_filters(self):
        suggestions = get_city_suggestions(
            limit=10,
            categories=["mountains"],
            tour_query="weekend",
        )
        self.assertGreaterEqual(len(suggestions), 1)

        target_city = suggestions[0]["city"]
        _tours, _meta, total_count = filter_tours(
            city=target_city,
            categories=["mountains"],
            query="weekend",
            limit=200,
        )
        self.assertEqual(total_count, suggestions[0]["count"])


class LiveParserExtractionTests(TestCase):
    def test_hotel_room_jsonld_is_extracted(self):
        html = """
        <script type="application/ld+json">
        {
          "@context": "http://schema.org",
          "@type": "Hotel",
          "name": "Санаторий Тест",
          "description": "Отель у моря",
          "address": {
            "@type": "PostalAddress",
            "addressLocality": "Сочи",
            "addressRegion": "Краснодарский край",
            "addressCountry": "Российская Федерация"
          }
        }
        </script>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@graph": [
            {
              "@type": "Product",
              "name": "Стандарт 2-местный",
              "sku": "room-1",
              "brand": {"@type": "Brand", "name": "Санаторий Тест"},
              "description": "Номер с балконом",
              "offers": {
                "@type": "Offer",
                "price": 4400,
                "priceCurrency": "RUB",
                "url": "https://www.putevka.com/krasnodar/sochi/test/nomera"
              }
            }
          ]
        }
        </script>
        <div class="search__element search__element--nights dropdown">
          <label class="search__trigger dropdown-toggle" data-icon="chevron">
            <input id="trigger-nights" type="button" value="7 ночей" data-value="7">
          </label>
          <input type="radio" name="input-nights" data-value="3" value="3 ночи">
          <input type="radio" name="input-nights" data-value="5" value="5 ночей">
          <input type="radio" name="input-nights" data-value="7" value="7 ночей">
        </div>
        """
        offers = _extract_live_offers_from_html(
            html,
            "https://www.putevka.com/krasnodar/sochi/test",
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["city"], "Сочи")
        self.assertEqual(offers[0]["region"], "Краснодарский край")
        self.assertIn("Санаторий Тест", offers[0]["title"])
        self.assertEqual(offers[0]["pricePerPerson"], 4400)
        self.assertEqual(offers[0]["days"], 7)
        self.assertEqual(offers[0]["minNights"], 3)

    def test_listing_offer_uses_offer_name_and_keeps_raw_price(self):
        html = """
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Place",
          "name": "Лазаревское",
          "address": {
            "@type": "PostalAddress",
            "addressLocality": "Лазаревское",
            "addressRegion": "Краснодарский край",
            "addressCountry": "Российская Федерация"
          }
        }
        </script>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org/",
          "@type": "Product",
          "name": "Лазаревского",
          "description": "Санатории Лазаревского",
          "offers": {
            "@type": "AggregateOffer",
            "offers": [
              {
                "@type": "Offer",
                "name": "Санаторий Бирюза",
                "url": "https://www.putevka.com/krasnodar/lazarevskoe/biryuza",
                "price": 4086,
                "priceCurrency": "RUB",
                "aggregateRating": {
                  "@type": "AggregateRating",
                  "itemReviewed": {
                    "@type": "Hotel",
                    "name": "Бирюза",
                    "address": {
                      "@type": "PostalAddress",
                      "addressLocality": "Лазаревское",
                      "addressRegion": "Краснодарский край"
                    }
                  }
                }
              }
            ]
          }
        }
        </script>
        """
        offers = _extract_live_offers_from_html(
            html,
            "https://www.putevka.com/krasnodar/lazarevskoe",
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["title"], "Санаторий Бирюза")
        self.assertEqual(offers[0]["pricePerPerson"], 4086)
        self.assertEqual(offers[0]["minNights"], 1)
