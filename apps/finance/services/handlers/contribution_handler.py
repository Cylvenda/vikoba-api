from finance.services.contribution_service import ContributionService


class ContributionPaymentHandler:

    @staticmethod
    def handle(transaction):

        ContributionService.verify_contribution(
            reference=transaction.reference,
            amount=transaction.amount,
        )
