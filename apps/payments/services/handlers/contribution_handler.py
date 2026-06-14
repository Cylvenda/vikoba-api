from apps.finance.models import Contribution
from apps.finance.services.contribution_service import ContributionService

class ContributionPaymentHandler:

    @staticmethod
    def handle(transaction):
        try:
            contribution = Contribution.objects.get(uuid=transaction.reference)
            ContributionService.verify_contribution(contribution)
        except Contribution.DoesNotExist:
            pass # Or handle appropriately
