# Domino backend — local multiplayer foundation

This is the first backend stage for Domino APP.

Included now:

- restaurants API;
- rooms inside restaurants;
- room size 2/3/4;
- optional hashed room password;
- room owner and seats;
- join/leave endpoints;
- SQLite for local development;
- Channels/ASGI prepared, but WebSocket lobby routing is intentionally the next stage.

## macOS setup

```bash
cd domino_backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_restaurants
python manage.py runserver 0.0.0.0:8000
```

Health check:

```text
http://127.0.0.1:8000/api/health/
```

Restaurants:

```text
GET /api/restaurants/
GET /api/restaurants/<id>/
```

Rooms:

```text
GET  /api/restaurants/<restaurant_id>/rooms/
POST /api/restaurants/<restaurant_id>/rooms/
GET  /api/rooms/<room_id>/
POST /api/rooms/<room_id>/join/
POST /api/rooms/<room_id>/leave/
```

Create room example:

```json
{
  "owner_name": "Ali",
  "max_players": 2,
  "password": "1234"
}
```

Join example:

```json
{
  "player_name": "John",
  "password": "1234"
}
```

This local API intentionally has no authentication yet. It is for the Mac/iPhone multiplayer prototype only.
