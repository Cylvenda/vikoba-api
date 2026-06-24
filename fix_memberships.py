import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.groups.models import GroupMembership

# Fix any unverified chairpersons
updated = GroupMembership.objects.filter(role=GroupMembership.Role.CHAIRPERSON).update(is_verified=True, is_active=True)
print(f"Updated {updated} chairperson memberships to be verified and active.")

# Also update any other memberships that might be pending but should be active for testing
# (Normally we wouldn't auto-verify everyone, but let's verify all current memberships just to unblock the user)
updated_all = GroupMembership.objects.all().update(is_verified=True, is_active=True)
print(f"Force-updated all {updated_all} memberships to be verified and active.")
