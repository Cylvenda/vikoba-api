# realtime/urls.py
from django.urls import path
from .views import LiveKitTokenView
from .webhooks import livekit_webhook

urlpatterns = [
    path("livekit/", livekit_webhook, name="realtime-livekit-webhook"),
    path(
        "meetings/<uuid:uuid>/token/",
        LiveKitTokenView.as_view(),
        name="realtime-livekit-token",
    ),
]
