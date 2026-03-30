# Путевки по России

Проект переведён на новый Go backend как основной путь запуска.

## Основной запуск

```powershell
npm run dev
```

Это поднимает Go сервер из [go_backend/main.go](/D:/svagg/putevka/go_backend/main.go) на `http://localhost:8080`.

## Что уже работает на Go

- отдача текущего фронтенда и статики
- каталог туров
- фильтры, города, подсказки, статистика
- отзывы через отдельный endpoint
- регистрация, вход и выход по логину/паролю

## Резервный Django путь

Если нужно временно вернуться на старый backend:

```powershell
npm run django:dev
```

## Структура

- [frontend/app.js](/D:/svagg/putevka/frontend/app.js) — текущий клиент
- [frontend/theme.css](/D:/svagg/putevka/frontend/theme.css) — стили
- [go_backend/main.go](/D:/svagg/putevka/go_backend/main.go) — новый backend
- [django_backend/tours/services.py](/D:/svagg/putevka/django_backend/tours/services.py) — старый Django backend

## Важно

Go backend уже запускается и отвечает, но пока ещё не повторяет весь сложный live-парсер Django один в один. Это следующий этап миграции.
