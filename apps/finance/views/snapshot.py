from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, F
from django.shortcuts import get_object_or_404

from apps.groups.models import Group
from apps.finance.models import Contribution, Loan, Fine, FinePayment, Transaction, LedgerEntry
from apps.finance.services.chart_of_accounts_service import ChartOfAccountsService

class FinanceSnapshotAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, group_uuid):
        group = get_object_or_404(Group, uuid=group_uuid)
        
        # Total Savings
        total_savings = Contribution.objects.filter(
            group=group, status=Contribution.Status.VERIFIED
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # Pending Contributions
        pending_contributions = Contribution.objects.filter(
            group=group, status=Contribution.Status.PENDING
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # Active Loan Book
        active_loans = Loan.objects.filter(
            group=group, status__in=[Loan.Status.ACTIVE, Loan.Status.OVERDUE]
        )
        active_loan_book = active_loans.aggregate(total=Sum('remaining_balance'))['total'] or Decimal('0.00')
        expected_interest = active_loans.aggregate(total=Sum('interest_amount'))['total'] or Decimal('0.00')

        # Unpaid Fines
        total_fines = Fine.objects.filter(group=group).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_fine_payments = FinePayment.objects.filter(fine__group=group).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        unpaid_fines = total_fines - total_fine_payments

        # Available Cash
        wallet_account = ChartOfAccountsService.get_group_wallet_account()
        wallet_debits = LedgerEntry.objects.filter(
            account=wallet_account, transaction__group=group
        ).aggregate(total=Sum('debit'))['total'] or Decimal('0.00')
        wallet_credits = LedgerEntry.objects.filter(
            account=wallet_account, transaction__group=group
        ).aggregate(total=Sum('credit'))['total'] or Decimal('0.00')
        available_cash = wallet_debits - wallet_credits

        # Recent Activity
        recent_txs = Transaction.objects.filter(group=group).select_related('created_by').order_by('-created_at')[:5]
        recent_activity = [
            {
                "id": str(tx.uuid),
                "title": tx.description,
                "type": tx.transaction_type,
                "amount": float(tx.amount),
                "status": "completed",
                "actor": tx.created_by.full_name if tx.created_by else "System",
                "happenedAt": tx.created_at.isoformat()
            }
            for tx in recent_txs
        ]

        # Calculate monthly collections as a 30-day lookback of VERIFIED contributions
        from django.utils import timezone
        import datetime
        thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
        monthly_collections = Contribution.objects.filter(
            group=group, status=Contribution.Status.VERIFIED, paid_at__gte=thirty_days_ago
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        return Response({
            "totalSavings": float(total_savings),
            "pendingContributions": float(pending_contributions),
            "activeLoanBook": float(active_loan_book),
            "expectedInterestReturn": float(expected_interest),
            "unpaidFines": float(unpaid_fines),
            "availableCash": float(available_cash),
            "monthlyCollections": float(monthly_collections),
            "recentActivity": recent_activity
        })
