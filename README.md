# Domino Backend

Backend для Domino APP: Django REST Framework + Django Channels/WebSocket.

## Docker architecture

Проект запускается через Docker Compose и состоит только из нужных сейчас сервисов:

- `web` — Django 5.2 + Daphne (HTTP + WebSocket/ASGI);
- `db` — PostgreSQL 16;
- `pgbouncer` — connection pooler в `transaction` mode;
- `redis` — channel layer для Django Channels.

Celery сейчас не используется, поэтому worker/beat сервисы намеренно не добавлены.

### Где лежат данные PostgreSQL

PostgreSQL использует bind mount:

```text
./data/postgres -> /var/lib/postgresql/data
```

То есть база физически хранится внутри папки проекта `data/postgres` и не зависит от Docker named volume.
Содержимое `data/postgres` добавлено в `.gitignore` и не попадёт в GitHub.

## Первый запуск

```bash
cd domino_backend
cp .env.example .env
```

Перед публичным доступом обязательно поменяй минимум:

```env
DJANGO_SECRET_KEY=...
POSTGRES_PASSWORD=...
```

Запуск:

```bash
docker compose up -d --build
```

Проверить контейнеры:

```bash
docker compose ps
```

Логи Django:

```bash
docker compose logs -f web
```

Миграции автоматически выполняются при старте контейнера `web` через `deploy/entrypoint.sh`.

## Django management commands

Засеять рестораны:

```bash
docker compose exec web python manage.py seed_restaurants
```

Создать администратора:

```bash
docker compose exec web python manage.py createsuperuser
```

Запустить тесты:

```bash
docker compose exec web python manage.py test
```

Открыть Django shell:

```bash
docker compose exec web python manage.py shell
```

## Порты

По умолчанию:

- Django/Daphne: `0.0.0.0:8000`;
- PgBouncer с хоста: `127.0.0.1:6433`;
- Redis с хоста: `127.0.0.1:6380`;
- PostgreSQL напрямую наружу не публикуется.

Внутри Docker-сети Django подключается так:

```text
Django -> pgbouncer:6432 -> db:5432
Django Channels -> redis:6379
```

Для Flutter на устройстве в той же локальной сети используй IP компьютера, например:

```bash
flutter run --dart-define=API_BASE_URL=http://192.168.1.100:8000
```

Для друга через интернет нужен публично доступный адрес/домен и корректно настроенный firewall/reverse proxy.

## Health check

```text
http://127.0.0.1:8000/api/health/
```

## Остановка

```bash
docker compose down
```

`docker compose down` не удаляет PostgreSQL, потому что данные находятся в `./data/postgres`.

Для полного удаления локальной базы нужно отдельно удалить `data/postgres` после остановки контейнеров. Это необратимо.

## Environment variables

Основные переменные находятся в `.env.example`:

- `DJANGO_SECRET_KEY`;
- `DJANGO_DEBUG`;
- `DJANGO_ALLOWED_HOSTS`;
- `POSTGRES_DB`;
- `POSTGRES_USER`;
- `POSTGRES_PASSWORD`;
- `WEB_BIND` / `WEB_PORT`;
- `PGBOUNCER_HOST_PORT`;
- `REDIS_HOST_PORT`.

В Docker Compose `web` автоматически получает:

```text
DB_HOST=pgbouncer
DB_PORT=6432
REDIS_URL=redis://redis:6379/0
```

Django использует PostgreSQL через Psycopg 3. Для PgBouncer `transaction` pooling отключены server-side cursors.

## Важно про старый SQLite

Backend больше не использует `db.sqlite3`. Файл SQLite находится в `.gitignore` и в репозитории его нет, поэтому его локальные данные автоматически перенести из GitHub невозможно. Если старые локальные данные нужны, их нужно отдельно экспортировать из существующей SQLite-базы и импортировать в PostgreSQL.
