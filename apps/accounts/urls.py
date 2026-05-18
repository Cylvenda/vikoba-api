from django.urls import path
from .views import (
    AdminGroupDetailView,
    AdminGroupListView,
    AdminUserDetailView,
    AdminUserListView,
    CustomeTokenObtainPairView,
    CustomeTokenVerifyView,
    CustomeTokenRefreshView,
    CurrentUserView,
    LogoutView,
)

urlpatterns = [
    path("me/auth/login/", CustomeTokenObtainPairView.as_view(), name="login"),
    path("me/auth/refresh/", CustomeTokenRefreshView.as_view(), name="token_refresh"),
    path("me/auth/verify/", CustomeTokenVerifyView.as_view(), name="token_verify"),
    path("me/auth/logout/", LogoutView.as_view(), name="logout"),
    path("me/auth/csrf/", CustomeTokenRefreshView.as_view(), name="csrf"),
    path("me/auth/me/", CurrentUserView.as_view(), name="current_user"),
    path("admin/users/", AdminUserListView.as_view(), name="admin-user-list"),
    path("admin/users/<int:pk>/", AdminUserDetailView.as_view(), name="admin-user-detail"),
    path("admin/groups/", AdminGroupListView.as_view(), name="admin-group-list"),
    path("admin/groups/<int:pk>/", AdminGroupDetailView.as_view(), name="admin-group-detail"),
]
