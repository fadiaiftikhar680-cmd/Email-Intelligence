"""
Unit tests for Accounts, Argon2 Hasher, and Owner-Only Permission Isolation.
Fulfills Part 4.4, Part 8.1, Part 12, and Part 23.3.
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.email_verifier.models import EmailVerification
from apps.history_reports.models import ExportRecord

User = get_user_model()


class AccountsAndIsolationTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            email="user_a@example.com",
            password="StrongPassword123#A"
        )
        self.user_b = User.objects.create_user(
            email="user_b@example.com",
            password="StrongPassword123#B"
        )
        self.client_a = Client()
        self.client_a.force_login(self.user_a)

        self.client_b = Client()
        self.client_b.force_login(self.user_b)

    def test_argon2_password_hashing(self):
        self.assertTrue(self.user_a.password.startswith("argon2"))
        self.assertTrue(self.user_a.check_password("StrongPassword123#A"))
        self.assertFalse(self.user_a.check_password("WrongPassword123"))

    def test_owner_only_isolation_on_exports(self):
        # User A creates an export record
        export_a = ExportRecord.objects.create(
            owner=self.user_a,
            source_type="test",
            source_id="123",
            format="csv",
            file_ref="exports/test_a.csv"
        )

        # User B attempts to access User A's export -> MUST return 404
        url = reverse("download_export", kwargs={"export_id": export_a.id})
        response_b = self.client_b.get(url)
        self.assertEqual(response_b.status_code, 404)

    def test_account_deletion_cascade(self):
        # Create records for User A
        ver = EmailVerification.objects.create(
            owner=self.user_a,
            email_normalized="test@example.com",
            status="deliverable"
        )
        ver_id = ver.id

        # Delete User A
        self.user_a.delete()

        # Check verifications cascade deleted
        self.assertFalse(EmailVerification.objects.filter(id=ver_id).exists())

