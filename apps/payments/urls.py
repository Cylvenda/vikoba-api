from django.urls import path
from apps.payments.views.payment import InitiateMobileCollectionAPIView

urlpatterns = [
    path(
        "initiate/",
        InitiateMobileCollectionAPIView.as_view(),
        name="initiate-payment",
    ),
]
