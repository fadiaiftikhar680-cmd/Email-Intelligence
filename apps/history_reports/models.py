"""
ExportRecord Model for CSV/XLSX export history and file expiration.
Fulfills Part 4 (4.1 ExportRecord) and Part 10 (S-16).
"""
import uuid
from django.db import models
from django.conf import settings


class ExportRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="export_records")
    source_type = models.CharField(max_length=50)  # 'bulk_job', 'finder_job', 'verification_history'
    source_id = models.CharField(max_length=100)
    format = models.CharField(max_length=10)  # 'csv', 'xlsx'
    file_ref = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Export ({self.format}) for {self.source_type} {self.source_id}"

