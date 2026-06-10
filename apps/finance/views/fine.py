from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.finance.models import Fine, FinePayment
from apps.finance.permissions import (
    get_group_or_404,
    is_group_finance_manager,
    is_group_member,
    is_user_group_finance_manager,
)
from apps.finance.serializers.fine import (
    CreateFinePaymentSerializer,
    FinePaymentSerializer,
    FineSerializer,
)
from apps.finance.services.fine_service import FineService


class FineListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        group_uuid = request.query_params.get("group_uuid")
        group = get_group_or_404(group_uuid)

        is_group_member(request.user, group)

        queryset = Fine.objects.filter(group=group).select_related(
            "group",
            "member__user",
        )

        if not is_user_group_finance_manager(request.user, group):
            queryset = queryset.filter(member__user=request.user)

        serializer = FineSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FinePaymentListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        group_uuid = request.query_params.get("group_uuid")
        group = get_group_or_404(group_uuid)

        is_group_member(request.user, group)

        queryset = FinePayment.objects.filter(fine__group=group).select_related(
            "fine",
            "fine__member__user",
            "received_by",
        )

        if not is_user_group_finance_manager(request.user, group):
            queryset = queryset.filter(fine__member__user=request.user)

        serializer = FinePaymentSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = CreateFinePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        group = get_group_or_404(data["group_id"])

        is_group_finance_manager(request.user, group)

        fine = get_object_or_404(
            Fine,
            uuid=data["fine_id"],
            group=group,
        )

        payment = FineService.create_fine_payment(
            fine=fine,
            amount=data["amount"],
            paid_at=data.get("paid_at"),
            received_by=request.user,
            reference=data.get("reference"),
            note=data.get("note"),
        )

        response_serializer = FinePaymentSerializer(payment)

        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
