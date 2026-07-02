from decimal import Decimal, InvalidOperation
import uuid

from clickpesa import (
    AuthenticationError as ClickPesaAuthenticationError,
    ForbiddenError as ClickPesaForbiddenError,
    ValidationError as ClickPesaValidationError,
)
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.finance.models import Loan
from apps.finance.services.loan_service import LoanService
from apps.finance.services.wallet_service import WalletService as FinanceWalletService
from apps.payments.gateway.clickpesa import ClickPesaGateway
from apps.payments.models import (
    PaymentProvider,
    PaymentTransaction,
    PayoutRequest,
    Wallet,
)
from apps.payments.services.payment_notification_service import notify_payment_event


class PayoutService:
    gateway = ClickPesaGateway()

    PROCESSING_STATUSES = {"AUTHORIZED", "PENDING", "PROCESSING", "INITIATED"}
    SUCCESS_STATUSES = {"SUCCESS"}
    FAILED_STATUSES = {"FAILED", "CANCELLED", "REFUNDED", "REVERSED"}

    @staticmethod
    def normalize_phone(phone):
        normalized = "".join(filter(str.isdigit, phone or ""))
        if normalized.startswith("0"):
            normalized = f"255{normalized[1:]}"
        elif normalized and not normalized.startswith("255"):
            normalized = f"255{normalized}"
        if len(normalized) != 12:
            raise ValidationError(
                {"detail": "The borrower must have a valid Tanzanian mobile number."}
            )
        return normalized

    @staticmethod
    def _reference():
        return f"LP{uuid.uuid4().hex[:24]}"

    @staticmethod
    def _response_item(response):
        if isinstance(response, list):
            return response[0] if response else {}
        if isinstance(response, dict) and isinstance(response.get("data"), list):
            return response["data"][0] if response["data"] else {}
        if isinstance(response, dict) and isinstance(response.get("data"), dict):
            return response["data"]
        return response if isinstance(response, dict) else {}

    @classmethod
    def _status(cls, response):
        item = cls._response_item(response)
        return str(item.get("status") or "").upper()

    @classmethod
    def _decimal_from_response(cls, response, *keys):
        item = cls._response_item(response)
        for key in keys:
            value = item.get(key)
            if value is None:
                continue
            if isinstance(value, dict):
                value = value.get("amount") or value.get("value")
            try:
                return Decimal(str(value)).quantize(Decimal("0.01"))
            except (InvalidOperation, TypeError, ValueError):
                continue
        return Decimal("0.00")

    @staticmethod
    def _provider():
        provider, _ = PaymentProvider.objects.get_or_create(
            provider_type=PaymentProvider.ProviderType.CLICKPESA,
            defaults={"name": "ClickPesa", "is_active": True},
        )
        return provider

    @classmethod
    def preview_loan_payout(cls, *, loan):
        cls._validate_loan(loan)
        phone = cls.normalize_phone(loan.borrower.user.phone)
        reference = cls._reference()
        response = cls.gateway.preview_payout(
            amount=loan.principal_amount,
            phone=phone,
            reference=reference,
        )
        fee = cls._decimal_from_response(
            response, "fee", "transactionFee", "totalFee"
        )
        gateway_balance = cls._decimal_from_response(
            response, "balance", "availableBalance", "accountBalance"
        )
        total_debit = loan.principal_amount + fee
        wallet, _ = Wallet.objects.get_or_create(
            wallet_type=Wallet.WalletType.GROUP,
            owner_uuid=loan.group.uuid,
        )

        return {
            "loan_uuid": str(loan.uuid),
            "borrower_name": loan.borrower.user.full_name or loan.borrower.user.email,
            "phone_number": phone,
            "amount": str(loan.principal_amount),
            "fee": str(fee),
            "total_debit": str(total_debit),
            "currency": "TZS",
            "group_wallet_balance": str(wallet.available_balance),
            "finance_wallet_balance": str(
                FinanceWalletService.get_group_balance(loan.group)
            ),
            "gateway_balance": str(gateway_balance),
            "receiver": cls._response_item(response).get("receiver") or {},
        }

    @staticmethod
    def _validate_loan(loan):
        if loan.status != Loan.Status.APPROVED:
            raise ValidationError(
                {"detail": "Only approved loans can be released."}
            )
        if not loan.borrower.is_active or not loan.borrower.is_verified:
            raise ValidationError(
                {"detail": "The borrower is no longer an active, verified member."}
            )
        available_balance = FinanceWalletService.get_group_balance(loan.group)
        if available_balance < loan.principal_amount:
            raise ValidationError(
                {
                    "detail": (
                        f"Insufficient group funds. Available balance is "
                        f"{available_balance}, but the loan is {loan.principal_amount}."
                    )
                }
            )

    @classmethod
    def initiate_loan_payout(cls, *, loan, initiated_by):
        cls._validate_loan(loan)
        phone = cls.normalize_phone(loan.borrower.user.phone)
        reference = cls._reference()
        preview = cls.gateway.preview_payout(
            amount=loan.principal_amount,
            phone=phone,
            reference=reference,
        )
        fee = cls._decimal_from_response(
            preview, "fee", "transactionFee", "totalFee"
        )
        total_debit = loan.principal_amount + fee

        try:
            with transaction.atomic():
                wallet, _ = Wallet.objects.select_for_update().get_or_create(
                    wallet_type=Wallet.WalletType.GROUP,
                    owner_uuid=loan.group.uuid,
                )
                if wallet.available_balance < total_debit:
                    raise ValidationError(
                        {
                            "detail": (
                                "The group ClickPesa wallet does not have enough available "
                                f"cash. Required TZS {total_debit:,.2f}; available "
                                f"TZS {wallet.available_balance:,.2f}."
                            )
                        }
                    )

                payment_transaction = PaymentTransaction.objects.create(
                    source_wallet=wallet,
                    transaction_type=PaymentTransaction.TransactionType.PAYOUT,
                    purpose=PaymentTransaction.TransactionPurpose.LOAN_DISBURSEMENT,
                    amount=loan.principal_amount,
                    reference=reference,
                    status=PaymentTransaction.Status.PENDING,
                    target_uuid=loan.uuid,
                    initiated_by=initiated_by,
                    metadata={
                        "fee": str(fee),
                        "total_debit": str(total_debit),
                        "phone_number": phone,
                        "preview": preview,
                    },
                )
                PayoutRequest.objects.create(
                    transaction=payment_transaction,
                    beneficiary_name=loan.borrower.user.full_name
                    or loan.borrower.user.email,
                    phone_number=phone,
                    provider=cls._provider(),
                )
                wallet.available_balance -= total_debit
                wallet.reserved_balance += total_debit
                wallet.save(
                    update_fields=["available_balance", "reserved_balance"]
                )
        except IntegrityError:
            existing = PaymentTransaction.objects.filter(
                transaction_type=PaymentTransaction.TransactionType.PAYOUT,
                purpose=PaymentTransaction.TransactionPurpose.LOAN_DISBURSEMENT,
                target_uuid=loan.uuid,
                status__in=[
                    PaymentTransaction.Status.PENDING,
                    PaymentTransaction.Status.PROCESSING,
                    PaymentTransaction.Status.SUCCESS,
                ],
            ).first()
            if existing:
                return existing
            raise

        try:
            response = cls.gateway.payout(
                amount=loan.principal_amount,
                phone=phone,
                reference=reference,
            )
        except Exception as exc:
            if isinstance(
                exc,
                (
                    ClickPesaAuthenticationError,
                    ClickPesaForbiddenError,
                    ClickPesaValidationError,
                ),
            ):
                cls.process_failed_payout(
                    payment_transaction,
                    provider_status="FAILED",
                    detail=str(exc),
                )
                raise

            payment_transaction.status = PaymentTransaction.Status.PROCESSING
            payment_transaction.metadata["submission_warning"] = str(exc)
            payment_transaction.save(update_fields=["status", "metadata"])
            transaction.on_commit(
                lambda: notify_payment_event(
                    payment_transaction,
                    "PAYOUT_INITIATED",
                    detail=(
                        "ClickPesa did not return a final response. The payout "
                        "will be reconciled automatically."
                    ),
                )
            )
            return payment_transaction

        item = cls._response_item(response)
        payment_transaction.provider_reference = str(
            item.get("id") or item.get("orderReference") or ""
        )
        payment_transaction.metadata["raw_response"] = response
        payment_transaction.save(
            update_fields=["provider_reference", "metadata"]
        )

        provider_status = cls._status(response)
        if provider_status in cls.SUCCESS_STATUSES:
            return cls.process_successful_payout(payment_transaction)
        if provider_status in cls.FAILED_STATUSES:
            return cls.process_failed_payout(
                payment_transaction,
                provider_status=provider_status,
            )

        payment_transaction.status = PaymentTransaction.Status.PROCESSING
        payment_transaction.save(update_fields=["status"])
        transaction.on_commit(
            lambda: notify_payment_event(
                payment_transaction, "PAYOUT_INITIATED"
            )
        )
        return payment_transaction

    @classmethod
    @transaction.atomic
    def process_successful_payout(cls, payment_transaction):
        payment_transaction = PaymentTransaction.objects.select_for_update().get(
            pk=payment_transaction.pk
        )
        if payment_transaction.status == PaymentTransaction.Status.SUCCESS:
            return payment_transaction

        wallet = Wallet.objects.select_for_update().get(
            pk=payment_transaction.source_wallet_id
        )
        total_debit = Decimal(
            payment_transaction.metadata.get(
                "total_debit", payment_transaction.amount
            )
        )
        wallet.reserved_balance = max(
            Decimal("0.00"), wallet.reserved_balance - total_debit
        )
        wallet.balance = max(Decimal("0.00"), wallet.balance - total_debit)
        wallet.save(update_fields=["balance", "reserved_balance"])

        loan = Loan.objects.select_for_update().get(
            uuid=payment_transaction.target_uuid
        )
        LoanService.disburse_loan(
            loan=loan,
            disbursed_by=payment_transaction.initiated_by,
            confirmed_payout=True,
        )

        payment_transaction.status = PaymentTransaction.Status.SUCCESS
        payment_transaction.completed_at = timezone.now()
        payment_transaction.save(update_fields=["status", "completed_at"])
        PayoutRequest.objects.filter(transaction=payment_transaction).update(
            processed_at=timezone.now()
        )
        transaction.on_commit(
            lambda: notify_payment_event(payment_transaction, "PAYOUT_SUCCESS")
        )
        return payment_transaction

    @classmethod
    @transaction.atomic
    def process_failed_payout(
        cls, payment_transaction, *, provider_status="FAILED", detail=""
    ):
        payment_transaction = PaymentTransaction.objects.select_for_update().get(
            pk=payment_transaction.pk
        )
        if payment_transaction.status in {
            PaymentTransaction.Status.FAILED,
            PaymentTransaction.Status.REVERSED,
        }:
            return payment_transaction

        wallet = Wallet.objects.select_for_update().get(
            pk=payment_transaction.source_wallet_id
        )
        total_debit = Decimal(
            payment_transaction.metadata.get(
                "total_debit", payment_transaction.amount
            )
        )

        if payment_transaction.status == PaymentTransaction.Status.SUCCESS:
            wallet.balance += total_debit
            wallet.available_balance += total_debit
            loan = Loan.objects.select_for_update().get(
                uuid=payment_transaction.target_uuid
            )
            LoanService.reverse_disbursement(loan=loan)
        else:
            wallet.reserved_balance = max(
                Decimal("0.00"), wallet.reserved_balance - total_debit
            )
            wallet.available_balance += total_debit

        is_reversed = provider_status in {"REFUNDED", "REVERSED"}
        payment_transaction.status = (
            PaymentTransaction.Status.REVERSED
            if is_reversed
            else PaymentTransaction.Status.FAILED
        )
        payment_transaction.completed_at = timezone.now()
        payment_transaction.metadata["provider_status"] = provider_status
        if detail:
            payment_transaction.metadata["failure_detail"] = detail
        payment_transaction.save(
            update_fields=["status", "completed_at", "metadata"]
        )
        wallet.save(
            update_fields=["balance", "available_balance", "reserved_balance"]
        )
        transaction.on_commit(
            lambda: notify_payment_event(
                payment_transaction,
                "PAYOUT_REVERSED" if is_reversed else "PAYOUT_FAILED",
                detail=detail,
            )
        )
        return payment_transaction

    @classmethod
    def refresh_status(cls, payment_transaction):
        if payment_transaction.status not in {
            PaymentTransaction.Status.PENDING,
            PaymentTransaction.Status.PROCESSING,
        }:
            return payment_transaction

        response = cls.gateway.check_payout_status(payment_transaction.reference)
        provider_status = cls._status(response)
        if provider_status in cls.SUCCESS_STATUSES:
            return cls.process_successful_payout(payment_transaction)
        if provider_status in cls.FAILED_STATUSES:
            return cls.process_failed_payout(
                payment_transaction,
                provider_status=provider_status,
            )
        return payment_transaction
