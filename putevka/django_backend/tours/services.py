from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import xml.etree.ElementTree as ET
from bisect import bisect_left, bisect_right
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from django.conf import settings

from .constants import VALID_CATEGORY_IDS

DATA_FILE = Path(settings.PROJECT_ROOT) / "data" / "offers.json"
TOKEN_PATTERN = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]+")
SCRIPT_JSONLD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
VALID_SORTS = {"price_asc", "price_desc", "days_asc", "days_desc"}
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
PAGE_REGION_MAP = {
    "krasnodar": "Краснодарский край",
    "adler": "Адлер",
    "anapa": "Анапа",
    "gelendzhik": "Геленджик",
    "tuapse": "Туапсе",
    "lazarevskoe": "Лазаревское",
    "divnomorskoe": "Дивноморское",
    "kavminvody": "Ставропольский край",
    "kislovodsk": "Кисловодск",
    "essentuky": "Ессентуки",
    "pyatigorsk": "Пятигорск",
    "zheleznovodsk": "Железноводск",
    "mineralnye-vody": "Минеральные Воды",
    "altay": "Алтай",
    "belokurikha": "Белокуриха",
    "gorno-altaysk": "Горно-Алтайск",
    "yarovoe": "Яровое",
    "teletskoye-ozero": "Телецкое озеро",
    "krym": "Крым",
    "yalta": "Ялта",
    "alushta": "Алушта",
    "sudak": "Судак",
    "feodosiya": "Феодосия",
    "evpatoria": "Евпатория",
    "saky": "Саки",
    "respublika-kareliya": "Республика Карелия",
    "kareliya": "Республика Карелия",
    "moskva": "Москва",
    "sankt-peterburg": "Санкт-Петербург",
    "kaliningrad": "Калининград",
    "respublika-dagestan": "Республика Дагестан",
    "bashkortostan": "Башкортостан",
    "leningradskaya-oblast": "Ленинградская область",
    "moskovskaya-oblast": "Московская область",
    "irkutskaya-oblast": "Иркутская область",
    "primorskii-krai": "Приморский край",
}

_cache_lock = threading.RLock()
_cached_tours = []
_cached_by_id = {}
_cached_sorted_ids = []
_cached_price_values = []
_cached_price_index = {}
_cached_category_index = {}
_cached_search_index = {}
_cache_updated_at = None
_cache_source = "local"
_cache_expires_at = 0.0
_cache_generation = 0
_last_refresh_note = ""

_result_cache = {}
_result_cache_hits = 0
_result_cache_misses = 0


def _to_iso_utc(timestamp: datetime | None) -> str | None:
    if timestamp is None:
        return None
    return timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _safe_int(value):
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text or "")]


def _find_product_nodes(json_data):
    stack = [json_data]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            current_type = current.get("@type")
            if current_type == "Product" and isinstance(current.get("offers"), dict):
                yield current
            for value in current.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(current, list):
            for item in current:
                if isinstance(item, (dict, list)):
                    stack.append(item)


def _infer_region_from_page(page_url: str) -> str:
    path_parts = [part for part in urlparse(page_url).path.split("/") if part]
    for part in path_parts:
        if part in PAGE_REGION_MAP:
            return PAGE_REGION_MAP[part]
    if len(path_parts) >= 2:
        return path_parts[-2].replace("-", " ").title()
    if path_parts:
        return path_parts[-1].replace("-", " ").title()
    return "Россия"


