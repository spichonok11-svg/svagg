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
SNAPSHOT_FILE = Path(settings.PROJECT_ROOT) / "data" / "live_cache_snapshot.json"
PARTIAL_SNAPSHOT_FILE = Path(settings.PROJECT_ROOT) / "data" / "live_cache_progress.json"
TOKEN_PATTERN = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]+")
SCRIPT_JSONLD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
MAX_REASONABLE_PRICE_PER_PERSON = 999_999
VALID_SORTS = {"price_asc", "price_desc", "days_asc", "days_desc"}
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
FOREIGN_PAGE_ROOTS = {
    "abkhazia",
    "belarus",
    "chehija",
    "italiya",
    "kirgiziya",
    "latviya",
    "litva",
    "polsha",
    "serbiya",
    "slovakiya",
    "sloveniya",
    "vengriya",
}
LISTING_PAGE_SUFFIXES = {
    "all-inclusive",
    "beach",
    "basseyny-sanatoriy",
    "cheap",
    "meal",
    "otdyh",
    "spa",
    "vip",
}
TRANSLIT_MULTI_CHAR = (
    ("shch", "щ"),
    ("yo", "ё"),
    ("yu", "ю"),
    ("ya", "я"),
    ("ye", "е"),
    ("zh", "ж"),
    ("kh", "х"),
    ("ts", "ц"),
    ("ch", "ч"),
    ("sh", "ш"),
)
TRANSLIT_SINGLE_CHAR = {
    "a": "а",
    "b": "б",
    "c": "к",
    "d": "д",
    "e": "е",
    "f": "ф",
    "g": "г",
    "h": "х",
    "i": "и",
    "j": "й",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "o": "о",
    "p": "п",
    "q": "к",
    "r": "р",
    "s": "с",
    "t": "т",
    "u": "у",
    "v": "в",
    "w": "в",
    "x": "кс",
    "y": "ы",
    "z": "з",
}
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
_refresh_in_progress = False
_refresh_stage = "idle"
_refresh_target_count = 0
_refresh_started_at = None
_refresh_completed_at = None
_refresh_thread = None
_live_page_cache = {}
_live_page_cache_lock = threading.RLock()
_sitemap_cache = {"urls": [], "expiresAt": 0.0}
_review_cache = {}

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


def _safe_float(value):
    if value in (None, ""):
        return None
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text or "")]


def _schema_has_type(node: dict, expected: str) -> bool:
    current_type = node.get("@type")
    if isinstance(current_type, list):
        return expected in current_type
    return current_type == expected


def _split_page_parts(page_url: str) -> list[str]:
    return [part for part in urlparse(page_url).path.split("/") if part]


def _humanize_slug(slug: str) -> str:
    normalized = str(slug or "").strip().lower().replace("_", "-")
    if not normalized:
        return ""
    if normalized in PAGE_REGION_MAP:
        return PAGE_REGION_MAP[normalized]
    if normalized.endswith("-city"):
        normalized = normalized[: -len("-city")]
        if normalized in PAGE_REGION_MAP:
            return PAGE_REGION_MAP[normalized]
    words = [word for word in normalized.replace("-", " ").split() if word]
    return _normalize_display_name(" ".join(word.capitalize() for word in words))


def _transliterate_latin_token(token: str) -> str:
    rest = token.lower()
    parts = []
    while rest:
        matched = False
        for source, target in TRANSLIT_MULTI_CHAR:
            if rest.startswith(source):
                parts.append(target)
                rest = rest[len(source) :]
                matched = True
                break
        if matched:
            continue
        parts.append(TRANSLIT_SINGLE_CHAR.get(rest[0], rest[0]))
        rest = rest[1:]
    result = "".join(parts)
    if not result:
        return token
    return result[0].upper() + result[1:]


def _looks_latin_text(text: str) -> bool:
    stripped = str(text or "").strip()
    return bool(stripped) and bool(re.fullmatch(r"[A-Za-z][A-Za-z\s-]*", stripped))


def _normalize_display_name(text: str) -> str:
    stripped = str(text or "").strip()
    if not stripped:
        return stripped
    if not _looks_latin_text(stripped):
        return stripped
    return " ".join(_transliterate_latin_token(part) for part in stripped.split())


def _is_russian_page_url(page_url: str) -> bool:
    parsed = urlparse(page_url)
    if "putevka.com" not in parsed.netloc:
        return False
    path_parts = _split_page_parts(page_url)
    return bool(path_parts)


def _find_product_nodes(json_data):
    stack = [json_data]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if _schema_has_type(current, "Product") and current.get("offers"):
                yield current
            for value in current.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(current, list):
            for item in current:
                if isinstance(item, (dict, list)):
                    stack.append(item)


def _infer_region_from_page(page_url: str) -> str:
    path_parts = _split_page_parts(page_url)
    for part in path_parts:
        if part in PAGE_REGION_MAP:
            return PAGE_REGION_MAP[part]
    if path_parts:
        return _humanize_slug(path_parts[0]) or _humanize_slug(path_parts[-1])
    return "Мир"


def _infer_city_from_page(page_url: str) -> str:
    path_parts = _split_page_parts(page_url)
    if not path_parts:
        return "Мир"

    if len(path_parts) >= 3:
        candidate = path_parts[-2]
    elif len(path_parts) == 2 and path_parts[-1] in LISTING_PAGE_SUFFIXES:
        candidate = path_parts[0]
    elif len(path_parts) >= 2:
        candidate = path_parts[-1]
    else:
        candidate = path_parts[0]

    return _humanize_slug(candidate) or _infer_region_from_page(page_url)


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
    return urlunsplit((split.scheme, split.netloc, split.path, split.query, ""))


