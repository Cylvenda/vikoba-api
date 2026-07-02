from django.urls import path
from apps.payments.views.payment import (
    InitiateLoanPayoutAPIView,
    InitiateMobileCollectionAPIView,
    LoanPayoutPreviewAPIView,
    TransactionStatusAPIView,
)
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
    path(
        "status/<uuid:transaction_uuid>/",
        TransactionStatusAPIView.as_view(),
        name="transaction-status",
    ),
    path(
        "payouts/loans/<uuid:loan_uuid>/preview/",
        LoanPayoutPreviewAPIView.as_view(),
        name="loan-payout-preview",
    ),
    path(
        "payouts/loans/<uuid:loan_uuid>/initiate/",
        InitiateLoanPayoutAPIView.as_view(),
        name="initiate-loan-payout",
    ),
]
