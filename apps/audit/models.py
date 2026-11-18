"""
AuditLog Model for append-only security and administrative audit trail.
Fulfills Part 4 (4.1 AuditLog) and Part 8.8.
"""
import uuid
from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_actions"
    )
    action = models.CharField(max_length=100, db_index=True)
    target_type = models.CharField(max_length=50, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-occurred_at"]

    def __str__(self):
        return f"[{self.occurred_at}] {self.action} by {self.actor or 'System'}"


def log_audit_event(
    action: str,
    actor=None,
    target_type: str = "",
    target_id: str = "",
    ip_address: str | None = None,
    metadata: dict | None = None
) -> AuditLog:
    """Helper function to create an immutable audit log record."""
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id else "",
        ip_address=ip_address,
        metadata_json=metadata or {}
    )

