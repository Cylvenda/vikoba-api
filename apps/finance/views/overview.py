from decimal import Decimal

from django.db.models import Q, Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.finance.models import (
    Contribution,
    Fine,
    FinePayment,
    GroupWallet,
    Loan,
    LoanRepayment,
    Transaction,
)
from apps.groups.models import GroupMembership


class UserFinanceOverviewAPIView(APIView):
    """Return the signed-in user's home-card data without rebuilding wallets."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = GroupMembership.objects.filter(
            user=request.user,
            is_active=True,
            is_verified=True,
        )
        group_ids = memberships.values("group_id")

        total_savings = (
            Contribution.objects.filter(
                member__user=request.user,
                member__is_active=True,
                member__is_verified=True,
                status=Contribution.Status.VERIFIED,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        active_loans = (
            Loan.objects.filter(
                borrower__user=request.user,
                borrower__is_active=True,
                borrower__is_verified=True,
                status__in=[Loan.Status.ACTIVE, Loan.Status.OVERDUE],
            ).aggregate(total=Sum("remaining_balance"))["total"]
            or Decimal("0.00")
        )

        unpaid_fines = Fine.objects.filter(
            member__user=request.user,
            member__is_active=True,
            member__is_verified=True,
            status=Fine.Status.UNPAID,
        )
        unpaid_fine_amount = (
            unpaid_fines.aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
        fine_payments = (
            FinePayment.objects.filter(fine__in=unpaid_fines).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        consolidated_cash = (
            GroupWallet.objects.filter(group_id__in=group_ids).aggregate(total=Sum("balance"))["total"]
            or Decimal("0.00")
        )

        user_contribution_ids = Contribution.objects.filter(
            member__in=memberships,
            status=Contribution.Status.VERIFIED,
        ).values("uuid")
        user_loan_ids = Loan.objects.filter(
            borrower__in=memberships,
        ).values("uuid")
        user_repayment_ids = LoanRepayment.objects.filter(
            loan__borrower__in=memberships,
        ).values("uuid")
        user_fine_payment_ids = FinePayment.objects.filter(
            fine__member__in=memberships,
        ).values("uuid")

        transaction_query = Transaction.objects.filter(
            group_id__in=group_ids,
        ).filter(
            Q(transaction_type=Transaction.Type.CONTRIBUTION, reference_id__in=user_contribution_ids)
            | Q(transaction_type=Transaction.Type.LOAN_DISBURSEMENT, reference_id__in=user_loan_ids)
            | Q(transaction_type=Transaction.Type.LOAN_REPAYMENT, reference_id__in=user_repayment_ids)
            | Q(transaction_type=Transaction.Type.FINE_PAYMENT, reference_id__in=user_fine_payment_ids)
        )
        recent_activity_total = transaction_query.count()
        recent_activity_limit = 10
        recent_transactions = (
            transaction_query
            .select_related("created_by", "group")
            .order_by("-created_at")[:recent_activity_limit]
        )
        recent_activity = [
            {
                "id": str(transaction.uuid),
                "title": transaction.description,
                "type": transaction.transaction_type,
                "amount": float(transaction.amount),
                "status": "completed",
                "actor": transaction.performed_by
                or (
                    (getattr(transaction.created_by, "full_name", "") or transaction.created_by.email)
                    if transaction.created_by
                    else "System"
                ),
                "happenedAt": transaction.created_at.isoformat(),
                "groupName": transaction.group.name,
            }
            for transaction in recent_transactions
        ]

        return Response(
            {
                "totalSavings": float(total_savings),
                "activeLoans": float(active_loans),
                "unpaidFines": float(max(unpaid_fine_amount - fine_payments, Decimal("0.00"))),
                "consolidatedCash": float(consolidated_cash),
                "recentActivity": recent_activity,
                "recentActivityTotal": recent_activity_total,
                "recentActivityLimit": recent_activity_limit,
            }
        )
