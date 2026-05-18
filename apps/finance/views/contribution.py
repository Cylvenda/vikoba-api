from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.groups.models import Group, GroupMembership
from apps.finance.services.contribution_service import ContributionService
from apps.finance.serializers.contribution import (
    ContributionSerializer,
    CreateContributionSerializer,
)


class ContributionCreateAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        serializer = CreateContributionSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        group = Group.objects.get(uuid=data.get("group_id"))

        member = GroupMembership.objects.get(uuid=data.get("membership_id"))

        contribution = ContributionService.create_contribution(
            member=member,
            group=group,
            amount=data.get("amount"),
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