def _infer_categories(name: str, url: str, page_url: str, region: str) -> list[str]:
    text = f"{name} {url} {page_url} {region}".lower()
    categories = {"with_hotel"}

    if any(token in text for token in ["бассейн", "pool", "spa", "аква"]):
        categories.add("with_pool")
    else:
        categories.add("without_pool")

    if any(token in text for token in ["гора", "горн", "кавмин", "altay", "эльбрус", "домбай"]):
        categories.add("mountains")

    if any(token in text for token in ["лес", "карел", "taiga", "эко", "заповед"]):
        categories.add("forest")

    if any(token in text for token in ["берег", "море", "пляж", "озер", "адлер", "sochi", "крым"]):
        categories.add("waterfront")

    if any(token in text for token in ["family", "дет", "сем", "ребен"]):
        categories.add("family")

    if any(token in text for token in ["all inclusive", "все включено", "all-inclusive"]):
        categories.add("all_inclusive")

    if any(token in text for token in ["база отдыха", "турбаза", "пансионат", "санатор"]):
        categories.add("recreation_base")

    if "with_hotel" not in categories:
        categories.add("without_hotel")
    if "with_pool" not in categories and "without_pool" not in categories:
        categories.add("without_pool")
    if not ({"mountains", "forest", "recreation_base", "waterfront"} & categories):
        categories.add("recreation_base")

    return [category for category in categories if category in VALID_CATEGORY_IDS]


def _normalize_offer_link(raw_url: str, page_url: str) -> str:
    normalized = str(raw_url or "").strip()
    if not normalized:
        return ""

    absolute = urljoin(page_url, normalized)
    split = urlsplit(absolute)
    # Remove URL fragment to keep a stable canonical link.
    absolute = urlunsplit((split.scheme, split.netloc, split.path, split.query, ""))
    return absolute


def _is_russia_country(country_value: str) -> bool:
    country_text = str(country_value or "").strip().lower()
    if not country_text:
        return True
    return "рос" in country_text or "russia" in country_text


def _extract_country_from_address(address: dict) -> str:
    raw_country = address.get("addressCountry")
    if isinstance(raw_country, dict):
        country_name = (
            raw_country.get("name")
            or raw_country.get("title")
            or raw_country.get("@id")
            or raw_country.get("addressCountry")
        )
        return str(country_name or "").strip()
    return str(raw_country or "").strip()


def _normalize_live_offer(offer_data: dict, page_url: str):
    raw_price = _safe_int(offer_data.get("price"))
    if raw_price is None:
        return None

    name = str(offer_data.get("name", "")).strip()
    url = _normalize_offer_link(str(offer_data.get("url", "")).strip(), page_url=page_url)
    if not name or not url:
        return None
    path_parts = [part for part in urlparse(url).path.split("/") if part]
    if len(path_parts) < 2:
        return None

    rating_info = offer_data.get("aggregateRating", {}) or {}
    reviewed = rating_info.get("itemReviewed", {}) or {}
    address = reviewed.get("address", {}) or {}
    country = _extract_country_from_address(address)
    if not _is_russia_country(country):
        return None
    locality = str(address.get("addressLocality", "")).strip()
    region = str(address.get("addressRegion", "")).strip() or _infer_region_from_page(page_url)
    city = locality or region
    title = name
    categories = _infer_categories(name=name, url=url, page_url=page_url, region=region)
    if not categories:
        return None

    price_per_person = max(3000, min(raw_price * 2, 100000))
    description = "Актуальная путевка с подтвержденной ценой."
    stable_id = hashlib.md5(f"{url}|{city}".encode("utf-8")).hexdigest()[:16]
    search_text = f"{title} {city} {region} {description}".lower()

    return {
        "id": f"putevka_live:{stable_id}",
        "source": "putevka_live",
        "title": title,
        "city": city,
        "region": region if region else (locality or "Россия"),
        "country": "Россия",
        "pricePerPerson": price_per_person,
        "days": 7,
        "categories": categories,
        "hasHotel": "with_hotel" in categories,
        "hasPool": "with_pool" in categories,
        "description": description,
        "link": url,
        "_search": search_text,
        "_tokens": _tokenize(search_text),
    }


def _extract_live_offers_from_html(html: str, page_url: str) -> list[dict]:
    extracted = []
    for script_match in SCRIPT_JSONLD_RE.finditer(html):
        raw_json = script_match.group(1).strip()
        if not raw_json:
            continue
        try:
            json_data = json.loads(raw_json)
        except json.JSONDecodeError:
            continue

        for product in _find_product_nodes(json_data):
            offers_wrapper = product.get("offers", {})
            offers = offers_wrapper.get("offers")
            if not isinstance(offers, list):
                continue
            for offer in offers:
                if not isinstance(offer, dict):
                    continue
                normalized = _normalize_live_offer(offer, page_url=page_url)
                if normalized:
                    extracted.append(normalized)
    return extracted


def _fetch_live_page(page_url: str) -> list[dict]:
    request = Request(page_url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=15) as response:
        html = response.read().decode("utf-8", errors="ignore")
    return _extract_live_offers_from_html(html, page_url=page_url)


def _fetch_live_pages(page_urls: list[str], max_workers: int = 10) -> list[dict]:
    if not page_urls:
        return []

    collected = []
    workers = max(2, min(max_workers, len(page_urls)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_fetch_live_page, page_url): page_url for page_url in page_urls}
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception:
                continue
            if result:
                collected.extend(result)
    return collected


def _load_sitemap_region_urls(limit: int) -> list[str]:
    sitemap_url = getattr(
        settings,
        "PUTEVKA_REGIONS_SITEMAP_URL",
        "https://www.putevka.com/sitemaps/regions.xml",
    )
    request = Request(sitemap_url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=25) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)
    urls = []
    for node in root.findall(".//sm:url/sm:loc", SITEMAP_NS):
        loc = str(node.text or "").strip()
        if not loc:
            continue
        if any(skip_token in loc for skip_token in ["/blog/", "/trip/", "/sights/", "/hotels/"]):
            continue
        urls.append(loc)

    deduped = list(dict.fromkeys(urls))
    safe_limit = max(1, limit)
    return deduped[:safe_limit]


def _load_live_putevka() -> list[dict]:
    if not settings.LIVE_PARSER_ENABLED:
        raise RuntimeError("Live parser disabled by settings")

    seed_urls = list(getattr(settings, "PUTEVKA_REGION_URLS", []) or [])
    if not seed_urls:
        raise RuntimeError("No live parser URLs configured")

    deduped_urls = list(dict.fromkeys(seed_urls))
    deduped_tours = {}
    for item in _fetch_live_pages(deduped_urls):
        deduped_tours[item["id"]] = item

    target_min_tours = max(0, int(getattr(settings, "PUTEVKA_MIN_TOURS_TARGET", 1200) or 0))
    sitemap_enabled = bool(getattr(settings, "PUTEVKA_SITEMAP_ENABLED", True))
    if sitemap_enabled and len(deduped_tours) < target_min_tours:
        sitemap_limit = max(50, int(getattr(settings, "PUTEVKA_SITEMAP_REGIONS_LIMIT", 320) or 320))
        sitemap_urls = _load_sitemap_region_urls(sitemap_limit)
        remaining_urls = [url for url in sitemap_urls if url not in deduped_urls]

        # Fetch sitemap pages in batches so we can stop early once enough tours are collected.
        batch_size = 120
        for start in range(0, len(remaining_urls), batch_size):
            batch_urls = remaining_urls[start : start + batch_size]
            for item in _fetch_live_pages(batch_urls):
                deduped_tours[item["id"]] = item
            if len(deduped_tours) >= target_min_tours:
                break

    tours = sorted(deduped_tours.values(), key=lambda item: item["pricePerPerson"])
    if not tours:
        raise RuntimeError("No offers parsed from live sources")

    return tours


def _normalize_record(record, source_name: str):
    price_per_person = _safe_int(record.get("pricePerPerson"))
    if price_per_person is None:
        return None

    country = str(record.get("country", "")).lower()
    if "росс" not in country and "russia" not in country:
        return None

    categories = [
        category_id
        for category_id in record.get("categories", [])
        if category_id in VALID_CATEGORY_IDS
    ]
    if not categories:
        return None

    title = str(record.get("title", "Путевка по России"))
    region = str(record.get("region", "Россия"))
    city = str(record.get("city", "")).strip() or region
    description = str(record.get("description", ""))
    search_text = " ".join([title, city, region, description]).lower()

    return {
        "id": f"{source_name}:{record.get('id', 'unknown')}",
        "source": source_name,
        "title": title,
        "city": city,
        "region": region,
        "country": "Россия",
        "pricePerPerson": price_per_person,
        "days": _safe_int(record.get("days")) or 5,
        "categories": categories,
        "hasHotel": "with_hotel" in categories,
        "hasPool": "with_pool" in categories,
        "description": description,
        "link": str(record.get("link", "#")),
        "_search": search_text,
        "_tokens": _tokenize(search_text),
    }


