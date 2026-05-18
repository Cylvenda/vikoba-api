from django.urls import path
from apps.finance.views.contribution import (
    ContributionCreateAPIView,
)
from apps.finance.views.loan import (
    LoanRequestAPIView,
)

urlpatterns = [
    path(
        "contributions/create/",
        ContributionCreateAPIView.as_view(),
        name="create-contribution",
    ),
    path(
        "loans/request/",
        LoanRequestAPIView.as_view(),
        name="request-loan",
    ),
]
