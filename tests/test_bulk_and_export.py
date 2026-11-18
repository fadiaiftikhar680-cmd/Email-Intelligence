"""
Unit tests for Bulk Processing, Delimiter Detection, and Formula Injection Neutralization.
Fulfills Part 8.4, Part 12, and Part 23.5.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from core.utilities.normalization import neutralize_formula_injection
from apps.bulk_processing.services import detect_csv_delimiter, create_bulk_job_from_file, process_bulk_job
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()


class BulkAndExportSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="bulkuser@example.com",
            password="StrongPassword123#Bulk"
        )

    def test_formula_injection_neutralization(self):
        # Cells starting with =, +, -, @ must be prepended with '
        self.assertEqual(neutralize_formula_injection("=cmd|'/C calc'!A0"), "'=cmd|'/C calc'!A0")
        self.assertEqual(neutralize_formula_injection("+12345"), "'+12345")
        self.assertEqual(neutralize_formula_injection("-5+10"), "'-5+10")
        self.assertEqual(neutralize_formula_injection("@SUM(A1:A10)"), "'@SUM(A1:A10)")
        self.assertEqual(neutralize_formula_injection("\tcmd"), "'\tcmd")

        # Normal safe text remains unescaped
        self.assertEqual(neutralize_formula_injection("user@example.com"), "user@example.com")
        self.assertEqual(neutralize_formula_injection("deliverable"), "deliverable")

    def test_csv_delimiter_detection(self):
        csv_comma = "email,name\njohn@example.com,John"
        csv_semi = "email;name\njohn@example.com;John"
        csv_tab = "email\tname\njohn@example.com\tJohn"

        self.assertEqual(detect_csv_delimiter(csv_comma), ",")
        self.assertEqual(detect_csv_delimiter(csv_semi), ";")
        self.assertEqual(detect_csv_delimiter(csv_tab), "\t")

    def test_bulk_job_lifecycle(self):
        csv_content = b"Email,Name\ninfo@example.com,Info\nsupport@example.com,Support\ninfo@example.com,Duplicate"
        uploaded = SimpleUploadedFile("contacts.csv", csv_content, content_type="text/csv")

        job = create_bulk_job_from_file(uploaded, "contacts.csv", self.user, email_column="Email")
        self.assertEqual(job.total_rows, 3)
        self.assertEqual(job.valid_rows, 2)
        self.assertEqual(job.duplicate_rows, 1)

        # Process job
        completed_job = process_bulk_job(str(job.id))
        self.assertEqual(completed_job.status, "completed")
        self.assertEqual(completed_job.records.filter(state="verified").count(), 2)

