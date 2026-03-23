# Путевки по России: React + Django + Go

Проект после апгрейда:

- React frontend с быстрым UX (поиск, сортировка, пагинация, URL-синхронизация фильтров).
- Django backend API с ускоренной фильтрацией.
- Go parser (опциональный ускоритель), Django автоматически использует fallback на локальные данные.
- Live-парсер реальных предложений с `putevka.com` (JSON-LD офферы по регионам).
- 3000+ строк CSS в `frontend/mega.css` и отдельная тема в `frontend/theme.css`.

## Что улучшено

- Кэш запросов на backend (query-result cache) с метриками hit/miss.
- Индекс по категориям, цене и поисковым токенам для ускорения фильтрации.
- Быстрый диапазон цен через бинарный поиск.
- Новый endpoint статистики `/api/stats`.
- UI с быстрыми пресетами категорий, skeleton-loader и обработкой ошибок.
- Фильтры теперь сохраняются в URL, можно делиться ссылкой на текущую выдачу.

## Запуск

```bash
.venv\Scripts\python django_backend\manage.py runserver 8000
```

Сайт: `http://localhost:8000`

### Запуск через npm (Windows)

Если в PowerShell блокируется `npm.ps1`, используй `npm.cmd`:

```bash
npm.cmd install
npm.cmd run dev
```

## Go parser (опционально)

```bash
cd go_parser
go run .
```

По умолчанию Go parser слушает `http://127.0.0.1:8090`.

## Live parser настройки

- `LIVE_PARSER_ENABLED=1` — включить live-парсер (по умолчанию включен).
- `PUTEVKA_REGION_URLS=url1,url2,...` — список региональных страниц для парсинга.

Если live-источник недоступен, backend автоматически переключается на `go parser`, а затем на локальный fallback.

## API

- `GET /api/health`
- `GET /api/stats`
- `GET /api/categories`
- `GET /api/price-options`
- `GET /api/tours?pricePerPerson=7000&category=mountains&q=weekend&sort=price_desc&limit=12&offset=0`
- `POST /api/parse`

Поддерживаемые `sort`:

- `price_asc` (по умолчанию)
- `price_desc`
- `days_asc`
- `days_desc`

## Тесты

```bash
.venv\Scripts\python django_backend\manage.py test tours
```
