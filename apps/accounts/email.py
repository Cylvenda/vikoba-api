from djoser import email
from django.conf import settings


class CustomActivationEmail(email.ActivationEmail):
    template_name = "email/activation.html"

    def get_context_data(self):
        context = super().get_context_data()
        context["site_name"] = settings.SITE_NAME
        return context


class CustomPasswordResetEmail(email.PasswordResetEmail):
    template_name = "email/password_reset.html"

    def get_context_data(self):
        context = super().get_context_data()
        context["site_name"] = settings.SITE_NAME
        return context
