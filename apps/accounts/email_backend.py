"""HTTPS email backend for Brevo.

Unlike SMTP, this works from hosting services that block outbound SMTP ports.
Set EMAIL_BACKEND=apps.accounts.email_backend.BrevoEmailBackend and provide
BREVO_API_KEY in the production environment.
"""

import json
import logging
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMultiAlternatives


logger = logging.getLogger(__name__)

_SENDER_RE = re.compile(r"^(.*)<([^>]+)>$")


class BrevoEmailBackend(BaseEmailBackend):
    endpoint = "https://api.brevo.com/v3/smtp/email"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = os.getenv("BREVO_API_KEY", "").strip()
        self.timeout = int(os.getenv("BREVO_EMAIL_TIMEOUT", "10"))
        self.sender_name = os.getenv("BREVO_SENDER_NAME", "Community Hub")
        self.sender_email = os.getenv("BREVO_SENDER_EMAIL", "").strip()
        if not self.sender_email:
            default_from = os.getenv("DEFAULT_FROM_EMAIL", "").strip()
            match = _SENDER_RE.match(default_from)
            if match:
                self.sender_email = match.group(2).strip()
            if not self.sender_email:
                self.sender_email = default_from

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            if self.fail_silently:
                return 0
            raise ValueError("BREVO_API_KEY must be set when using BrevoEmailBackend.")
        if not self.sender_email:
            if self.fail_silently:
                return 0
            raise ValueError(
                "BREVO_SENDER_EMAIL or DEFAULT_FROM_EMAIL must be set when using BrevoEmailBackend."
            )

        sent_count = 0
        for message in email_messages:
            try:
                self._send(message)
                sent_count += 1
            except HTTPError as error:
                if not self.fail_silently:
                    details = error.read().decode("utf-8", errors="replace")[:500]
                    logger.error(
                        "Brevo rejected email with HTTP %s: %s", error.code, details
                    )
                    raise RuntimeError(
                        f"Brevo rejected email ({error.code}): {details}"
                    ) from error
            except (URLError, TimeoutError, ValueError) as error:
                if not self.fail_silently:
                    raise RuntimeError(f"Brevo could not send email: {error}") from error
        return sent_count

    def _send(self, message):
        to_recipients = []
        for addr in message.to:
            to_recipients.append({"email": addr.strip()})
        for addr in getattr(message, "cc", []) or []:
            to_recipients.append({"email": addr.strip()})
        for addr in getattr(message, "bcc", []) or []:
            to_recipients.append({"email": addr.strip()})

        payload = {
            "sender": {
                "name": self.sender_name,
                "email": self.sender_email,
            },
            "to": to_recipients,
            "subject": message.subject,
            "textContent": message.body,
        }
        html_body = self._html_body(message)
        if html_body:
            payload["htmlContent"] = html_body

        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "api-key": self.api_key,
                "accept": "application/json",
                "content-type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Unexpected Brevo response status: {response.status}")

    @staticmethod
    def _html_body(message):
        if isinstance(message, EmailMultiAlternatives):
            for content, mimetype in message.alternatives:
                if mimetype == "text/html":
                    return content
        return ""
