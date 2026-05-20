from django.urls import include, path
from rest_framework.routers import DefaultRouter
from apps.finance.views.contribution import (
    ContributionListCreateAPIView,
)
from apps.finance.views.loan import (
    ApproveLoanAPIView,
    LoanRequestCategoriesViewSet,
    LoanRequestAPIView,
    RejectLoanAPIView,
)

router = DefaultRouter()
router.register(
    r"loan-categories",
    LoanRequestCategoriesViewSet,
    basename="loan-categories",
)

urlpatterns = [
    path("", include(router.urls)),
    path(
        "contributions/",
        ContributionListCreateAPIView.as_view(),
        name="contribution-list-create",
    ),
    path(
        "loans/request/",
        LoanRequestAPIView.as_view(),
        name="request-loan",
    ),
    path(
        "loans/request/<uuid:loan_uuid>/approve/",
        ApproveLoanAPIView.as_view(),
        name="approve-loan",
    ),
    path(
        "loans/request/<uuid:loan_uuid>/reject/",
        RejectLoanAPIView.as_view(),
        name="reject-loan",
    ),
]
