from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from apps.groups.models import GroupMembership
from apps.finance.models import Loan, LoanRequestCategories
from apps.finance.services.loan_service import LoanService
from apps.finance.serializers.loan import (
    LoanRequestCategoriesSerializer,
    LoanSerializer,
    LoanRequestSerializer,
)
from apps.finance.permissions import (
    get_group_or_404,
    is_group_leader,
    is_group_member,
    is_user_group_leader,
)

class LoanRequestCategoriesViewSet(viewsets.ModelViewSet):
    queryset: QuerySet[LoanRequestCategories] = LoanRequestCategories.objects.all()
    serializer_class = LoanRequestCategoriesSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"
    
    def get_queryset(self) -> QuerySet[LoanRequestCategories]:
        group_uuid = (
            self.request.query_params.get("group_uuid")
            or self.request.data.get("group_uuid")
        )

        queryset = LoanRequestCategories.objects.filter(
            group__memberships__user=self.request.user,
            group__memberships__is_active=True,
            group__memberships__is_verified=True
        ).distinct()

        if group_uuid:
            queryset = queryset.filter(group__uuid=group_uuid)

        return queryset

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

    def get(self, request):
        group_uuid = request.query_params.get("group_uuid")
        group = get_group_or_404(group_uuid)

        is_group_member(request.user, group)

        queryset = Loan.objects.filter(group=group).select_related(
            "group",
            "borrower__user",
            "loan_request_category",
        )

        if not is_user_group_leader(request.user, group):
            queryset = queryset.filter(borrower__user=request.user)

        serializer = LoanSerializer(queryset, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = LoanRequestSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        group = get_group_or_404(data["group_id"])
        is_group_member(request.user, group)

        borrower = get_object_or_404(
            GroupMembership,
            group=group,
            user=request.user,
            is_active=True,
            is_verified=True,
        )
        loan_request_category = get_object_or_404(
            
            LoanRequestCategories,
            uuid=data["loan_request_category_id"],
            group=group,
        )

        loan = LoanService.request_loan(
            borrower=borrower,
            group=group,
            loan_request_category=loan_request_category,
            interest_rate=data["interest_rate"],
            purpose=data.get("purpose", ""),
        )

        response_serializer = LoanSerializer(loan)

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class ApproveLoanAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, loan_uuid):
        loan = get_object_or_404(
            Loan.objects.select_related("group", "loan_request_category"),
            uuid=loan_uuid,
        )

        is_group_leader(request.user, loan.group)

        if loan.status != Loan.Status.PENDING:
            return Response(
                {"detail": "Only pending loans can be approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        loan = LoanService.approve_loan(
            loan=loan,
            approved_by=request.user,
        )

        serializer = LoanSerializer(loan)

        return Response(serializer.data, status=status.HTTP_200_OK)


class RejectLoanAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, loan_uuid):
        loan = get_object_or_404(
            Loan.objects.select_related("group", "loan_request_category"),
            uuid=loan_uuid,
        )

        is_group_leader(request.user, loan.group)

        if loan.status != Loan.Status.PENDING:
            return Response(
                {"detail": "Only pending loans can be rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        loan = LoanService.reject_loan(loan=loan)

        serializer = LoanSerializer(loan)

        return Response(serializer.data, status=status.HTTP_200_OK)
