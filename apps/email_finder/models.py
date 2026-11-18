"""
FinderJob, CrawlPage, Company, Person, and DiscoveredEmail Models.
Fulfills Part 4 (4.1 FinderJob, CrawlPage, Company, Person, DiscoveredEmail) and Part 7.
"""
import uuid
from django.db import models
from django.conf import settings
from core.utilities.constants import (
    JOB_STATUS_CHOICES,
    JOB_STATUS_QUEUED,
    CATEGORY_CHOICES,
    CATEGORY_UNKNOWN,
    ORIGIN_DISCOVERED,
    EVIDENCE_DOMAIN,
)


class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="companies")
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255, db_index=True)
    website = models.URLField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("owner", "domain")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.domain})"


class Person(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="people")
    full_name = models.CharField(max_length=255)
    job_title = models.CharField(max_length=255, blank=True)
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL, related_name="employees")
    profile_url = models.URLField(max_length=500, blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.job_title})"


class FinderJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="finder_jobs")
    kind = models.CharField(max_length=30)  # 'company', 'person_url', 'person_name'
    input_json = models.JSONField(default=dict)
    status = models.CharField(max_length=30, choices=JOB_STATUS_CHOICES, default=JOB_STATUS_QUEUED)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    result_count = models.IntegerField(default=0)
    error_code = models.CharField(max_length=50, blank=True)
    idempotency_key = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kind} job ({self.id}) - {self.status}"

    @property
    def display_target(self):
        if not isinstance(self.input_json, dict):
            return "Discovery Target"
        return (
            self.input_json.get("url")
            or self.input_json.get("full_name")
            or self.input_json.get("profile_url")
            or self.input_json.get("domain")
            or "Discovery Target"
        )

    @property
    def batch_id(self):
        if isinstance(self.input_json, dict):
            return self.input_json.get("batch_id")
        return None

    @property
    def batch_name(self):
        if isinstance(self.input_json, dict):
            return self.input_json.get("batch_name")
        return None


class CrawlPage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(FinderJob, on_delete=models.CASCADE, related_name="visited_pages")
    url = models.URLField(max_length=1000)
    final_url = models.URLField(max_length=1000, blank=True)
    http_status = models.IntegerField(default=0)
    robots_allowed = models.BooleanField(default=True)
    fetched_at = models.DateTimeField(auto_now_add=True)
    content_hash = models.CharField(max_length=64, blank=True)
    error_code = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ("job", "url")
        ordering = ["fetched_at"]


class DiscoveredEmail(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="discovered_emails")
    job = models.ForeignKey(FinderJob, on_delete=models.CASCADE, related_name="discovered_emails")
    person = models.ForeignKey(Person, null=True, blank=True, on_delete=models.SET_NULL, related_name="emails")
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL, related_name="emails")
    email_normalized = models.CharField(max_length=255, db_index=True)
    origin = models.CharField(max_length=30, default=ORIGIN_DISCOVERED)  # 'discovered' or 'inferred'
    method = models.CharField(max_length=50)  # 'mailto_link', 'page_text', 'company_pattern'
    source_page = models.ForeignKey(CrawlPage, null=True, blank=True, on_delete=models.SET_NULL)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default=CATEGORY_UNKNOWN)
    evidence_level = models.CharField(max_length=20, default=EVIDENCE_DOMAIN)
    found_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("job", "email_normalized")
        ordering = ["-found_at"]

    def __str__(self):
        return f"{self.email_normalized} ({self.origin})"

    @property
    def verification(self):
        from apps.email_verifier.models import EmailVerification
        return EmailVerification.objects.filter(discovered_email_id=self.id).first()


class SocialAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="social_accounts")
    email_searched = models.CharField(max_length=255, db_index=True)
    platform = models.CharField(max_length=50)  # 'facebook', 'twitter', 'instagram', 'threads', 'tiktok', 'linkedin', 'github', etc.
    platform_display_name = models.CharField(max_length=50)
    profile_url = models.URLField(max_length=500)
    username = models.CharField(max_length=150, blank=True)
    is_verified = models.BooleanField(default=True)
    source_method = models.CharField(max_length=100, default="verified_web")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.platform_display_name}: {self.profile_url} ({self.email_searched})"


