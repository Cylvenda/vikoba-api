from django.urls import path
from apps.payments.views.payment import InitiateMobileCollectionAPIView
from apps.payments.views.webhook import ClickPesaWebhookAPIView

urlpatterns = [
    path(
        "initiate/",
        InitiateMobileCollectionAPIView.as_view(),
        name="initiate-payment",
    ),
    path(
        "webhook/clickpesa/",
        ClickPesaWebhookAPIView.as_view(),
        name="clickpesa-webhook",
    ),
]
