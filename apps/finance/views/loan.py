
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework import status
from apps.groups.models import Group, GroupMembership
from apps.finance.models import LoanRequestCategories
from apps.finance.services.loan_service import LoanService
from apps.finance.serializers.loan import (
    LoanSerializer,
    LoanRequestSerializer,
    LoanRequestCategoriesSerializer
)

class LoanRequestCategoriesViewSet(viewsets.ModelViewSet):
    queryset = LoanRequestCategories.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = LoanRequestCategoriesSerializer
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
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
