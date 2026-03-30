# Go backend

Новый backend-слой для миграции проекта с Django на Go.

Что уже есть:
- отдача текущего `frontend/index.html` и `/static/*`
- API каталога: `/api/health`, `/api/categories`, `/api/price-options`, `/api/stats`, `/api/cities`, `/api/search-suggestions`, `/api/tours`, `/api/reviews`, `/api/parse`
- регистрация и вход по логину/паролю через `/api/auth/*`
- хранение пользователей в `data/users.json`
- загрузка каталога из `data/live_cache_snapshot.json` с fallback на `data/offers.json`

Запуск:

```powershell
cd go_backend
go run .
```

Порт по умолчанию: `8080`

Переменные:
- `GO_BACKEND_PORT`
- `GO_BACKEND_SESSION_SECRET`

Важно:
- сейчас это переходный слой, он не повторяет весь live-парсер Django 1 в 1
- если в системе нет `go`, сначала нужно установить Go и добавить его в `PATH`
