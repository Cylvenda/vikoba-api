from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from apps.groups.models import GroupMembership
from apps.finance.permissions import (
    get_group_or_404,
    is_group_finance_manager,
    is_group_member,
    is_user_group_finance_manager,
)
from apps.finance.services.contribution_service import ContributionService
from apps.finance.serializers.contribution import (
    ContributionSerializer,
    CreateContributionSerializer,
)
from apps.finance.models import Contribution


class ContributionListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        group_uuid = request.query_params.get("group_uuid")
        group = get_group_or_404(group_uuid)

        is_group_member(request.user, group)

        queryset = Contribution.objects.filter(group=group).select_related(
            "group",
            "member__user",
            "received_by",
        )

        if not is_user_group_finance_manager(request.user, group):
            queryset = queryset.filter(member__user=request.user)

        serializer = ContributionSerializer(queryset, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = CreateContributionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        group = get_group_or_404(data["group_id"])

        is_group_finance_manager(request.user, group)

        member = get_object_or_404(
            GroupMembership,
            uuid=data["membership_id"],
            group=group,
            is_active=True,
            is_verified=True,
        )

        contribution = ContributionService.create_contribution(
            member=member,
            group=group,
            amount=data["amount"],
            paid_at=data.get("paid_at"),
            received_by=request.user,
            reference=data.get("reference"),
            note=data.get("note"),
        )

        response_serializer = ContributionSerializer(contribution)

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )
