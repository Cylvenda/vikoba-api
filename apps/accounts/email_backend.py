"""HTTPS email backend for Resend.

Unlike SMTP, this works from hosting services that block outbound SMTP ports.
Set EMAIL_BACKEND=apps.accounts.email_backend.ResendEmailBackend and provide
RESEND_API_KEY in the production environment.
"""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMultiAlternatives
from django.core.mail.utils import DNS_NAME


class ResendEmailBackend(BaseEmailBackend):
    endpoint = "https://api.resend.com/emails"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = os.getenv("RESEND_API_KEY", "").strip()
        self.timeout = int(os.getenv("RESEND_EMAIL_TIMEOUT", "10"))

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            if self.fail_silently:
                return 0
            raise ValueError("RESEND_API_KEY must be set when using ResendEmailBackend.")

        sent_count = 0
        for message in email_messages:
            try:
                self._send(message)
                sent_count += 1
            except (HTTPError, URLError, TimeoutError, ValueError) as error:
                if not self.fail_silently:
                    raise RuntimeError(f"Resend could not send email: {error}") from error
        return sent_count

    def _send(self, message):
        payload = {
            "from": message.from_email,
            "to": message.to,
            "subject": message.subject,
        }
        html_body = self._html_body(message)
        if html_body:
            payload["html"] = html_body
            if message.body:
                payload["text"] = message.body
        else:
            payload["text"] = message.body

        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": f"Django/{DNS_NAME.get_fqdn()}",
            },
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Unexpected Resend response status: {response.status}")

    @staticmethod
    def _html_body(message):
        if isinstance(message, EmailMultiAlternatives):
            for content, mimetype in message.alternatives:
                if mimetype == "text/html":
                    return content
        return ""
