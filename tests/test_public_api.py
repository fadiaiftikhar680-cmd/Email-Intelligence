"""
Unit tests for Public REST API (v1).
Fulfills Part 5 and Part 12.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from core.security.api_keys import generate_api_key
from core.utilities.constants import SCOPE_EMAIL_VERIFY, SCOPE_ACCOUNT_READ
from apps.api_management.models import APIKey

User = get_user_model()


class PublicAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="api_user@example.com",
            password="StrongPassword123#API"
        )
        self.client = APIClient()

        # Generate API key with email:verify and account:read
        self.raw_key, self.prefix, self.key_hash = generate_api_key()
        self.api_key_obj = APIKey.objects.create(
            user=self.user,
            name="Test Key",
            prefix=self.prefix,
            key_hash=self.key_hash,
            scopes=[SCOPE_EMAIL_VERIFY, SCOPE_ACCOUNT_READ],
            status="active"
        )

    def test_verify_single_api_endpoint(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Api-Key {self.raw_key}")
        response = self.client.post("/api/v1/email/verify", {"email": "hello@example.com"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "hello@example.com")
        self.assertIn("status", response.data)
        self.assertIn("reason_codes", response.data)
        self.assertIn("evidence", response.data)

    def test_account_summary_api_endpoint(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Api-Key {self.raw_key}")
        response = self.client.get("/api/v1/account")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "api_user@example.com")

    def test_revoked_key_rejection(self):
        self.api_key_obj.status = "revoked"
        self.api_key_obj.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Api-Key {self.raw_key}")
        response = self.client.get("/api/v1/account")
        self.assertEqual(response.status_code, 403)

