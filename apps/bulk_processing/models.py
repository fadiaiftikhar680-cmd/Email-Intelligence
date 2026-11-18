"""
BulkJob, BulkChunk, and BulkRecord Models.
Fulfills Part 4 (4.1 BulkJob, BulkChunk, BulkRecord) and Part 11.6.
"""
import uuid
from django.db import models
from django.conf import settings
from core.utilities.constants import (
    JOB_STATUS_CHOICES,
    JOB_STATUS_QUEUED,
)


class BulkJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bulk_jobs")
    filename = models.CharField(max_length=255)
    file_ref = models.CharField(max_length=255)
    email_column = models.CharField(max_length=100, blank=True)
    total_rows = models.IntegerField(default=0)
    valid_rows = models.IntegerField(default=0)
    duplicate_rows = models.IntegerField(default=0)
    invalid_rows = models.IntegerField(default=0)
    status = models.CharField(max_length=30, choices=JOB_STATUS_CHOICES, default=JOB_STATUS_QUEUED)
    progress_counts = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"BulkJob {self.id} ({self.filename}) - {self.status}"


class BulkChunk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bulk_job = models.ForeignKey(BulkJob, on_delete=models.CASCADE, related_name="chunks")
    seq = models.IntegerField()
    status = models.CharField(max_length=30, default=JOB_STATUS_QUEUED)
    attempts = models.IntegerField(default=0)
    last_error_code = models.CharField(max_length=50, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("bulk_job", "seq")
        ordering = ["seq"]


class BulkRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bulk_job = models.ForeignKey(BulkJob, on_delete=models.CASCADE, related_name="records")
    row_number = models.IntegerField()
    raw_value = models.TextField(blank=True)
    email_normalized = models.CharField(max_length=255, blank=True, db_index=True)
    state = models.CharField(max_length=30, default="pending")  # 'pending', 'verified', 'invalid', 'duplicate'
    verification = models.ForeignKey(
        "email_verifier.EmailVerification",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bulk_records"
    )

    class Meta:
        unique_together = ("bulk_job", "row_number")
        ordering = ["row_number"]

