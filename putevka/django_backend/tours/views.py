from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .constants import PRICE_OPTIONS, TOUR_CATEGORIES
from .services import (
    filter_tours,
    force_refresh,
    get_cache_meta,
    get_city_suggestions,
    get_stats,
)


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def index(request):
    return render(request, "index.html")


def health(request):
    if request.method != "GET":
        return JsonResponse({"ok": False, "message": "Method not allowed"}, status=405)
    meta = get_cache_meta()
    return JsonResponse(
        {
            "ok": True,
            "toursInCache": meta["count"],
            "lastParsedAt": meta["lastParsedAt"],
            "cacheSource": meta["cacheSource"],
            "refreshNote": meta["refreshNote"],
            "queryCacheHits": meta["queryCacheHits"],
            "queryCacheMisses": meta["queryCacheMisses"],
            "queryCacheSize": meta["queryCacheSize"],
            "cacheGeneration": meta["cacheGeneration"],
        }
    )


def categories(request):
    if request.method != "GET":
        return JsonResponse({"ok": False, "message": "Method not allowed"}, status=405)
    return JsonResponse({"categories": TOUR_CATEGORIES})


def price_options(request):
    if request.method != "GET":
        return JsonResponse({"ok": False, "message": "Method not allowed"}, status=405)
    return JsonResponse({"options": PRICE_OPTIONS})


def cities(request):
    if request.method != "GET":
        return JsonResponse({"ok": False, "message": "Method not allowed"}, status=405)
    limit = _safe_int(request.GET.get("limit"), 12)
    suggestions = get_city_suggestions(query=request.GET.get("q"), limit=limit)
    return JsonResponse({"cities": suggestions})


def tours(request):
    if request.method != "GET":
        return JsonResponse({"ok": False, "message": "Method not allowed"}, status=405)

    filtered, meta, total_count = filter_tours(
        price_per_person=request.GET.get("pricePerPerson"),
        min_price=request.GET.get("minPrice"),
        max_price=request.GET.get("maxPrice"),
        categories=request.GET.getlist("category"),
        city=request.GET.get("city"),
        query=request.GET.get("q"),
        sort=request.GET.get("sort", "price_asc"),
        limit=request.GET.get("limit", "50"),
        offset=request.GET.get("offset", "0"),
    )
    offset = _safe_int(request.GET.get("offset"), 0)
    limit = _safe_int(request.GET.get("limit"), 50)
    return JsonResponse(
        {
            "count": total_count,
            "returned": len(filtered),
            "tours": filtered,
            "lastParsedAt": meta["lastParsedAt"],
            "cacheSource": meta["cacheSource"],
            "refreshNote": meta["refreshNote"],
            "queryCacheHits": meta["queryCacheHits"],
            "queryCacheMisses": meta["queryCacheMisses"],
            "offset": max(0, offset),
            "limit": max(1, limit),
        }
    )


def stats(request):
    if request.method != "GET":
        return JsonResponse({"ok": False, "message": "Method not allowed"}, status=405)
    return JsonResponse(get_stats())


@csrf_exempt
def parse(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "Method not allowed"}, status=405)

    force_refresh()
    meta = get_cache_meta()
    return JsonResponse(
        {
            "ok": True,
            "parsed": meta["count"],
            "lastParsedAt": meta["lastParsedAt"],
            "cacheSource": meta["cacheSource"],
            "refreshNote": meta["refreshNote"],
        }
    )
