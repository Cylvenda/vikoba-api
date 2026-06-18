from apps.finance.models import Contribution
from apps.finance.services.contribution_service import ContributionService

class ContributionPaymentHandler:

    @staticmethod
    def handle(transaction):
        try:
            target_uuid = transaction.metadata.get("target_uuid")
            contribution = Contribution.objects.get(uuid=target_uuid)
            ContributionService.verify_contribution(contribution)
        except Contribution.DoesNotExist:
            pass # Or handle appropriately
