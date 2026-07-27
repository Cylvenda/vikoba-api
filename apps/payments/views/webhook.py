from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.payments.services.webhook_service import WebhookService


class ClickPesaWebhookAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        payload = request.data
        signature = (
            request.headers.get("X-ClickPesa-Signature")
            or request.headers.get("X-Signature")
            or ""
        )

        ip_address = request.META.get("REMOTE_ADDR")
        headers = {key: value for key, value in request.headers.items()}

        try:
            WebhookService.process_clickpesa_event(
                payload, signature, ip_address=ip_address, headers=headers
            )
        except ValueError as exc:
            error_message = str(exc)
            if "signature" in error_message.lower():
                return Response(
                    {"detail": "Invalid webhook signature."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            return Response({"detail": error_message}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"status": "received"}, status=status.HTTP_200_OK)
