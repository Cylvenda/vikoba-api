from django.db import models
import uuid
from . import PaymentProvider


class WebhookEvent(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(PaymentProvider, on_delete=models.PROTECT)
    event_type = models.CharField(max_length=100)
    event_key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    payload = models.JSONField()
    signature = models.TextField(blank=True)
    processed = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    headers = models.JSONField(default=dict, blank=True)
    processing_result = models.CharField(max_length=100, blank=True)
    processing_error = models.TextField(blank=True)
