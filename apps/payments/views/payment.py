from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
import uuid

from apps.payments.services.collection_service import CollectionService
from apps.payments.models import Wallet, PaymentTransaction

from apps.finance.models import Contribution, Loan, Fine

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

        amount = request.data.get("amount")
        purpose = request.data.get("purpose")
        target_uuid = request.data.get("target_uuid")

        if not all([phone, amount, purpose, target_uuid]):
            return Response(
                {"detail": "phone, amount, purpose, and target_uuid are required fields."},
                status=status.HTTP_400_BAD_REQUEST
            )

        owner_uuid = None
        try:
            if purpose == PaymentTransaction.TransactionPurpose.CONTRIBUTION:
                owner_uuid = Contribution.objects.get(uuid=target_uuid).group.uuid
            elif purpose == PaymentTransaction.TransactionPurpose.LOAN_REPAYMENT:
                owner_uuid = Loan.objects.get(uuid=target_uuid).group.uuid
            elif purpose == PaymentTransaction.TransactionPurpose.PENALTY_PAYMENT:
                owner_uuid = Fine.objects.get(uuid=target_uuid).group.uuid
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
