from rest_framework import serializers


class StartGameSerializer(serializers.Serializer):
    player_id = serializers.IntegerField(min_value=1)


class PlayDominoSerializer(serializers.Serializer):
    player_id = serializers.IntegerField(min_value=1)
    domino_id = serializers.IntegerField(min_value=0)
    side = serializers.ChoiceField(
        choices=("left", "right", "center", "top", "bottom")
    )


class PlayerGameActionSerializer(serializers.Serializer):
    player_id = serializers.IntegerField(min_value=1)
