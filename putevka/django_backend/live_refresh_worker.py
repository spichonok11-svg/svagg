import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
STATUS_FILE = PROJECT_ROOT / "data" / "live_refresh_status.json"


def write_status(payload: dict) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_refresh_note(meta: dict) -> str:
    if meta.get("isRefreshing"):
        stage = str(meta.get("refreshStage") or "queued")
        current = int(meta.get("refreshCurrentCount") or 0)
        return f"Идёт live-поиск: найдено {current} вариантов ({stage})."
    source = str(meta.get("cacheSource") or "")
    current = int(meta.get("refreshCurrentCount") or meta.get("count") or 0)
    if source.startswith("live_putevka"):
        return f"Используется live-парсер putevka.com ({current} предложений)."
    return str(meta.get("refreshNote") or "")


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    import django

    django.setup()

    from tours.services import force_refresh, get_cache_meta, start_background_refresh

    started_at = time.time()
    try:
        write_status(
            {
                "ok": True,
                "isRefreshing": True,
                "refreshStage": "queued",
                "refreshTargetCount": 0,
                "refreshCurrentCount": 0,
                "cacheSource": "live_putevka",
                "refreshNote": "Live-парсер запускается.",
                "startedAt": started_at,
                "updatedAt": iso_now(),
                "pid": os.getpid(),
            }
        )

        started = start_background_refresh(force=True)
        meta = get_cache_meta()
        if not started and not meta.get("isRefreshing"):
            force_refresh()
            meta = get_cache_meta()

        while True:
            meta = get_cache_meta()
            payload = {
                "ok": True,
                "isRefreshing": bool(meta.get("isRefreshing")),
                "refreshStage": meta.get("refreshStage") or "idle",
                "refreshTargetCount": int(meta.get("refreshTargetCount") or 0),
                "refreshCurrentCount": int(meta.get("refreshCurrentCount") or 0),
                "lastParsedAt": meta.get("lastParsedAt") or "",
                "cacheSource": meta.get("cacheSource") or "",
                "refreshNote": build_refresh_note(meta),
                "startedAt": started_at,
                "updatedAt": iso_now(),
                "pid": os.getpid(),
            }
            write_status(payload)
            if not payload["isRefreshing"]:
                break
            time.sleep(1.0)
        return 0
    except Exception as error:
        write_status(
            {
                "ok": False,
                "isRefreshing": False,
                "refreshStage": "error",
                "refreshTargetCount": 0,
                "refreshCurrentCount": 0,
                "cacheSource": "",
                "refreshNote": f"Ошибка live-парсера: {error}",
                "startedAt": started_at,
                "updatedAt": iso_now(),
                "pid": os.getpid(),
            }
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
