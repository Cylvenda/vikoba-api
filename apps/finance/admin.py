from django.contrib import admin
from .models import (
    Contribution,
    Fine,
    FinePayment,
    GroupWallet,
    Loan,
    LoanInstallment,
    LoanProduct,
    LoanRepayment,
    MemberWallet,
    Transaction,
)

admin.site.register(Contribution)
admin.site.register(LoanProduct)
admin.site.register(Loan)
admin.site.register(LoanInstallment)
admin.site.register(LoanRepayment)
admin.site.register(Fine)
admin.site.register(FinePayment)
admin.site.register(GroupWallet)
admin.site.register(MemberWallet)
admin.site.register(Transaction)
