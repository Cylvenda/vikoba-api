from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date

from apps.groups.models import Group
from apps.finance.models import Contribution, Loan, Fine, Transaction
from apps.finance.services.wallet_service import WalletService

class FinanceSnapshotAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, group_uuid):
        group = get_object_or_404(Group, uuid=group_uuid)
        wallet_report = WalletService.build_wallet_report(group)
        
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
        unpaid_fines = Fine.objects.filter(
            group=group, status=Fine.Status.UNPAID
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        available_cash = Decimal(str(wallet_report["groupWallet"]["balance"]))

        # Activity. Dashboards keep the latest 50 records; reporting requests can
        # supply a month or date range and receive the matching transaction set.
        activity_query = Transaction.objects.filter(group=group).select_related('created_by')
        report_month = request.query_params.get("month")
        date_from = parse_date(request.query_params.get("date_from", ""))
        date_to = parse_date(request.query_params.get("date_to", ""))

        if report_month:
            try:
                year, month = (int(part) for part in report_month.split("-", 1))
                activity_query = activity_query.filter(created_at__year=year, created_at__month=month)
            except (TypeError, ValueError):
                pass
        if date_from:
            activity_query = activity_query.filter(created_at__date__gte=date_from)
        if date_to:
            activity_query = activity_query.filter(created_at__date__lte=date_to)

        is_report_request = bool(report_month or date_from or date_to or request.query_params.get("all_activity") == "true")
        ordered_activity = activity_query.order_by("-created_at")
        recent_activity_total = activity_query.count()
        recent_activity_limit = 5000 if is_report_request else 50
        recent_txs = ordered_activity[:recent_activity_limit]
        recent_activity = [
            {
                "id": str(tx.uuid),
                "title": tx.description,
                "type": tx.transaction_type,
                "amount": float(tx.amount),
                "status": "completed",
                "actor": tx.performed_by or (
                    (getattr(tx.created_by, "full_name", "") or tx.created_by.email)
                    if tx.created_by
                    else "System"
                ),
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
            "recentActivity": recent_activity,
            "recentActivityTotal": recent_activity_total,
            "recentActivityLimit": recent_activity_limit,
            "groupWallet": wallet_report["groupWallet"],
            "memberWallets": wallet_report["memberWallets"],
        })
