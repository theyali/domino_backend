from django.urls import path

from .views import (
    DirectMessageThreadView,
    FriendRequestAcceptView,
    FriendRequestCreateView,
    FriendshipRemoveView,
    LoginView,
    LogoutView,
    MeView,
    RegisterView,
    RoomInvitationAcceptView,
    RoomInvitationCreateView,
    RoomInvitationDeclineView,
    SocialHeartbeatView,
    SocialOnlineUsersView,
    SocialOverviewView,
    StatisticsView,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("stats/", StatisticsView.as_view(), name="statistics"),
    path("social/heartbeat/", SocialHeartbeatView.as_view(), name="social-heartbeat"),
    path("social/overview/", SocialOverviewView.as_view(), name="social-overview"),
    path("social/online/", SocialOnlineUsersView.as_view(), name="social-online"),
    path("social/friends/request/", FriendRequestCreateView.as_view(), name="friend-request"),
    path("social/friends/<int:pk>/accept/", FriendRequestAcceptView.as_view(), name="friend-accept"),
    path("social/friends/<int:pk>/remove/", FriendshipRemoveView.as_view(), name="friend-remove"),
    path("social/chats/<int:user_id>/", DirectMessageThreadView.as_view(), name="direct-message-thread"),
    path("social/rooms/<int:room_id>/invitations/", RoomInvitationCreateView.as_view(), name="room-invitations"),
    path("social/invitations/<int:pk>/accept/", RoomInvitationAcceptView.as_view(), name="room-invitation-accept"),
    path("social/invitations/<int:pk>/decline/", RoomInvitationDeclineView.as_view(), name="room-invitation-decline"),
]
