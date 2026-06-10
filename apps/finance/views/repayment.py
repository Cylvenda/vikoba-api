from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.finance.models import Loan, LoanRepayment
from apps.finance.services.repayment_service import RepaymentService
from apps.finance.serializers.repayment import (
    LoanInstallmentSerializer,
    LoanPaymentSerializer,
)
from apps.finance.permissions import is_group_member

class LoanRepaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, loan_uuid):
        loan = get_object_or_404(Loan, uuid=loan_uuid)
        
        # Validate user is a member of the group
        is_group_member(request.user, loan.group)

        if loan.status not in [Loan.Status.ACTIVE, Loan.Status.OVERDUE]:
            return Response(
                {"detail": "Repayments can only be made on active or overdue loans."},
                status=status.HTTP_400_BAD_REQUEST
            )

        amount = request.data.get("amount")
        if not amount:
            return Response({"detail": "Amount is required."}, status=status.HTTP_400_BAD_REQUEST)

        payment_method = request.data.get("payment_method", "CASH")
        valid_methods = list(LoanRepayment.PaymentMethod.values)
        if payment_method not in valid_methods:
            return Response({"detail": f"Invalid payment method. Choose from: {', '.join(valid_methods)}"}, status=status.HTTP_400_BAD_REQUEST)

        reference = request.data.get("reference", "")
        note = request.data.get("note", "")

        try:
            repayment = RepaymentService.repay_loan(
                loan=loan,
                amount=amount,
                paid_at=timezone.now(),
                received_by=request.user,
                payment_method=payment_method,
                reference=reference,
                note=note,
            )
            loan.refresh_from_db()

            serializer = LoanPaymentSerializer(repayment, many=True)
            return Response(
                {
                    "detail": "Repayment recorded successfully.",
                    "payments": serializer.data,
                    "loan_status": loan.status,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class LoanInstallmentListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, loan_uuid):
        loan = get_object_or_404(Loan, uuid=loan_uuid)
        is_group_member(request.user, loan.group)

        serializer = LoanInstallmentSerializer(
            loan.installments.all().order_by("installment_number"),
            many=True,
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class LoanPaymentListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, loan_uuid):
        loan = get_object_or_404(Loan, uuid=loan_uuid)
        is_group_member(request.user, loan.group)

        serializer = LoanPaymentSerializer(
            loan.repayments.select_related("installment").all().order_by("-paid_at"),
            many=True,
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