def _is_russia_country(country_value: str) -> bool:
    country_text = str(country_value or "").strip().lower()
    if not country_text:
        return False
    return "рос" in country_text or "russia" in country_text


def _normalize_country_name(country_value: str, fallback: str = "Мир") -> str:
    normalized = _normalize_display_name(str(country_value or "").strip())
    return normalized or fallback


def _extract_country_from_address(address: dict) -> str:
    if not isinstance(address, dict):
        return ""
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


def _extract_image_candidate(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        for item in value:
            candidate = _extract_image_candidate(item)
            if candidate:
                return candidate
        return ""
    if isinstance(value, dict):
        for key in ("url", "contentUrl", "thumbnailUrl", "image", "imageUrl", "photo"):
            candidate = _extract_image_candidate(value.get(key))
            if candidate:
                return candidate
    return ""


def _normalize_image_url(raw_url: str, page_url: str) -> str:
    normalized = str(raw_url or "").strip()
    if not normalized:
        return ""
    absolute = urljoin(page_url, normalized)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    split = urlsplit(absolute)
    return urlunsplit((split.scheme, split.netloc, split.path, split.query, ""))


def _normalize_locality(locality_value, fallback_city: str) -> str:
    text = str(locality_value or "").strip()
    if not text:
        return fallback_city

    normalized = text.lower()
    noisy_tokens = [
        "россия",
        "област",
        "край",
        "район",
        "р-он",
        "улиц",
        "ул.",
        "дом",
        "д.",
        ",",
    ]
    if any(token in normalized for token in noisy_tokens):
        return fallback_city
    return _normalize_display_name(text)


def _parse_jsonld_blocks(html: str) -> list[dict | list]:
    blocks = []
    for script_match in SCRIPT_JSONLD_RE.finditer(html):
        raw_json = script_match.group(1).strip()
        if not raw_json:
            continue
        try:
            blocks.append(json.loads(raw_json))
        except json.JSONDecodeError:
            continue
    return blocks


def _extract_page_context(json_blocks: list[dict | list], page_url: str) -> dict:
    context = {
        "country": "",
        "city": _infer_city_from_page(page_url),
        "region": _infer_region_from_page(page_url),
        "name": "",
        "description": "",
        "image": "",
    }

    for json_block in json_blocks:
        stack = [json_block]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                if _schema_has_type(current, "Hotel") or _schema_has_type(current, "Place"):
                    address = current.get("address", {}) or {}
                    context["country"] = _extract_country_from_address(address) or context["country"]
                    context["region"] = str(address.get("addressRegion", "")).strip() or context["region"]
                    context["city"] = _normalize_locality(
                        address.get("addressLocality"),
                        fallback_city=context["city"],
                    )
                    context["name"] = str(current.get("name", "")).strip() or context["name"]
                    context["description"] = (
                        str(current.get("description", "")).strip() or context["description"]
                    )
                    context["image"] = _normalize_image_url(
                        _extract_image_candidate(current.get("image") or current.get("photo")),
                        page_url=page_url,
                    ) or context["image"]
                    return context
                for value in current.values():
                    if isinstance(value, (dict, list)):
                        stack.append(value)
            elif isinstance(current, list):
                for item in current:
                    if isinstance(item, (dict, list)):
                        stack.append(item)

    return context


def _build_live_title(offer_data: dict, product_data: dict | None) -> str:
    offer_name = str(offer_data.get("name", "")).strip()
    if not isinstance(product_data, dict):
        return offer_name

    product_name = str(product_data.get("name", "")).strip()
    brand = product_data.get("brand", {}) or {}
    if isinstance(brand, dict):
        brand_name = str(brand.get("name", "")).strip()
    else:
        brand_name = str(brand or "").strip()

    if brand_name and product_name:
        if product_name.lower() in brand_name.lower():
            return brand_name
        return f"{brand_name} - {product_name}"
    return offer_name or product_name or brand_name


def _extract_night_values_from_html(html: str) -> tuple[int | None, int | None]:
    selected_match = re.search(
        r'<input[^>]+id=["\']trigger-nights["\'][^>]+data-value=["\'](\d+)["\']',
        html,
        re.IGNORECASE,
    )
    selected_nights = _safe_int(selected_match.group(1)) if selected_match else None

    option_values = [
        value
        for value in (
            _safe_int(match)
            for match in re.findall(
                r'<input[^>]+name=["\']input-nights["\'][^>]+data-value=["\'](\d+)["\']',
                html,
                re.IGNORECASE,
            )
        )
        if value and value > 0
    ]
    min_nights = min(option_values) if option_values else selected_nights
    return min_nights, selected_nights


def _extract_review_node(value):
    if isinstance(value, list):
        for item in value:
            extracted = _extract_review_node(item)
            if extracted:
                return extracted
        return {}

    if isinstance(value, str):
        text = value.strip()
        return {"text": text} if text else {}

    if not isinstance(value, dict):
        return {}

    text = (
        str(value.get("reviewBody", "")).strip()
        or str(value.get("description", "")).strip()
        or str(value.get("name", "")).strip()
    )
    author_raw = value.get("author", {})
    if isinstance(author_raw, dict):
        author = str(author_raw.get("name", "")).strip()
    else:
        author = str(author_raw or "").strip()

    if text or author:
        return {"text": text, "author": author}

    for nested_key in ("review", "itemReviewed"):
        extracted = _extract_review_node(value.get(nested_key))
        if extracted:
            return extracted
    return {}


def _normalize_review_entry(review_like, fallback_author: str = "") -> dict | None:
    if isinstance(review_like, str):
        text = review_like.strip()
        if not text:
            return None
        return {
            "author": fallback_author,
            "text": text,
            "rating": None,
            "date": "",
            "title": "",
        }

    if not isinstance(review_like, dict):
        return None

    text = (
        str(review_like.get("reviewBody", "")).strip()
        or str(review_like.get("description", "")).strip()
        or str(review_like.get("text", "")).strip()
    )
    title = str(review_like.get("name", "")).strip()
    author_raw = review_like.get("author", {})
    if isinstance(author_raw, dict):
        author = str(author_raw.get("name", "")).strip()
    else:
        author = str(author_raw or fallback_author or "").strip()

    review_rating = review_like.get("reviewRating", {}) or {}
    if isinstance(review_rating, dict):
        rating = _safe_float(review_rating.get("ratingValue"))
    else:
        rating = _safe_float(review_rating)
    date = str(review_like.get("datePublished", "")).strip()

    if not any([text, title, author, rating, date]):
        return None

    return {
        "author": author,
        "text": text or title,
        "rating": rating,
        "date": date,
        "title": title,
    }


def _collect_reviews_from_node(node, collected: list[dict]):
    if isinstance(node, list):
        for item in node:
            _collect_reviews_from_node(item, collected)
        return

    if not isinstance(node, dict):
        return

    current_type = node.get("@type")
    if current_type == "Review" or (isinstance(current_type, list) and "Review" in current_type):
        normalized = _normalize_review_entry(node)
        if normalized:
            collected.append(normalized)

    if "review" in node:
        review_value = node.get("review")
        normalized = _normalize_review_entry(review_value)
        if normalized:
            collected.append(normalized)
        _collect_reviews_from_node(review_value, collected)

    for value in node.values():
        if isinstance(value, (dict, list)):
            _collect_reviews_from_node(value, collected)


def _normalize_live_offer(
    offer_data: dict,
    page_url: str,
    product_data: dict | None = None,
    page_context: dict | None = None,
    min_nights: int | None = None,
    selected_nights: int | None = None,
):
    raw_price = _safe_int(offer_data.get("price"))
    if raw_price is None or raw_price <= 0:
        return None
    if raw_price > MAX_REASONABLE_PRICE_PER_PERSON:
        return None

    title = _build_live_title(offer_data, product_data)
    url = _normalize_offer_link(str(offer_data.get("url", "")).strip() or page_url, page_url=page_url)
    if not title or not url:
        return None
    if len(_split_page_parts(url)) < 2:
        return None

    page_context = page_context or {}
    rating_info = offer_data.get("aggregateRating", {}) or {}
    reviewed = rating_info.get("itemReviewed", {}) or {}
    review_payload = (
        _extract_review_node(offer_data.get("review"))
        or _extract_review_node((product_data or {}).get("review"))
        or _extract_review_node(reviewed.get("review"))
    )
    address = reviewed.get("address", {}) or {}
    country = _extract_country_from_address(address) or str(page_context.get("country", "")).strip()
    if not country and not _is_russian_page_url(page_url):
        return None

    page_city = str(page_context.get("city", "")).strip()
    page_region = str(page_context.get("region", "")).strip()
    fallback_city = page_city
    if not fallback_city or fallback_city == page_region:
        fallback_city = _infer_city_from_page(url) or _infer_city_from_page(page_url)
    city = _normalize_locality(address.get("addressLocality"), fallback_city=fallback_city)
    region = (
        str(address.get("addressRegion", "")).strip()
        or str(page_context.get("region", "")).strip()
        or _infer_region_from_page(page_url)
    )
    categories = _infer_categories(name=title, url=url, page_url=page_url, region=region)
    if not categories:
        return None

    description = (
        str((product_data or {}).get("description", "")).strip()
        or str(page_context.get("description", "")).strip()
        or "Актуальная путевка с подтвержденной ценой."
    )
    identity = (
        str((product_data or {}).get("sku", "")).strip()
        or title
    )
    stable_id = hashlib.md5(f"{url}|{identity}|{raw_price}".encode("utf-8")).hexdigest()[:16]
    search_text = f"{title} {city} {region} {description}".lower()
    image_url = ""
    for candidate in (
        offer_data.get("image"),
        offer_data.get("photo"),
        (product_data or {}).get("image"),
        (product_data or {}).get("photo"),
        reviewed.get("image"),
        reviewed.get("photo"),
        page_context.get("image"),
    ):
        image_url = _normalize_image_url(_extract_image_candidate(candidate), page_url=page_url)
        if image_url:
            break

    return {
        "id": f"putevka_live:{stable_id}",
        "source": "putevka_live",
        "title": title,
        "city": city or region,
        "region": region or city or "Мир",
        "country": _normalize_country_name(country, fallback="Мир"),
        "pricePerPerson": raw_price,
        "days": selected_nights or min_nights or 7,
        "minNights": min_nights or selected_nights or 1,
        "categories": categories,
        "hasHotel": "with_hotel" in categories,
        "hasPool": "with_pool" in categories,
        "description": description,
        "reviewText": review_payload.get("text", "") or description,
        "reviewAuthor": review_payload.get("author", ""),
        "ratingValue": _safe_float(rating_info.get("ratingValue")),
        "reviewCount": _safe_int(rating_info.get("reviewCount") or rating_info.get("ratingCount")),
        "image": image_url,
        "link": url,
        "_search": search_text,
        "_tokens": _tokenize(search_text),
    }


def _extract_live_offers_from_html(html: str, page_url: str) -> list[dict]:
    extracted = []
    json_blocks = _parse_jsonld_blocks(html)
    page_context = _extract_page_context(json_blocks, page_url=page_url)
    min_nights, selected_nights = _extract_night_values_from_html(html)

    for json_data in json_blocks:
        for product in _find_product_nodes(json_data):
            offers_data = product.get("offers")
            if isinstance(offers_data, dict) and isinstance(offers_data.get("offers"), list):
                offers = offers_data.get("offers", [])
            elif isinstance(offers_data, list):
                offers = offers_data
            elif isinstance(offers_data, dict):
                offers = [offers_data]
            else:
                offers = []

            for offer in offers:
                if not isinstance(offer, dict):
                    continue
                normalized = _normalize_live_offer(
                    offer,
                    page_url=page_url,
                    product_data=product,
                    page_context=page_context,
                    min_nights=min_nights,
                    selected_nights=selected_nights,
                )
                if normalized:
                    extracted.append(normalized)
    return extracted


def _extract_reviews_from_html(html: str, page_url: str) -> list[dict]:
    json_blocks = _parse_jsonld_blocks(html)
    collected = []
    for json_block in json_blocks:
        _collect_reviews_from_node(json_block, collected)

    deduped = []
    seen = set()
    for item in collected:
        text = str(item.get("text", "")).strip()
        author = str(item.get("author", "")).strip()
        title = str(item.get("title", "")).strip()
        key = (text.lower(), author.lower(), title.lower())
        if not any(key):
            continue
        if key in seen:
            continue
        seen.add(key)
        deduped.append(
            {
                "author": author,
                "text": text,
                "rating": item.get("rating"),
                "date": str(item.get("date", "")).strip(),
                "title": title,
            }
        )

    if deduped:
        return deduped

    page_context = _extract_page_context(json_blocks, page_url=page_url)
    fallback_text = str(page_context.get("description", "")).strip()
    if fallback_text:
        return [
            {
                "author": "",
                "text": fallback_text,
                "rating": None,
                "date": "",
                "title": str(page_context.get("name", "")).strip(),
            }
        ]

    return []


def _fetch_live_page(page_url: str) -> list[dict]:
    if not _is_russian_page_url(page_url):
        return []

    cache_ttl = max(30, int(getattr(settings, "PUTEVKA_PAGE_CACHE_TTL_SECONDS", 1800) or 1800))
    cache_now = time.time()
    with _live_page_cache_lock:
        cached_entry = _live_page_cache.get(page_url)
    if cached_entry and cached_entry["expiresAt"] > cache_now:
        return list(cached_entry["offers"])

    request = Request(page_url, headers=REQUEST_HEADERS)
    timeout_seconds = max(5, int(getattr(settings, "PUTEVKA_FETCH_TIMEOUT_SECONDS", 12) or 12))
    with urlopen(request, timeout=timeout_seconds) as response:
        html = response.read().decode("utf-8", errors="ignore")
    offers = _extract_live_offers_from_html(html, page_url=page_url)
    with _live_page_cache_lock:
        _live_page_cache[page_url] = {
            "expiresAt": cache_now + cache_ttl,
            "offers": list(offers),
        }
    return offers


def _fetch_reviews_for_url(page_url: str) -> list[dict]:
    normalized_url = str(page_url or "").strip()
    if not normalized_url:
        return []

    cache_ttl = max(60, int(getattr(settings, "PUTEVKA_PAGE_CACHE_TTL_SECONDS", 1800) or 1800))
    cache_now = time.time()
    with _live_page_cache_lock:
        cached_entry = _review_cache.get(normalized_url)
    if cached_entry and cached_entry["expiresAt"] > cache_now:
        return list(cached_entry["reviews"])

    request = Request(normalized_url, headers=REQUEST_HEADERS)
    timeout_seconds = max(5, int(getattr(settings, "PUTEVKA_FETCH_TIMEOUT_SECONDS", 12) or 12))
    with urlopen(request, timeout=timeout_seconds) as response:
        html = response.read().decode("utf-8", errors="ignore")
    reviews = _extract_reviews_from_html(html, normalized_url)
    with _live_page_cache_lock:
        _review_cache[normalized_url] = {
            "expiresAt": cache_now + cache_ttl,
            "reviews": list(reviews),
        }
    return reviews


def _fetch_live_pages(page_urls: list[str], max_workers: int = 10) -> list[dict]:
    if not page_urls:
        return []

    deduped_urls = list(dict.fromkeys(page_urls))
    collected = []
    configured_workers = int(getattr(settings, "PUTEVKA_FETCH_WORKERS", max_workers) or max_workers)
    workers = max(4, min(configured_workers, len(deduped_urls)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_fetch_live_page, page_url): page_url for page_url in deduped_urls}
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception:
                continue
            if result:
                collected.extend(result)
    return collected


def _load_sitemap_region_urls(limit: int) -> list[str]:
    cache_ttl = max(60, int(getattr(settings, "PUTEVKA_SITEMAP_CACHE_TTL_SECONDS", 3600) or 3600))
    cache_now = time.time()
    with _live_page_cache_lock:
        if _sitemap_cache["urls"] and _sitemap_cache["expiresAt"] > cache_now:
            safe_limit = max(1, limit)
            return list(_sitemap_cache["urls"][:safe_limit])

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
        if not _is_russian_page_url(loc):
            continue
        urls.append(loc)

    deduped = list(dict.fromkeys(urls))
    with _live_page_cache_lock:
        _sitemap_cache["urls"] = list(deduped)
        _sitemap_cache["expiresAt"] = cache_now + cache_ttl
    safe_limit = max(1, limit)
    return deduped[:safe_limit]


def _extend_live_index_from_pages(page_urls: list[str], deduped_tours: dict, detail_urls: set[str]):
    for item in _fetch_live_pages(page_urls):
        deduped_tours[item["id"]] = item
        detail_link = str(item.get("link", "")).strip()
        if detail_link and _is_russian_page_url(detail_link):
            detail_urls.add(detail_link)


def _load_live_putevka(progress_callback=None) -> list[dict]:
    if not settings.LIVE_PARSER_ENABLED:
        raise RuntimeError("Live parser disabled by settings")

    seed_urls = [
        url
        for url in list(getattr(settings, "PUTEVKA_REGION_URLS", []) or [])
        if _is_russian_page_url(url)
    ]
    if not seed_urls:
        raise RuntimeError("No live parser URLs configured")

    deduped_urls = list(dict.fromkeys(seed_urls))
    deduped_tours = {}
    detail_urls = set()
    _extend_live_index_from_pages(deduped_urls, deduped_tours, detail_urls)

    target_min_tours = max(0, int(getattr(settings, "PUTEVKA_MIN_TOURS_TARGET", 3600) or 0))
    if progress_callback:
        progress_callback(
            list(deduped_tours.values()),
            stage="seed",
            target_count=target_min_tours,
        )
    sitemap_enabled = bool(getattr(settings, "PUTEVKA_SITEMAP_ENABLED", True))
    if sitemap_enabled and len(deduped_tours) < target_min_tours:
        sitemap_limit = max(100, int(getattr(settings, "PUTEVKA_SITEMAP_REGIONS_LIMIT", 900) or 900))
        sitemap_urls = _load_sitemap_region_urls(sitemap_limit)
        remaining_urls = [url for url in sitemap_urls if url not in deduped_urls]
        batch_size = max(20, int(getattr(settings, "PUTEVKA_REGION_BATCH_SIZE", 120) or 120))

        for start in range(0, len(remaining_urls), batch_size):
            batch_urls = remaining_urls[start : start + batch_size]
            _extend_live_index_from_pages(batch_urls, deduped_tours, detail_urls)
            if progress_callback:
                progress_callback(
                    list(deduped_tours.values()),
                    stage="regions",
                    target_count=target_min_tours,
                )
            if len(deduped_tours) >= target_min_tours:
                break

    if len(deduped_tours) < target_min_tours and detail_urls:
        detail_page_limit = max(50, int(getattr(settings, "PUTEVKA_DETAIL_PAGES_LIMIT", 900) or 900))
        detail_batch_size = max(10, int(getattr(settings, "PUTEVKA_DETAIL_BATCH_SIZE", 60) or 60))
        detail_candidates = list(dict.fromkeys(detail_urls))[:detail_page_limit]

        for start in range(0, len(detail_candidates), detail_batch_size):
            batch_urls = detail_candidates[start : start + detail_batch_size]
            _extend_live_index_from_pages(batch_urls, deduped_tours, set())
            if progress_callback:
                progress_callback(
                    list(deduped_tours.values()),
                    stage="details",
                    target_count=target_min_tours,
                )
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
    if price_per_person > MAX_REASONABLE_PRICE_PER_PERSON:
        return None

    categories = [
        category_id
        for category_id in record.get("categories", [])
        if category_id in VALID_CATEGORY_IDS
    ]
    if not categories:
        return None

    title = str(record.get("title", "Путевка по России"))
    region = str(record.get("region", "Мир"))
    city = str(record.get("city", "")).strip() or region
    country = _normalize_country_name(record.get("country", ""), fallback="Мир")
    description = str(record.get("description", ""))
    image = str(record.get("image", "")).strip()
    review_text = str(record.get("reviewText") or description or "").strip()
    review_author = str(record.get("reviewAuthor", "")).strip()
    rating_value = _safe_float(record.get("ratingValue"))
    review_count = _safe_int(record.get("reviewCount"))
    search_text = " ".join([title, city, region, description]).lower()
    min_nights = _safe_int(record.get("minNights")) or _safe_int(record.get("days")) or 1
    days = _safe_int(record.get("days")) or min_nights

    return {
        "id": f"{source_name}:{record.get('id', 'unknown')}",
        "source": source_name,
        "title": title,
        "city": city,
        "region": region,
        "country": country,
        "pricePerPerson": price_per_person,
        "days": days,
        "minNights": min_nights,
        "categories": categories,
        "hasHotel": "with_hotel" in categories,
        "hasPool": "with_pool" in categories,
        "description": description,
        "reviewText": review_text,
        "reviewAuthor": review_author,
        "ratingValue": rating_value,
        "reviewCount": review_count,
        "image": image,
        "link": str(record.get("link", "#")),
        "_search": search_text,
        "_tokens": _tokenize(search_text),
    }


def _load_local() -> list[dict]:
    raw = DATA_FILE.read_text(encoding="utf-8")
    records = json.loads(raw)
    tours = [_normalize_record(record, "local_json") for record in records]
    return sorted([tour for tour in tours if tour], key=lambda item: item["pricePerPerson"])


def _serialize_tours_for_snapshot(tours: list[dict]) -> list[dict]:
    return [
        {
            "id": str(tour.get("id", "")),
            "title": str(tour.get("title", "")),
            "city": str(tour.get("city", "")),
            "region": str(tour.get("region", "")),
            "country": str(tour.get("country", "Мир")),
            "pricePerPerson": tour.get("pricePerPerson"),
            "days": tour.get("days"),
            "minNights": tour.get("minNights"),
            "categories": list(tour.get("categories", [])),
            "description": str(tour.get("description", "")),
            "reviewText": str(tour.get("reviewText", "")),
            "reviewAuthor": str(tour.get("reviewAuthor", "")),
            "ratingValue": tour.get("ratingValue"),
            "reviewCount": tour.get("reviewCount"),
            "image": str(tour.get("image", "")),
            "link": str(tour.get("link", "#")),
        }
        for tour in tours
    ]


def _persist_snapshot(tours: list[dict]):
    try:
        SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_FILE.write_text(
            json.dumps(_serialize_tours_for_snapshot(tours), ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        return


def _persist_partial_snapshot(tours: list[dict]):
    try:
        PARTIAL_SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
        PARTIAL_SNAPSHOT_FILE.write_text(
            json.dumps(_serialize_tours_for_snapshot(tours), ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        return


def _clear_partial_snapshot():
    try:
        PARTIAL_SNAPSHOT_FILE.unlink(missing_ok=True)
    except Exception:
        return


def _load_snapshot() -> list[dict]:
    if not SNAPSHOT_FILE.exists():
        return []

    try:
        raw = SNAPSHOT_FILE.read_text(encoding="utf-8")
        records = json.loads(raw)
    except Exception:
        return []

    tours = [_normalize_record(record, "snapshot") for record in records]
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


def _reset_query_cache_unlocked():
    global _result_cache
    global _result_cache_hits
    global _result_cache_misses

    _result_cache = {}
    _result_cache_hits = 0
    _result_cache_misses = 0


def _apply_partial_cache_unlocked(tours: list[dict], source_name: str, refresh_note: str):
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

    sorted_tours = sorted(tours, key=lambda item: item["pricePerPerson"])
    by_id = {}
    sorted_ids = []
    price_values = []
    price_index = {}
    category_index = {}
    search_index = {}

    for tour in sorted_tours:
        tour_id = tour["id"]
        by_id[tour_id] = tour
        sorted_ids.append(tour_id)
        price_values.append(tour["pricePerPerson"])
        price_index.setdefault(tour["pricePerPerson"], []).append(tour_id)
        for category in tour["categories"]:
            category_index.setdefault(category, set()).add(tour_id)
        for token in set(tour["_tokens"]):
            search_index.setdefault(token, set()).add(tour_id)

    _cached_tours = sorted_tours
    _cached_by_id = by_id
    _cached_sorted_ids = sorted_ids
    _cached_price_values = price_values
    _cached_price_index = price_index
    _cached_category_index = category_index
    _cached_search_index = search_index
    _cache_updated_at = datetime.now(UTC)
    _cache_source = source_name
    _cache_expires_at = time.time() + max(settings.TOUR_CACHE_TTL_SECONDS, 30)
    _cache_generation += 1
    _last_refresh_note = refresh_note
    _reset_query_cache_unlocked()
    if source_name == "live_putevka" or source_name == "go":
        _persist_snapshot(sorted_tours)
        _clear_partial_snapshot()
    elif source_name.startswith("live_putevka_partial"):
        _persist_partial_snapshot(sorted_tours)


def _refresh_status_unlocked() -> dict:
    return {
        "isRefreshing": _refresh_in_progress,
        "refreshStage": _refresh_stage,
        "refreshTargetCount": _refresh_target_count,
        "refreshCurrentCount": len(_cached_tours),
        "refreshStartedAt": _to_iso_utc(_refresh_started_at),
        "refreshCompletedAt": _to_iso_utc(_refresh_completed_at),
    }


def _background_refresh_worker():
    global _refresh_in_progress
    global _refresh_stage
    global _refresh_target_count
    global _refresh_completed_at
    global _last_refresh_note

    try:
        def progress_callback(tours: list[dict], *, stage: str, target_count: int):
            global _refresh_stage
            global _refresh_target_count
            if not tours:
                return
            with _cache_lock:
                _refresh_stage = stage
                _refresh_target_count = max(target_count, len(tours))
                _apply_partial_cache_unlocked(
                    tours,
                    source_name="live_putevka_partial",
                    refresh_note=f"Идёт live-поиск: найдено {len(tours)} вариантов ({stage}).",
                )

        tours = _load_live_putevka(progress_callback=progress_callback)
        with _cache_lock:
            _apply_partial_cache_unlocked(
                tours,
                source_name="live_putevka",
                refresh_note=f"Используется live-парсер putevka.com ({len(tours)} предложений).",
            )
            _refresh_in_progress = False
            _refresh_stage = "idle"
            _refresh_target_count = len(tours)
            _refresh_completed_at = datetime.now(UTC)
    except Exception as error:
        with _cache_lock:
            try:
                _refresh_unlocked(force=True)
                _refresh_stage = "idle"
                _refresh_target_count = len(_cached_tours)
            except Exception:
                _refresh_stage = "error"
                if _cached_tours:
                    _last_refresh_note = f"Ошибка фонового обновления: {error}"
            _refresh_in_progress = False
            _refresh_completed_at = datetime.now(UTC)


def start_background_refresh(force: bool = False) -> bool:
    global _refresh_in_progress
    global _refresh_stage
    global _refresh_target_count
    global _refresh_started_at
    global _refresh_thread

    with _cache_lock:
        now = time.time()
        if _refresh_in_progress:
            return False
        if not force and _cached_tours and now < _cache_expires_at:
            return False

        _refresh_in_progress = True
        _refresh_stage = "queued"
        _refresh_target_count = max(
            len(_cached_tours),
            int(getattr(settings, "PUTEVKA_MIN_TOURS_TARGET", 3600) or 0),
        )
        _refresh_started_at = datetime.now(UTC)
        _refresh_thread = threading.Thread(
            target=_background_refresh_worker,
            name="putevka-live-refresh",
            daemon=True,
        )
        _refresh_thread.start()
        return True


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
        _last_refresh_note = (
            f"Используется live-парсер putevka.com ({len(tours)} предложений)."
        )
    except Exception as error:
        live_error = error
        try:
            tours = _load_from_go()
            source_name = "go"
            _last_refresh_note = (
                f"Live-парсер недоступен, взяты данные из go parser: {error}"
            )
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
    if source_name in {"live_putevka", "go"}:
        _persist_snapshot(tours)


def ensure_cache():
    global _cache_expires_at
    should_start_refresh = False
    with _cache_lock:
        now = time.time()
        if _cached_tours and now < _cache_expires_at:
            return

        if not _cached_tours:
            snapshot_tours = []
            if settings.LIVE_PARSER_ENABLED:
                try:
                    snapshot_tours = _load_snapshot()
                except Exception:
                    snapshot_tours = []
            if snapshot_tours:
                _apply_partial_cache_unlocked(
                    snapshot_tours,
                    source_name="snapshot_bootstrap",
                    refresh_note="Показан сохранённый live-снимок, каталог дополняется новым live-парсером.",
                )
                _cache_expires_at = now + 15

        if not _cached_tours:
            try:
                bootstrap_tours = _load_local()
            except Exception:
                bootstrap_tours = []
            if bootstrap_tours:
                _apply_partial_cache_unlocked(
                    bootstrap_tours,
                    source_name="local_bootstrap",
                    refresh_note="Показан быстрый локальный снимок, каталог дополняется live-парсером.",
                )
                _cache_expires_at = now + 5

        should_start_refresh = not _refresh_in_progress

    if should_start_refresh:
        start_background_refresh(force=True)


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
            if str(_cached_by_id[tour_id].get("city", "")).strip().lower() == city
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


def _get_cache_key(normalized_query: dict) -> tuple:
    return (
        _cache_generation,
        normalized_query["price_per_person"],
        normalized_query["min_price"],
        normalized_query["max_price"],
        normalized_query["categories"],
        normalized_query["city"],
        normalized_query["query"],
        normalized_query["sort"],
    )


def _get_matched_ids_unlocked(normalized_query: dict) -> list[str]:
    global _result_cache_hits
    global _result_cache_misses

    cache_key = _get_cache_key(normalized_query)
    matched_ids = _result_cache.get(cache_key)
    if matched_ids is None:
        _result_cache_misses += 1
        matched_ids = _build_candidate_ids_unlocked(normalized_query)
        _result_cache[cache_key] = matched_ids
    else:
        _result_cache_hits += 1
    return matched_ids


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

    with _cache_lock:
        matched_ids = _get_matched_ids_unlocked(normalized_query)
        total_count = len(matched_ids)
        page_ids = matched_ids[
            normalized_query["offset"] : normalized_query["offset"] + normalized_query["limit"]
        ]
        tours = [
            {k: v for k, v in _cached_by_id[tour_id].items() if not k.startswith("_")}
            for tour_id in page_ids
        ]
        meta = {
            "lastParsedAt": _to_iso_utc(_cache_updated_at),
            "cacheSource": _cache_source,
            "queryCacheHits": _result_cache_hits,
            "queryCacheMisses": _result_cache_misses,
            "refreshNote": _last_refresh_note,
        }
        meta.update(_refresh_status_unlocked())
    return tours, meta, total_count


def get_city_suggestions(
    query=None,
    limit=12,
    *,
    price_per_person=None,
    min_price=None,
    max_price=None,
    categories=None,
    tour_query=None,
):
    ensure_cache()
    normalized_prefix = str(query or "").strip().lower()
    safe_limit = _safe_int(limit) or 12
    safe_limit = max(1, min(safe_limit, 50))
    base_query = _normalize_query(
        price_per_person=price_per_person,
        min_price=min_price,
        max_price=max_price,
        categories=categories,
        city="",
        query=tour_query,
        sort="price_asc",
        limit=safe_limit,
        offset=0,
    )

    with _cache_lock:
        candidate_ids = _get_matched_ids_unlocked(base_query)
        counter = Counter()
        for tour_id in candidate_ids:
            city = str(_cached_by_id[tour_id].get("city", "")).strip()
            if not city:
                continue
            city_lower = city.lower()
            if normalized_prefix and not city_lower.startswith(normalized_prefix):
                continue
            counter[city] += 1

        return [
            {"city": city, "count": count}
            for city, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:safe_limit]
        ]


def get_query_suggestions(
    query=None,
    limit=8,
    *,
    price_per_person=None,
    min_price=None,
    max_price=None,
    categories=None,
    city=None,
):
    ensure_cache()
    normalized_prefix = str(query or "").strip().lower()
    safe_limit = _safe_int(limit) or 8
    safe_limit = max(1, min(safe_limit, 20))
    base_query = _normalize_query(
        price_per_person=price_per_person,
        min_price=min_price,
        max_price=max_price,
        categories=categories,
        city=city,
        query="",
        sort="price_asc",
        limit=safe_limit,
        offset=0,
    )

    with _cache_lock:
        candidate_ids = _get_matched_ids_unlocked(base_query)
        counter = Counter()
        for tour_id in candidate_ids:
            title = str(_cached_by_id[tour_id].get("title", "")).strip()
            if not title:
                continue
            title_lower = title.lower()
            if normalized_prefix:
                title_tokens = _tokenize(title_lower)
                if normalized_prefix not in title_lower and not any(
                    token.startswith(normalized_prefix) for token in title_tokens
                ):
                    continue
            counter[title] += 1

        return [
            {"query": title, "count": count}
            for title, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:safe_limit]
        ]


def get_cache_meta():
    ensure_cache()
    with _cache_lock:
        meta = {
            "count": len(_cached_tours),
            "lastParsedAt": _to_iso_utc(_cache_updated_at),
            "cacheSource": _cache_source,
            "queryCacheHits": _result_cache_hits,
            "queryCacheMisses": _result_cache_misses,
            "queryCacheSize": len(_result_cache),
            "cacheGeneration": _cache_generation,
            "refreshNote": _last_refresh_note,
        }
        meta.update(_refresh_status_unlocked())
        return meta


def _build_display_price_stats(prices: list[int]) -> tuple[int | None, int | None, int | None]:
    if not prices:
        return None, None, None

    sorted_prices = sorted(int(price) for price in prices if price is not None)
    if not sorted_prices:
        return None, None, None

    sane_cap = int(getattr(settings, "PUTEVKA_DISPLAY_PRICE_CAP", 100000) or 100000)
    visible_prices = [price for price in sorted_prices if price <= sane_cap]
    if visible_prices:
        sorted_prices = visible_prices

    if len(sorted_prices) <= 10:
        average_price = int(round(sum(sorted_prices) / len(sorted_prices)))
        return sorted_prices[0], sorted_prices[-1], average_price

    trimmed_size = max(5, int(round(len(sorted_prices) * 0.92)))
    trimmed_prices = sorted_prices[:trimmed_size]
    average_price = int(round(sum(trimmed_prices) / len(trimmed_prices)))
    return sorted_prices[0], trimmed_prices[-1], average_price


def get_stats():
    ensure_cache()
    with _cache_lock:
        prices = [tour["pricePerPerson"] for tour in _cached_tours]
        total = len(_cached_tours)
        if total == 0:
            payload = {
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
            payload.update(_refresh_status_unlocked())
            return payload

        region_counter = Counter(tour["region"] for tour in _cached_tours)
        category_counter = Counter()
        for tour in _cached_tours:
            category_counter.update(tour["categories"])
        display_price_min, display_price_max, display_price_avg = _build_display_price_stats(prices)

        payload = {
            "totalTours": total,
            "priceMin": display_price_min,
            "priceMax": display_price_max,
            "priceAvg": display_price_avg,
            "priceMaxRaw": max(prices),
            "priceAvgRaw": int(round(sum(prices) / total)),
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
        payload.update(_refresh_status_unlocked())
        return payload


def get_tour_reviews(*, tour_id: str | None = None, link: str | None = None) -> dict:
    ensure_cache()

    selected_tour = None
    normalized_link = str(link or "").strip()
    normalized_id = str(tour_id or "").strip()

    with _cache_lock:
        if normalized_id:
            selected_tour = _cached_by_id.get(normalized_id)
        if selected_tour is None and normalized_link:
            for item in _cached_tours:
                if str(item.get("link", "")).strip() == normalized_link:
                    selected_tour = item
                    break

    if selected_tour is None:
        return {
            "title": "",
            "link": normalized_link,
            "reviews": [],
            "ratingValue": None,
            "reviewCount": 0,
        }

    resolved_link = str(selected_tour.get("link", "")).strip() or normalized_link
    reviews = []
    if _is_russian_page_url(resolved_link):
        try:
            reviews = _fetch_reviews_for_url(resolved_link)
        except Exception:
            reviews = []

    if not reviews:
        fallback_text = str(selected_tour.get("reviewText", "") or selected_tour.get("description", "")).strip()
        if fallback_text:
            reviews = [
                {
                    "author": str(selected_tour.get("reviewAuthor", "")).strip(),
                    "text": fallback_text,
                    "rating": selected_tour.get("ratingValue"),
                    "date": "",
                    "title": "",
                }
            ]

    return {
        "title": str(selected_tour.get("title", "")).strip(),
        "link": resolved_link,
        "reviews": reviews,
        "ratingValue": selected_tour.get("ratingValue"),
        "reviewCount": selected_tour.get("reviewCount") or len(reviews),
    }
