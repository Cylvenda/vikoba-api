from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from apps.groups.models import Group
from apps.finance.services.wallet_service import WalletService


class GroupWalletReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, group_uuid):
        group = get_object_or_404(Group, uuid=group_uuid)
        return Response(WalletService.build_wallet_report(group))
