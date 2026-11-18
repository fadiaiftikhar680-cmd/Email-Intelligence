"""
DomainRecord and EmailVerification Models.
Fulfills Part 4 (4.1 DomainRecord, EmailVerification) and Part 6.6.
"""
import uuid
from django.db import models
from django.conf import settings
from core.utilities.constants import (
    VERIFICATION_STATUSES,
    STATUS_UNKNOWN,
)


class DomainRecord(models.Model):
    id = models.BigAutoField(primary_key=True)
    domain = models.CharField(max_length=255, unique=True, db_index=True)
    has_mx = models.BooleanField(default=False)
    mx_hosts = models.JSONField(default=list)
    has_address_fallback = models.BooleanField(default=False)
    is_disposable = models.BooleanField(default=False)
    is_free_provider = models.BooleanField(default=False)
    catch_all_state = models.CharField(max_length=20, default="unknown")  # 'yes', 'no', 'unknown'
    checked_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"{self.domain} (MX={self.has_mx}, CatchAll={self.catch_all_state})"


class EmailVerification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="verifications")
    email_normalized = models.CharField(max_length=255, db_index=True)
    status = models.CharField(max_length=30, choices=VERIFICATION_STATUSES, default=STATUS_UNKNOWN)
    reason_codes = models.JSONField(default=list)
    evidence_json = models.JSONField(default=dict)
    domain_record = models.ForeignKey(DomainRecord, null=True, blank=True, on_delete=models.SET_NULL, related_name="verifications")
    bulk_record_id = models.UUIDField(null=True, blank=True)
    discovered_email_id = models.UUIDField(null=True, blank=True)
    verified_at = models.DateTimeField(auto_now_add=True, db_index=True)
    engine_version = models.CharField(max_length=20, default="1.0.0")

    class Meta:
        ordering = ["-verified_at"]

    def __str__(self):
        return f"{self.email_normalized} - {self.status}"

    @property
    def local_part(self):
        if "@" in self.email_normalized:
            return self.email_normalized.split("@", 1)[0]
        return self.email_normalized

    @property
    def domain(self):
        if "@" in self.email_normalized:
            return self.email_normalized.split("@", 1)[1]
        return ""

