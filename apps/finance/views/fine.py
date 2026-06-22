from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.finance.models import Fine, FineCategory, FinePayment
from apps.finance.permissions import (
    get_group_or_404,
    is_group_finance_manager,
    is_group_leader,
    is_group_member,
    is_user_group_finance_manager,
)
from apps.finance.serializers.fine import (
    CreateFinePaymentSerializer,
    CreateFineSerializer,
    FineCategorySerializer,
    CreateFineCategorySerializer,
    FinePaymentSerializer,
    FineSerializer,
)
from apps.finance.services.fine_service import FineService
from apps.groups.models import GroupMembership


# ─── Fine Category (CRUD for leaders) ────────────────────────────────────────

class FineCategoryViewSet(viewsets.ModelViewSet):
    """
    Leaders can create / list / update / delete fine categories for their group.
    All verified members can list categories (needed to pick one when issuing a fine).
    """
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return CreateFineCategorySerializer
        return FineCategorySerializer

    def get_queryset(self):
        group_uuid = (
            self.request.query_params.get("group_uuid")
            or self.request.data.get("group_uuid")
        )
        qs = FineCategory.objects.filter(
            group__memberships__user=self.request.user,
            group__memberships__is_active=True,
            group__memberships__is_verified=True,
        ).distinct()
        if group_uuid:
            qs = qs.filter(group__uuid=group_uuid)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = CreateFineCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        group = get_group_or_404(serializer.validated_data.pop("group_uuid"))
        is_group_leader(request.user, group)

        category = FineCategory.objects.create(
            group=group,
            created_by=request.user,
            **serializer.validated_data,
        )
        return Response(FineCategorySerializer(category).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        category = self.get_object()
        group = category.group
        is_group_leader(request.user, group)

        # Allow partial update via PATCH
        partial = kwargs.pop("partial", False)
        allowed_fields = {"name", "description", "default_amount"}
        data = {k: v for k, v in request.data.items() if k in allowed_fields}

        serializer = FineCategorySerializer(category, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        is_group_leader(request.user, category.group)
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─── Fines ────────────────────────────────────────────────────────────────────

class FineListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        group_uuid = request.query_params.get("group_uuid")
        group = get_group_or_404(group_uuid)
        is_group_member(request.user, group)

        queryset = Fine.objects.filter(group=group).select_related(
            "group", "member__user", "fine_category", "issued_by",
        )
        if not is_user_group_finance_manager(request.user, group):
            queryset = queryset.filter(member__user=request.user)

        serializer = FineSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """Issue a new fine to a member. Only group leaders (chair/secretary/treasurer)."""
        serializer = CreateFineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        group = get_group_or_404(data["group_uuid"])
        is_group_finance_manager(request.user, group)

        membership = get_object_or_404(
            GroupMembership,
            uuid=data["membership_uuid"],
            group=group,
        )
        if not membership.is_active:
            raise serializers.ValidationError({"detail": "Cannot issue a fine to an inactive member."})

        fine_category = None
        if data.get("fine_category_uuid"):
            fine_category = get_object_or_404(
                FineCategory,
                uuid=data["fine_category_uuid"],
                group=group,
            )

        fine = FineService.create_fine(
            group=group,
            membership=membership,
            fine_category=fine_category,
            reason=data["reason"],
            amount=data["amount"],
            due_date=data["due_date"],
            issued_by=request.user,
            note=data.get("note", ""),
        )

        return Response(FineSerializer(fine).data, status=status.HTTP_201_CREATED)


# ─── Fine Payments ────────────────────────────────────────────────────────────

class FinePaymentListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        group_uuid = request.query_params.get("group_uuid")
        group = get_group_or_404(group_uuid)
        is_group_member(request.user, group)

        queryset = FinePayment.objects.filter(fine__group=group).select_related(
            "fine", "fine__member__user", "received_by",
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

        fine = get_object_or_404(Fine, uuid=data["fine_id"], group=group)

        payment = FineService.create_fine_payment(
            fine=fine,
            amount=data["amount"],
            paid_at=data.get("paid_at"),
            received_by=request.user,
            reference=data.get("reference"),
            note=data.get("note"),
        )

        return Response(FinePaymentSerializer(payment).data, status=status.HTTP_201_CREATED)
