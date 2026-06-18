from django.urls import include, path
from rest_framework.routers import DefaultRouter
from apps.finance.views.contribution import (
    ContributionListCreateAPIView,
)
from apps.finance.views.fine import (
    FineListAPIView,
    FinePaymentListCreateAPIView,
)
from apps.finance.views.loan import (
    ApproveLoanAPIView,
    DisburseLoanAPIView,
    LoanProductViewSet,
    LoanRequestAPIView,
    RejectLoanAPIView,
)
from apps.finance.views.repayment import (
    LoanInstallmentListAPIView,
    LoanPaymentListAPIView,
    LoanRepaymentAPIView,
)
from apps.finance.views.snapshot import FinanceSnapshotAPIView

router = DefaultRouter()
router.register(
    r"loan-categories",
    LoanProductViewSet,
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
        "fines/",
        FineListAPIView.as_view(),
        name="fine-list",
    ),
    path(
        "fines/payments/",
        FinePaymentListCreateAPIView.as_view(),
        name="fine-payment-list-create",
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
        "loans/request/<uuid:loan_uuid>/disburse/",
        DisburseLoanAPIView.as_view(),
        name="disburse-loan",
    ),
    path(
        "loans/request/<uuid:loan_uuid>/reject/",
        RejectLoanAPIView.as_view(),
        name="reject-loan",
    ),
    path(
        "loans/<uuid:loan_uuid>/repay/",
        LoanRepaymentAPIView.as_view(),
        name="repay-loan",
    ),
    path(
        "loans/<uuid:loan_uuid>/installments/",
        LoanInstallmentListAPIView.as_view(),
        name="loan-installments",
    ),
    path(
        "loans/<uuid:loan_uuid>/payments/",
        LoanPaymentListAPIView.as_view(),
        name="loan-payments",
    ),
    path(
        "groups/<uuid:group_uuid>/snapshot/",
        FinanceSnapshotAPIView.as_view(),
        name="finance-snapshot",
    ),
]
