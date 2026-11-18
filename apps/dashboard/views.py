"""
Dashboard Views with Visual Analytics, Timeframes, and Live Telemetry.
Fulfills Part 10 (S-06), Decision D-22, and Phase 2 requirements.
"""
import json
import datetime
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from apps.email_verifier.models import EmailVerification
from apps.email_finder.models import FinderJob, DiscoveredEmail
from apps.bulk_processing.models import BulkJob
from apps.api_management.models import APIKey, UsageRecord
from core.utilities.constants import (
    STATUS_DELIVERABLE,
    STATUS_RISKY,
    STATUS_UNDELIVERABLE,
    STATUS_UNKNOWN,
)


@login_required
def dashboard_view(request):
    """
    S-06: Main Dashboard showing metrics, Chart.js telemetry, and active job statuses.
    """
    user = request.user
    timeframe = request.GET.get("timeframe", "all")
    now = timezone.now()

    ver_qs = EmailVerification.objects.filter(owner=user)
    finder_qs = FinderJob.objects.filter(owner=user)

    # Apply Timeframe Filter
    if timeframe == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        ver_qs = ver_qs.filter(verified_at__gte=start_date)
        finder_qs = finder_qs.filter(created_at__gte=start_date)
    elif timeframe == "7d":
        start_date = now - datetime.timedelta(days=7)
        ver_qs = ver_qs.filter(verified_at__gte=start_date)
        finder_qs = finder_qs.filter(created_at__gte=start_date)
    elif timeframe == "30d":
        start_date = now - datetime.timedelta(days=30)
        ver_qs = ver_qs.filter(verified_at__gte=start_date)
        finder_qs = finder_qs.filter(created_at__gte=start_date)

    # Verifications Breakdown
    total_verifications = ver_qs.count()
    deliverable_count = ver_qs.filter(status=STATUS_DELIVERABLE).count()
    risky_count = ver_qs.filter(status=STATUS_RISKY).count()
    undeliverable_count = ver_qs.filter(status=STATUS_UNDELIVERABLE).count()
    unknown_count = ver_qs.filter(status=STATUS_UNKNOWN).count()

    # Percentage Calculations
    def calc_pct(val, total):
        return round((val / total * 100), 1) if total > 0 else 0

    deliverable_pct = calc_pct(deliverable_count, total_verifications)
    risky_pct = calc_pct(risky_count, total_verifications)
    undeliverable_pct = calc_pct(undeliverable_count, total_verifications)
    unknown_pct = calc_pct(unknown_count, total_verifications)

    # Finder & Contact Metrics
    total_finder_jobs = finder_qs.count()
    total_discovered_emails = DiscoveredEmail.objects.filter(owner=user).count()

    # API Telemetry
    active_keys_count = APIKey.objects.filter(user=user, status="active").count()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    api_calls_today = UsageRecord.objects.filter(owner=user, occurred_at__gte=today_start).count()

    # Active Background Jobs Pulse
    active_bulk_job = BulkJob.objects.filter(owner=user, status__in=["queued", "running"]).first()
    active_finder_job = FinderJob.objects.filter(owner=user, status__in=["queued", "running"]).first()

    # Daily Verification Volume for Chart (Last 7 Days)
    daily_labels = []
    daily_deliverable = []
    daily_undeliverable = []
    daily_other = []

    for i in range(6, -1, -1):
        day_date = (now - datetime.timedelta(days=i)).date()
        day_label = day_date.strftime("%b %d")
        daily_labels.append(day_label)

        day_start = timezone.make_aware(datetime.datetime.combine(day_date, datetime.time.min))
        day_end = timezone.make_aware(datetime.datetime.combine(day_date, datetime.time.max))

        day_ver = EmailVerification.objects.filter(owner=user, verified_at__range=(day_start, day_end))
        daily_deliverable.append(day_ver.filter(status=STATUS_DELIVERABLE).count())
        daily_undeliverable.append(day_ver.filter(status=STATUS_UNDELIVERABLE).count())
        daily_other.append(day_ver.filter(status__in=[STATUS_RISKY, STATUS_UNKNOWN]).count())

    chart_data = {
        "labels": daily_labels,
        "deliverable": daily_deliverable,
        "undeliverable": daily_undeliverable,
        "other": daily_other,
        "distribution": [deliverable_count, risky_count, undeliverable_count, unknown_count],
    }

    # Recent activity
    recent_verifications = ver_qs.order_by("-verified_at")[:8]
    recent_finder_jobs = finder_qs.order_by("-created_at")[:6]

    context = {
        "timeframe": timeframe,
        "total_verifications": total_verifications,
        "deliverable_count": deliverable_count,
        "risky_count": risky_count,
        "undeliverable_count": undeliverable_count,
        "unknown_count": unknown_count,
        "deliverable_pct": deliverable_pct,
        "risky_pct": risky_pct,
        "undeliverable_pct": undeliverable_pct,
        "unknown_pct": unknown_pct,
        "total_finder_jobs": total_finder_jobs,
        "total_discovered_emails": total_discovered_emails,
        "active_keys_count": active_keys_count,
        "api_calls_today": api_calls_today,
        "active_bulk_job": active_bulk_job,
        "active_finder_job": active_finder_job,
        "recent_verifications": recent_verifications,
        "recent_finder_jobs": recent_finder_jobs,
        "chart_data_json": json.dumps(chart_data),
    }
    return render(request, "dashboard/dashboard.html", context)
