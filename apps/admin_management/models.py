"""
SuppressionEntry Model for opt-outs and suppression lists.
Fulfills Part 4 (4.1 SuppressionEntry) and Part 8.7.
"""
from django.db import models
from django.conf import settings


class SuppressionEntry(models.Model):
    id = models.BigAutoField(primary_key=True)
    email_or_domain = models.CharField(max_length=255, unique=True, db_index=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="suppressions"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email_or_domain


def is_suppressed_target(email_or_domain: str) -> bool:
    """Checks whether an email or domain has been suppressed/opted-out."""
    if not email_or_domain:
        return False
    val = email_or_domain.strip().lower()
    if SuppressionEntry.objects.filter(email_or_domain=val).exists():
        return True
    if "@" in val:
        domain = val.split("@")[-1]
        if SuppressionEntry.objects.filter(email_or_domain=domain).exists():
            return True
    return False