def _load_local() -> list[dict]:
    raw = DATA_FILE.read_text(encoding="utf-8")
    records = json.loads(raw)
    tours = [_normalize_record(record, "local_json") for record in records]
    return sorted([tour for tour in tours if tour], key=lambda item: item["pricePerPerson"])


def _load_from_go() -> list[dict]:
    request = Request(settings.GO_PARSER_URL, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=4) as response:
        payload = json.loads(response.read().decode("utf-8"))
    records = payload.get("tours", [])
    tours = [_normalize_record(record, "go_parser") for record in records]
    tours = sorted([tour for tour in tours if tour], key=lambda item: item["pricePerPerson"])
    if not tours:
        raise RuntimeError("Go parser returned empty list")
    return tours


def _refresh_unlocked(force: bool = False):
    global _cached_tours
    global _cached_by_id
    global _cached_sorted_ids
    global _cached_price_values
    global _cached_price_index
    global _cached_category_index
    global _cached_search_index
    global _cache_updated_at
    global _cache_source
    global _cache_expires_at
    global _cache_generation
    global _last_refresh_note
    global _result_cache
    global _result_cache_hits
    global _result_cache_misses

    now = time.time()
    if not force and _cached_tours and now < _cache_expires_at:
        return

    live_error = None
    go_error = None
    try:
        tours = _load_live_putevka()
        source_name = "live_putevka"
        _last_refresh_note = f"Используется live-парсер putevka.com ({len(tours)} предложений)."
    except Exception as error:
        live_error = error
        try:
            tours = _load_from_go()
            source_name = "go"
            _last_refresh_note = f"Live-парсер недоступен, взяты данные из go parser: {error}"
        except Exception as go_exception:
            go_error = go_exception
            tours = _load_local()
            source_name = "local_fallback"
            _last_refresh_note = (
                f"Live-парсер недоступен ({live_error}), go parser недоступен ({go_error}), "
                "используется локальный fallback."
            )

    by_id = {}
    sorted_ids = []
    price_values = []
    price_index = {}
    category_index = {}
    search_index = {}

    for tour in tours:
        tour_id = tour["id"]
        by_id[tour_id] = tour
        sorted_ids.append(tour_id)
        price_values.append(tour["pricePerPerson"])
        price_index.setdefault(tour["pricePerPerson"], []).append(tour_id)
        for category in tour["categories"]:
            category_index.setdefault(category, set()).add(tour_id)
        for token in set(tour["_tokens"]):
            search_index.setdefault(token, set()).add(tour_id)

    _cached_tours = tours
    _cached_by_id = by_id
    _cached_sorted_ids = sorted_ids
    _cached_price_values = price_values
    _cached_price_index = price_index
    _cached_category_index = category_index
    _cached_search_index = search_index
    _cache_updated_at = datetime.now(UTC)
    _cache_source = source_name
    _cache_expires_at = now + max(settings.TOUR_CACHE_TTL_SECONDS, 30)
    _cache_generation += 1

    _result_cache = {}
    _result_cache_hits = 0
    _result_cache_misses = 0


def ensure_cache():
    with _cache_lock:
        _refresh_unlocked(force=False)


def force_refresh():
    with _cache_lock:
        _refresh_unlocked(force=True)


