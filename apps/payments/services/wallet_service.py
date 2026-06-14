from decimal import Decimal
from django.db import transaction


class WalletService:

    @staticmethod
    @transaction.atomic
    def credit(wallet, amount, reference=None):

        wallet.available_balance += Decimal(amount)

        wallet.save(update_fields=["available_balance"])

        return wallet


    @staticmethod
    @transaction.atomic
    def debit(wallet, amount, reference=None):

        amount = Decimal(amount)

        if wallet.available_balance < amount:
            raise ValueError("Insufficient wallet balance.")

        wallet.available_balance -= amount

        wallet.save(update_fields=["available_balance"])

        return wallet

    @staticmethod
    @transaction.atomic
    def reserve(wallet, amount):

        amount = Decimal(amount)

        if wallet.available_balance < amount:
            raise ValueError(
                "Insufficient available balance."
            )

        wallet.available_balance -= amount
        wallet.reserved_balance += amount

        wallet.save(
            update_fields=[
                "available_balance",
                "reserved_balance",
            ]
        )

        return wallet
    
    @staticmethod
    @transaction.atomic
    def release(wallet, amount):

        amount = Decimal(amount)

        if wallet.reserved_balance < amount:
            raise ValueError(
                "Insufficient reserved balance."
            )

        wallet.reserved_balance -= amount
        wallet.available_balance += amount

        wallet.save(
            update_fields=[
                "available_balance",
                "reserved_balance",
            ]
        )

        return wallet
    
    @staticmethod
    @transaction.atomic
    def transfer(
        source_wallet,
        destination_wallet,
        amount,
        reference=None,
    ):

        amount = Decimal(amount)

        WalletService.debit(
            source_wallet,
            amount,
            reference,
        )

        WalletService.credit(
            destination_wallet,
            amount,
            reference,
        )

        return {
            "source_wallet": source_wallet,
            "destination_wallet": destination_wallet,
            "amount": amount,
            "reference": reference,
        }
        
    @staticmethod
    @transaction.atomic
    def consume_reserved(wallet, amount):

        amount = Decimal(amount)

        if wallet.reserved_balance < amount:
            raise ValueError(
                "Insufficient reserved balance."
            )

        wallet.reserved_balance -= amount

        wallet.save(
            update_fields=[
                "reserved_balance"
            ]
        )

        return wallet