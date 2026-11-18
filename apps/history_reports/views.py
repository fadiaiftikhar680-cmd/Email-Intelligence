"""
Search History, Verification History, and Reports Views.
Fulfills Part 10 (S-14, S-15, S-16).
"""
import os
import mimetypes
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from apps.email_finder.models import FinderJob
from apps.email_verifier.models import EmailVerification
from apps.history_reports.models import ExportRecord
from apps.bulk_processing.services import generate_bulk_export
from core.storage.storage import get_full_storage_path


@login_required
def finder_history_view(request):
    """S-14: Search / Finder History."""
    jobs = FinderJob.objects.filter(owner=request.user)
    return render(request, "history/finder_history.html", {"jobs": jobs})


@login_required
def verification_history_view(request):
    """S-15: Verification History."""
    status_filter = request.GET.get("status")
    verifications = EmailVerification.objects.filter(owner=request.user)
    if status_filter:
        verifications = verifications.filter(status=status_filter)
    return render(request, "history/verification_history.html", {
        "verifications": verifications[:100],
        "status_filter": status_filter,
    })


@login_required
def reports_view(request):
    """S-16: Reports and Exports."""
    exports = ExportRecord.objects.filter(owner=request.user)
    return render(request, "reports/reports.html", {"exports": exports})


@login_required
def download_export_view(request, export_id):
    """Securely downloads an export file verifying owner authorization."""
    record = get_object_or_404(ExportRecord, id=export_id, owner=request.user)
    full_path = get_full_storage_path(record.file_ref)

    if not os.path.exists(full_path):
        raise Http404("Export file not found or expired.")

    content_type, _ = mimetypes.guess_type(full_path)
    with open(full_path, "rb") as f:
        response = HttpResponse(f.read(), content_type=content_type or "application/octet-stream")
        response["Content-Disposition"] = f'attachment; filename="export_{record.id}.{record.format}"'
        return response