def _normalize_query(
    *,
    price_per_person=None,
    min_price=None,
    max_price=None,
    categories=None,
    city=None,
    query=None,
    sort="price_asc",
    limit=50,
    offset=0,
):
    price_per_person = _safe_int(price_per_person)
    min_price = _safe_int(min_price)
    max_price = _safe_int(max_price)
    if min_price is not None and max_price is not None and min_price > max_price:
        min_price, max_price = max_price, min_price

    sort = sort if sort in VALID_SORTS else "price_asc"
    limit = _safe_int(limit) or 50
    limit = max(1, min(limit, 200))
    offset = _safe_int(offset) or 0
    offset = max(0, offset)

    normalized_categories = tuple(
        sorted({category for category in (categories or []) if category in VALID_CATEGORY_IDS})
    )
    city = str(city or "").strip().lower()
    query = str(query or "").strip().lower()
    query_tokens = tuple(_tokenize(query)[:6])

    return {
        "price_per_person": price_per_person,
        "min_price": min_price,
        "max_price": max_price,
        "categories": normalized_categories,
        "city": city,
        "query": query,
        "query_tokens": query_tokens,
        "sort": sort,
        "limit": limit,
        "offset": offset,
    }


def _match_tour_with_query(tour: dict, normalized_query: dict) -> bool:
    min_price = normalized_query["min_price"]
    max_price = normalized_query["max_price"]
    query = normalized_query["query"]

    if min_price is not None and tour["pricePerPerson"] < min_price:
        return False
    if max_price is not None and tour["pricePerPerson"] > max_price:
        return False
    if query and query not in tour["_search"]:
        return False
    return True


def _build_candidate_ids_unlocked(normalized_query: dict) -> list[str]:
    price_per_person = normalized_query["price_per_person"]
    min_price = normalized_query["min_price"]
    max_price = normalized_query["max_price"]
    categories = normalized_query["categories"]
    city = normalized_query["city"]
    query = normalized_query["query"]
    query_tokens = normalized_query["query_tokens"]

    if price_per_person is not None:
        candidate_ids = list(_cached_price_index.get(price_per_person, []))
    else:
        left = 0
        right = len(_cached_sorted_ids)
        if min_price is not None:
            left = bisect_left(_cached_price_values, min_price)
        if max_price is not None:
            right = bisect_right(_cached_price_values, max_price)
        candidate_ids = list(_cached_sorted_ids[left:right])

    if categories:
        allowed_ids = None
        for category in categories:
            ids = _cached_category_index.get(category, set())
            if allowed_ids is None:
                allowed_ids = set(ids)
            else:
                allowed_ids &= ids
        allowed_ids = allowed_ids or set()
        candidate_ids = [tour_id for tour_id in candidate_ids if tour_id in allowed_ids]

    if city:
        candidate_ids = [
            tour_id
            for tour_id in candidate_ids
            if str(_cached_by_id[tour_id].get("city", "")).lower().startswith(city)
        ]

    if query_tokens:
        indexed_ids = None
        for token in query_tokens:
            ids = _cached_search_index.get(token, set())
            if indexed_ids is None:
                indexed_ids = set(ids)
            else:
                indexed_ids &= ids
        indexed_ids = indexed_ids or set()
        candidate_ids = [tour_id for tour_id in candidate_ids if tour_id in indexed_ids]

    if query:
        candidate_ids = [
            tour_id
            for tour_id in candidate_ids
            if _match_tour_with_query(_cached_by_id[tour_id], normalized_query)
        ]

    sort = normalized_query["sort"]
    if sort == "price_desc":
        candidate_ids.reverse()
        return candidate_ids

    if sort in {"days_asc", "days_desc"}:
        reverse = sort == "days_desc"
        candidate_ids.sort(
            key=lambda tour_id: (
                _cached_by_id[tour_id]["days"],
                _cached_by_id[tour_id]["pricePerPerson"],
                _cached_by_id[tour_id]["title"],
            ),
            reverse=reverse,
        )
    return candidate_ids


