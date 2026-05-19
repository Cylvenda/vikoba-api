from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework import status
from django.db.models import QuerySet
from apps.groups.models import Group, GroupMembership
from apps.finance.models import LoanRequestCategories
from apps.finance.services.loan_service import LoanService
from apps.finance.serializers.loan import (
    LoanSerializer,
    LoanRequestSerializer,
    LoanRequestCategoriesSerializer
)
from apps.finance.permissions import is_group_leader, get_group_or_404

class LoanRequestCategoriesViewSet(viewsets.ModelViewSet):
    queryset: QuerySet[LoanRequestCategories] = LoanRequestCategories.objects.all()
    serializer_class = LoanRequestCategoriesSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"
    
    def get_queryset(self) -> QuerySet[LoanRequestCategories]:
        group_uuid = self.request.data.get("group_uuid")

        return LoanRequestCategories.objects.filter(
            group__uuid=group_uuid,
            group__memberships__user=self.request.user,
            group__memberships__is_active=True,
            group__memberships__is_verified=True
        ).distinct()

    def perform_create(self, serializer):
        group_uuid = self.request.data.get("group_uuid")

        group = get_group_or_404(group_uuid)

        # Check permission BEFORE saving
        is_group_leader(self.request.user, group)

        serializer.save(created_by=self.request.user, group=group)

    def perform_update(self, serializer):
        group = serializer.instance.group

        is_group_leader(self.request.user, group)

        serializer.save()

    def perform_destroy(self, instance):
        is_group_leader(self.request.user, instance.group)

        instance.delete()


class LoanRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = LoanRequestSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        group = Group.objects.get(uuid=data["group_id"])

        borrower = GroupMembership.objects.get(uuid=data["borrower_id"])

        loan = LoanService.request_loan(
            borrower=borrower,
            group=group,
            amount_requested=data["amount_requested"],
            interest_rate=data["interest_rate"],
            duration_months=data["duration_months"],
            purpose=data["purpose"],
        )

        response_serializer = LoanSerializer(loan)

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )
