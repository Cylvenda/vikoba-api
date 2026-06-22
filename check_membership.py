import os
import django
import sys
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.groups.models import GroupMembership
from apps.groups.serializers import GroupMembershipSerializer

memberships = GroupMembership.objects.all()[:3]
for m in memberships:
    data = GroupMembershipSerializer(m).data
    print(json.dumps(data, indent=2))