def filter_tours(
    *,
    price_per_person=None,
    min_price=None,
    max_price=None,
    categories=None,
    city=None,
    query=None,
    sort="price_asc",
    limit=50,
    offset=0,
):
    ensure_cache()
    normalized_query = _normalize_query(
        price_per_person=price_per_person,
        min_price=min_price,
        max_price=max_price,
        categories=categories,
        city=city,
        query=query,
        sort=sort,
        limit=limit,
        offset=offset,
    )

    global _result_cache_hits
    global _result_cache_misses

    with _cache_lock:
        cache_key = (
            _cache_generation,
            normalized_query["price_per_person"],
            normalized_query["min_price"],
            normalized_query["max_price"],
            normalized_query["categories"],
            normalized_query["city"],
            normalized_query["query"],
            normalized_query["sort"],
        )
        matched_ids = _result_cache.get(cache_key)
        if matched_ids is None:
            _result_cache_misses += 1
            matched_ids = _build_candidate_ids_unlocked(normalized_query)
            _result_cache[cache_key] = matched_ids
        else:
            _result_cache_hits += 1

        total_count = len(matched_ids)
        page_ids = matched_ids[
            normalized_query["offset"] : normalized_query["offset"] + normalized_query["limit"]
        ]
        tours = []
        for tour_id in page_ids:
            tours.append({k: v for k, v in _cached_by_id[tour_id].items() if not k.startswith("_")})

        meta = {
            "lastParsedAt": _to_iso_utc(_cache_updated_at),
            "cacheSource": _cache_source,
            "queryCacheHits": _result_cache_hits,
            "queryCacheMisses": _result_cache_misses,
            "refreshNote": _last_refresh_note,
        }
    return tours, meta, total_count


def get_city_suggestions(query=None, limit=12):
    ensure_cache()
    normalized_query = str(query or "").strip().lower()
    safe_limit = _safe_int(limit) or 12
    safe_limit = max(1, min(safe_limit, 50))

    with _cache_lock:
        counter = Counter()
        for tour in _cached_tours:
            city = str(tour.get("city", "")).strip()
            if not city:
                continue
            city_lower = city.lower()
            if normalized_query and not city_lower.startswith(normalized_query):
                continue
            counter[city] += 1

        return [
            {"city": city, "count": count}
            for city, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:safe_limit]
        ]


def get_cache_meta():
    ensure_cache()
    with _cache_lock:
        return {
            "count": len(_cached_tours),
            "lastParsedAt": _to_iso_utc(_cache_updated_at),
            "cacheSource": _cache_source,
            "queryCacheHits": _result_cache_hits,
            "queryCacheMisses": _result_cache_misses,
            "queryCacheSize": len(_result_cache),
            "cacheGeneration": _cache_generation,
            "refreshNote": _last_refresh_note,
        }


def get_stats():
    ensure_cache()
    with _cache_lock:
        prices = [tour["pricePerPerson"] for tour in _cached_tours]
        total = len(_cached_tours)
        if total == 0:
            return {
                "totalTours": 0,
                "priceMin": None,
                "priceMax": None,
                "priceAvg": None,
                "topRegions": [],
                "categoryCounts": {},
                "lastParsedAt": _to_iso_utc(_cache_updated_at),
                "cacheSource": _cache_source,
                "queryCacheHits": _result_cache_hits,
                "queryCacheMisses": _result_cache_misses,
                "queryCacheSize": len(_result_cache),
                "refreshNote": _last_refresh_note,
            }

        region_counter = Counter(tour["region"] for tour in _cached_tours)
        category_counter = Counter()
        for tour in _cached_tours:
            category_counter.update(tour["categories"])

        return {
            "totalTours": total,
            "priceMin": min(prices),
            "priceMax": max(prices),
            "priceAvg": int(round(sum(prices) / total)),
            "topRegions": [
                {"region": region, "count": count}
                for region, count in region_counter.most_common(8)
            ],
            "categoryCounts": dict(category_counter),
            "lastParsedAt": _to_iso_utc(_cache_updated_at),
            "cacheSource": _cache_source,
            "queryCacheHits": _result_cache_hits,
            "queryCacheMisses": _result_cache_misses,
            "queryCacheSize": len(_result_cache),
            "refreshNote": _last_refresh_note,
        }
