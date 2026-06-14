from apps.payments.models.payment_transaction import PaymentTransaction

from .handlers.contribution_handler import ContributionPaymentHandler
from .handlers.loan_repayment_handler import LoanRepaymentHandler
from .handlers.penalty_handler import PenaltyPaymentHandler


class PaymentDispatcher:

    HANDLERS = {
        PaymentTransaction.TransactionPurpose.CONTRIBUTION: ContributionPaymentHandler,
        PaymentTransaction.TransactionPurpose.LOAN_REPAYMENT: LoanRepaymentHandler,
        PaymentTransaction.TransactionPurpose.PENALTY_PAYMENT: PenaltyPaymentHandler,
    }

    @classmethod
    def dispatch(cls, transaction):
        handler = cls.HANDLERS.get(transaction.purpose)

        if not handler:
            return

        handler.handle(transaction)
