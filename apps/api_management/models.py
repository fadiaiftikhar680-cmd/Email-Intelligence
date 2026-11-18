"""
API Key, UsageRecord, and APIRequestLog Models.
Fulfills Part 4 (4.1 APIKey, UsageRecord, APIRequestLog) and Part 5.2.
"""
import uuid
from django.db import models
from django.conf import settings
from core.utilities.constants import ALL_API_SCOPES


class APIKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=32, unique=True, db_index=True)
    key_hash = models.CharField(max_length=128)
    scopes = models.JSONField(default=list)
    status = models.CharField(max_length=20, default="active", db_index=True)  # 'active', 'revoked'
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.prefix}...)"

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def has_scope(self, scope: str) -> bool:
        return self.is_active and (scope in self.scopes or "all" in self.scopes)


class UsageRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="usage_records")
    api_key = models.ForeignKey(APIKey, null=True, blank=True, on_delete=models.SET_NULL, related_name="usages")
    kind = models.CharField(max_length=50)  # 'verify_single', 'verify_bulk', 'finder_company', 'finder_person'
    quantity = models.IntegerField(default=1)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-occurred_at"]


class APIRequestLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    api_key = models.ForeignKey(APIKey, on_delete=models.CASCADE, related_name="request_logs")
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=255)
    status_code = models.IntegerField()
    duration_ms = models.IntegerField()
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-occurred_at"]

