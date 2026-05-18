from django.db import models


class WalletService:

    @staticmethod
    def get_group_balance(group):
        if group is None:
            return 0

        total_in = (
            group.transactions.filter(direction="IN")
            .aggregate(total=models.Sum("amount"))["total"]
            or 0
        )

        total_out = (
            group.transactions.filter(direction="OUT")
            .aggregate(total=models.Sum("amount"))["total"]
            or 0
        )

        return total_in - total_out
