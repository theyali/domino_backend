from django.db import transaction

from .models import UserProfile

WIN_POINTS = 25

LEAGUES = (
    {"number": 5, "roman": "V", "min_points": 0, "max_points": 99},
    {"number": 4, "roman": "IV", "min_points": 100, "max_points": 249},
    {"number": 3, "roman": "III", "min_points": 250, "max_points": 499},
    {"number": 2, "roman": "II", "min_points": 500, "max_points": 899},
    {"number": 1, "roman": "I", "min_points": 900, "max_points": None},
)


def league_for_points(points):
    points = max(0, int(points or 0))
    for league in reversed(LEAGUES):
        if points >= league["min_points"]:
            return league
    return LEAGUES[0]


def _display_name(user):
    return (user.get_full_name() or user.username).strip()


def _serialize_profile(profile, *, rank=None):
    league = league_for_points(profile.league_points)
    next_league = next(
        (
            item
            for item in LEAGUES
            if item["number"] == league["number"] - 1
        ),
        None,
    )
    points_to_next = (
        max(0, next_league["min_points"] - profile.league_points)
        if next_league is not None
        else 0
    )

    return {
        "user_id": profile.user_id,
        "username": profile.user.username,
        "name": _display_name(profile.user),
        "avatar_url": profile.avatar.url if profile.avatar else None,
        "league": league["number"],
        "league_roman": league["roman"],
        "league_points": profile.league_points,
        "points_to_next_league": points_to_next,
        "games_played": profile.games_played,
        "wins": profile.wins,
        "losses": profile.losses,
        "win_rate": round(
            (profile.wins / profile.games_played) * 100,
            1,
        )
        if profile.games_played
        else 0.0,
        "rank": rank,
    }


def build_statistics_payload(user):
    current_profile, _ = UserProfile.objects.get_or_create(user=user)
    profiles = list(
        UserProfile.objects.select_related("user")
        .filter(user__is_active=True)
    )

    grouped = {league["number"]: [] for league in LEAGUES}
    for profile in profiles:
        league_number = league_for_points(profile.league_points)["number"]
        grouped[league_number].append(profile)

    leagues = []
    current_payload = None

    for league in LEAGUES:
        players = sorted(
            grouped[league["number"]],
            key=lambda profile: (
                -profile.league_points,
                -profile.wins,
                profile.user.username.lower(),
            ),
        )
        serialized_players = []
        for index, profile in enumerate(players, start=1):
            payload = _serialize_profile(profile, rank=index)
            serialized_players.append(payload)
            if profile.user_id == current_profile.user_id:
                current_payload = payload

        leagues.append(
            {
                **league,
                "players": serialized_players,
            }
        )

    if current_payload is None:
        current_payload = _serialize_profile(current_profile)

    return {
        "win_points": WIN_POINTS,
        "me": current_payload,
        "leagues": leagues,
    }


@transaction.atomic
def record_match_statistics(
    *,
    session,
    players,
    winner_player_ids,
    loser_player_ids,
):
    if session.stats_recorded:
        return False

    winner_ids = set(winner_player_ids)
    loser_ids = set(loser_player_ids)

    for player in players:
        if player.user_id is None:
            continue

        profile, _ = UserProfile.objects.select_for_update().get_or_create(
            user_id=player.user_id,
        )
        profile.games_played += 1

        if player.pk in winner_ids:
            profile.wins += 1
            profile.league_points += WIN_POINTS
        elif player.pk in loser_ids or player.pk not in winner_ids:
            profile.losses += 1

        profile.save(
            update_fields=[
                "games_played",
                "wins",
                "losses",
                "league_points",
                "updated_at",
            ]
        )

    session.stats_recorded = True
    session.save(update_fields=["stats_recorded", "updated_at"])
    return True
