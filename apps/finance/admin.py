from django.contrib import admin
from .models import Loan, LoanInstallment, LoanRepayment, LoanProduct, Contribution, Fine, FinePayment, Transaction

admin.site.register(Contribution)
admin.site.register(LoanProduct)
admin.site.register(Loan)
admin.site.register(LoanInstallment)
admin.site.register(LoanRepayment)
admin.site.register(Fine)
admin.site.register(FinePayment)
admin.site.register(Transaction)
