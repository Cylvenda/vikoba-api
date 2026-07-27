from clickpesa import ClickPesaError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
import uuid
import logging
from decimal import Decimal, InvalidOperation

from apps.payments.services.collection_service import CollectionService
from apps.payments.services.payout_service import PayoutService
from apps.payments.models import Wallet, PaymentTransaction

from apps.finance.models import Contribution, Loan, Fine
from apps.finance.permissions import is_group_treasurer
from apps.groups.models import GroupMembership


logger = logging.getLogger(__name__)

class TransactionStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, transaction_uuid):
        try:
            transaction = PaymentTransaction.objects.get(uuid=transaction_uuid)
            wallet = transaction.source_wallet or transaction.destination_wallet
            is_involved = transaction.initiated_by_id == request.user.id
            if wallet and wallet.owner_uuid:
                is_involved = is_involved or GroupMembership.objects.filter(
                    group__uuid=wallet.owner_uuid,
                    user=request.user,
                    is_active=True,
                    is_verified=True,
                ).exists()
            if not is_involved:
                return Response(
                    {"detail": "You cannot view this transaction."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            return Response(
                {
                    "uuid": str(transaction.uuid),
                    "status": transaction.status,
                    "provider_reference": transaction.provider_reference,
                    "reference": transaction.reference,
                    "completed_at": transaction.completed_at,
                },
                status=status.HTTP_200_OK
            )
        except PaymentTransaction.DoesNotExist:
            return Response(
                {"detail": "Transaction not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as exc:
            logger.error("Transaction status lookup failed: %s", exc, exc_info=True)
            return Response(
                {"detail": "Unable to retrieve payment status right now. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class InitiateMobileCollectionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        phone = request.data.get("phone", "")
        if phone:
            phone = ''.join(filter(str.isdigit, phone))
            if phone.startswith("0"):
                phone = "255" + phone[1:]
            elif not phone.startswith("255"):
                phone = "255" + phone

        raw_amount = request.data.get("amount")
        purpose = request.data.get("purpose")
        target_uuid = request.data.get("target_uuid")

        if not all([phone, raw_amount, purpose, target_uuid]):
            return Response(
                {"detail": "phone, amount, purpose, and target_uuid are required fields."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            amount = Decimal(str(raw_amount)).quantize(Decimal("0.01"))
            if amount <= 0:
                raise InvalidOperation
        except (InvalidOperation, TypeError, ValueError):
            return Response(
                {"detail": "amount must be a positive number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        owner_uuid = None
        try:
            if purpose == PaymentTransaction.TransactionPurpose.CONTRIBUTION:
                contribution = Contribution.objects.select_related(
                    "group", "member__user"
                ).get(uuid=target_uuid)
                if contribution.member.user_id != request.user.id:
                    return Response(
                        {"detail": "You can only pay your own contribution."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                if amount != contribution.amount:
                    return Response(
                        {
                            "detail": (
                                "The payment amount must match the contribution "
                                f"amount of TZS {contribution.amount}."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                owner_uuid = contribution.group.uuid
            elif purpose == PaymentTransaction.TransactionPurpose.LOAN_REPAYMENT:
                loan = Loan.objects.select_related(
                    "group", "borrower__user"
                ).get(uuid=target_uuid)
                if loan.borrower.user_id != request.user.id:
                    return Response(
                        {"detail": "You can only repay your own loan."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                owner_uuid = loan.group.uuid
            elif purpose == PaymentTransaction.TransactionPurpose.PENALTY_PAYMENT:
                fine = Fine.objects.get(uuid=target_uuid)
                if fine.member.user != request.user:
                    return Response(
                        {"detail": "You can only pay your own fines."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                owner_uuid = fine.group.uuid
            else:
                return Response(
                    {"detail": "Unsupported payment purpose."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (Contribution.DoesNotExist, Loan.DoesNotExist, Fine.DoesNotExist):
            return Response(
                {"detail": "Invalid target_uuid for the given purpose."},
                status=status.HTTP_400_BAD_REQUEST
            )

        destination_wallet, _ = Wallet.objects.get_or_create(
            wallet_type=Wallet.WalletType.GROUP,
            owner_uuid=owner_uuid
        )
        reference = uuid.uuid4().hex[:20]

        try:
            transaction = CollectionService.initiate_mobile_collection(
                amount=amount,
                phone=phone,
                destination_wallet=destination_wallet,
                reference=reference,
                purpose=purpose,
                target_uuid=target_uuid,
                initiated_by=request.user,
            )
        except ClickPesaError as exc:
            logger.error(
                "ClickPesa service unavailable for user %s: %s",
                request.user.id,
                str(exc),
            )
            return Response(
                {
                    "detail": (
                        "Payment service is temporarily unavailable. "
                        "Please try again later. The system administrator has been notified."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            return Response(
                {"detail": f"Payment initiation failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {
                "transaction_uuid": str(transaction.uuid),
                "status": transaction.status,
                "message": "Mobile money collection initiated. Please check your phone."
            },
            status=status.HTTP_200_OK
        )


class LoanPayoutPreviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, loan_uuid):
        try:
            loan = Loan.objects.select_related(
                "group", "borrower__user", "loan_product"
            ).get(uuid=loan_uuid)
        except Loan.DoesNotExist:
            return Response(
                {"detail": "Loan not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_group_treasurer(request.user, loan.group)
        try:
            preview = PayoutService.preview_loan_payout(loan=loan)
        except Exception as exc:
            return Response(
                {"detail": f"Unable to preview ClickPesa payout: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(preview, status=status.HTTP_200_OK)


class InitiateLoanPayoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, loan_uuid):
        if request.data.get("confirmed") is not True:
            return Response(
                {"detail": "Treasurer confirmation is required before releasing money."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            loan = Loan.objects.select_related(
                "group", "borrower__user", "loan_product"
            ).get(uuid=loan_uuid)
        except Loan.DoesNotExist:
            return Response(
                {"detail": "Loan not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_group_treasurer(request.user, loan.group)
        try:
            payment_transaction = PayoutService.initiate_loan_payout(
                loan=loan,
                initiated_by=request.user,
            )
        except Exception as exc:
            return Response(
                {"detail": f"Loan payout could not be submitted: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "transaction_uuid": str(payment_transaction.uuid),
                "status": payment_transaction.status,
                "message": (
                    "ClickPesa payout submitted. The loan will become active "
                    "only after the transfer succeeds."
                ),
            },
            status=status.HTTP_200_OK,
        )
