from django.urls import path
from .views import NotificationListView, MarkNotificationAsReadView

urlpatterns = [
    path("",  NotificationListView.as_view(), name="notification-list"),
    path(
         "<uuid:notification_uuid>/read/",
         MarkNotificationAsReadView.as_view(),
         name="notification-mark-read",
    ),
]
