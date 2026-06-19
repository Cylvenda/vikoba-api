from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.payments.services.webhook_service import WebhookService

class ClickPesaWebhookAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        payload = request.data
        signature = request.headers.get("X-Signature") or ""

        try:
            WebhookService.process_clickpesa_event(payload, signature)
        except Exception as e:
            # We log but usually return 200 to prevent retries if it's a validation error.
            # But for critical processing errors, 400/500 could be returned depending on the gateway doc.
            # We will return 400 to show the failure.
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"status": "received"}, status=status.HTTP_200_OK)
