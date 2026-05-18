from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.urls import resolve, reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .views import (
    CurrentUserView,
    CustomeTokenObtainPairView,
    CustomeTokenRefreshView,
    CustomeTokenVerifyView,
    LogoutView,
)

User = get_user_model()


class AccountUrlTests(SimpleTestCase):
    def test_login_route(self):
        self.assertEqual(reverse("login"), "/api/me/auth/login/")
        self.assertIs(resolve("/api/me/auth/login/").func.view_class, CustomeTokenObtainPairView)

    def test_refresh_route(self):
        self.assertEqual(reverse("token_refresh"), "/api/me/auth/refresh/")
        self.assertIs(
            resolve("/api/me/auth/refresh/").func.view_class,
            CustomeTokenRefreshView,
        )

    def test_verify_route(self):
        self.assertEqual(reverse("token_verify"), "/api/me/auth/verify/")
        self.assertIs(
            resolve("/api/me/auth/verify/").func.view_class,
            CustomeTokenVerifyView,
        )

    def test_legacy_csrf_alias_points_to_refresh(self):
        self.assertEqual(reverse("csrf"), "/api/me/auth/csrf/")
        self.assertIs(
            resolve("/api/me/auth/csrf/").func.view_class,
            CustomeTokenRefreshView,
        )

    def test_logout_route(self):
        self.assertEqual(reverse("logout"), "/api/me/auth/logout/")
        self.assertIs(resolve("/api/me/auth/logout/").func.view_class, LogoutView)

    def test_current_user_route(self):
        self.assertEqual(reverse("current_user"), "/api/me/auth/me/")
        self.assertIs(
            resolve("/api/me/auth/me/").func.view_class,
            CurrentUserView,
        )


class AccountAuthFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="member@example.com",
            phone="+255700000001",
            password="StrongPassword123!",
            first_name="Member",
            last_name="User",
        )

    def test_login_sets_auth_cookies_and_current_user_endpoint_works(self):
        login_response = self.client.post(
            reverse("login"),
            {"email": self.user.email, "password": "StrongPassword123!"},
            format="json",
        )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_response.cookies)
        self.assertIn("refresh", login_response.cookies)

        me_response = self.client.get(reverse("current_user"))

        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["email"], self.user.email)

    def test_refresh_uses_refresh_cookie_and_issues_new_access_token(self):
        self.client.post(
            reverse("login"),
            {"email": self.user.email, "password": "StrongPassword123!"},
            format="json",
        )

        refresh_response = self.client.post(reverse("token_refresh"), {}, format="json")

        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_response.data)
        self.assertIn("access", refresh_response.cookies)

    def test_logout_clears_authentication_for_followup_requests(self):
        self.client.post(
            reverse("login"),
            {"email": self.user.email, "password": "StrongPassword123!"},
            format="json",
        )

        logout_response = self.client.post(reverse("logout"))

        self.assertEqual(logout_response.status_code, status.HTTP_204_NO_CONTENT)

        self.client.cookies.pop("access", None)
        self.client.cookies.pop("refresh", None)

        me_response = self.client.get(reverse("current_user"))
        self.assertEqual(me_response.status_code, status.HTTP_401_UNAUTHORIZED)


class AdminManagementTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            phone="+255700000100",
            password="StrongPassword123!",
        )
        self.member = User.objects.create_user(
            email="member2@example.com",
            phone="+255700000101",
            password="StrongPassword123!",
            first_name="Regular",
        )

    def test_admin_can_list_and_update_users(self):
        self.client.force_authenticate(user=self.admin_user)

        list_response = self.client.get(reverse("admin-user-list"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(user["email"] == self.member.email for user in list_response.data))

        update_response = self.client.patch(
            reverse("admin-user-detail", kwargs={"pk": self.member.pk}),
            {"is_active": False, "first_name": "Updated"},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)

        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)
        self.assertEqual(self.member.first_name, "Updated")

    def test_non_admin_cannot_access_admin_endpoints(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.get(reverse("admin-user-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
