from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from game.models import GameSession
from game.state import serialize_game_state_for_player

from .models import GameRoom, RoomPlayer
from .presence import mark_player_offline, mark_player_online, touch_player
from .realtime import room_group_name
from .serializers import GameRoomSerializer


class RoomLobbyConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.room_id = int(self.scope["url_route"]["kwargs"]["room_id"])
        self.room_group_name = room_group_name(self.room_id)

        player_id = self._player_id_from_query_string()
        if player_id is None:
            await self.close(code=4400)
            return

        player_is_member = await self._player_belongs_to_room(player_id)
        if not player_is_member:
            await self.close(code=4403)
            return

        self.player_id = player_id

        await self._set_online()
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        await self.accept()

        await self._send_room_state()
        await self._send_game_state_if_started()
        await self._broadcast_presence_change()

    async def disconnect(self, close_code):
        group_name = getattr(self, "room_group_name", None)
        player_id = getattr(self, "player_id", None)

        if player_id is not None:
            await self._set_offline()

        if group_name is not None:
            await self.channel_layer.group_discard(
                group_name,
                self.channel_name,
            )

        if group_name is not None and player_id is not None:
            await self.channel_layer.group_send(
                group_name,
                {"type": "room.updated"},
            )

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self._touch_player()
            await self.send_json({"type": "pong"})

    async def room_updated(self, event):
        await self._send_room_state()
        await self._send_game_state(message_type="game_state")

    async def room_deleted(self, event):
        await self.send_json(
            {
                "type": "room_deleted",
                "room_id": self.room_id,
            }
        )
        await self.close(code=4001)

    async def game_started(self, event):
        await self._send_game_state(message_type="game_started")

    async def game_state_updated(self, event):
        await self._send_game_state(message_type="game_state")

    async def _broadcast_presence_change(self):
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "room.updated"},
        )

    async def _send_room_state(self):
        room_data = await self._serialized_room()
        if room_data is None:
            await self.send_json(
                {
                    "type": "room_deleted",
                    "room_id": self.room_id,
                }
            )
            await self.close(code=4001)
            return

        await self.send_json(
            {
                "type": "room_state",
                "room": room_data,
            }
        )

    async def _send_game_state_if_started(self):
        game_data = await self._serialized_game()
        if game_data is None:
            return

        await self.send_json(
            {
                "type": "game_started",
                "game": game_data,
            }
        )

    async def _send_game_state(self, *, message_type):
        game_data = await self._serialized_game()
        if game_data is None:
            return

        await self.send_json(
            {
                "type": message_type,
                "game": game_data,
            }
        )

    def _player_id_from_query_string(self):
        raw_query_string = self.scope.get("query_string", b"").decode("utf-8")
        query = parse_qs(raw_query_string)
        raw_player_id = query.get("player_id", [None])[0]

        try:
            return int(raw_player_id)
        except (TypeError, ValueError):
            return None

    @database_sync_to_async
    def _player_belongs_to_room(self, player_id):
        return RoomPlayer.objects.filter(
            pk=player_id,
            room_id=self.room_id,
            is_active=True,
        ).exists()

    @database_sync_to_async
    def _set_online(self):
        return mark_player_online(
            room_id=self.room_id,
            player_id=self.player_id,
        )

    @database_sync_to_async
    def _touch_player(self):
        return touch_player(
            room_id=self.room_id,
            player_id=self.player_id,
        )

    @database_sync_to_async
    def _set_offline(self):
        return mark_player_offline(
            room_id=self.room_id,
            player_id=self.player_id,
        )

    @database_sync_to_async
    def _serialized_room(self):
        try:
            room = GameRoom.objects.prefetch_related("players").get(pk=self.room_id)
        except GameRoom.DoesNotExist:
            return None

        return GameRoomSerializer(room).data

    @database_sync_to_async
    def _serialized_game(self):
        try:
            session = (
                GameSession.objects.select_related(
                    "room",
                    "current_player",
                    "opening_player",
                )
                .prefetch_related("room__players")
                .get(room_id=self.room_id)
            )
        except GameSession.DoesNotExist:
            return None

        return serialize_game_state_for_player(session, self.player_id)
