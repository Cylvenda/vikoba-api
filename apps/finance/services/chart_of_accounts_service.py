from apps.finance.models import LedgerAccount


class ChartOfAccountsService:

    @staticmethod
    def _get_or_create_account(code, name, account_type):
        account, _ = LedgerAccount.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "account_type": account_type,
            }
        )
        return account

    @classmethod
    def get_group_wallet_account(cls, group=None):
        return cls._get_or_create_account(
            code="1100",
            name="Group Wallet",
            account_type=LedgerAccount.AccountType.ASSET,
        )

    @classmethod
    def get_loan_receivable_account(cls, group=None):
        return cls._get_or_create_account(
            code="1200",
            name="Loans Receivable",
            account_type=LedgerAccount.AccountType.ASSET,
        )

    @classmethod
    def get_member_savings_account(cls, group=None):
        return cls._get_or_create_account(
            code="2000",
            name="Member Savings",
            account_type=LedgerAccount.AccountType.LIABILITY,
        )

    @classmethod
    def get_interest_income_account(cls, group=None):
        return cls._get_or_create_account(
            code="4000",
            name="Interest Income",
            account_type=LedgerAccount.AccountType.INCOME,
        )

    @classmethod
    def get_penalty_income_account(cls, group=None):
        # Using 4100 as an example for Penalty Income
        return cls._get_or_create_account(
            code="4100",
            name="Penalty Income",
            account_type=LedgerAccount.AccountType.INCOME,
        )
