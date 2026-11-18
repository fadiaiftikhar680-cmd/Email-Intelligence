"""
Admin Dashboard and Operational Management Views.
Fulfills Part 10 (S-20), Part 8.8, and Decision D-12.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from apps.accounts.models import User
from apps.email_verifier.models import EmailVerification
from apps.email_finder.models import FinderJob
from apps.bulk_processing.models import BulkJob
from apps.admin_management.models import SuppressionEntry
from apps.audit.models import AuditLog, log_audit_event


def is_admin_user(user):
    return user.is_authenticated and (user.is_admin or user.is_staff)


@login_required
@user_passes_test(is_admin_user)
def admin_dashboard_view(request):
    """
    S-20: Admin Dashboard showing platform vitals, user management,
    suppression management, and break-glass audited access.
    """
    users = User.objects.all().order_by("-created_at")[:50]
    total_users = User.objects.count()
    active_jobs = BulkJob.objects.filter(status__in=["queued", "running"]).count() + \
                  FinderJob.objects.filter(status__in=["queued", "running"]).count()
    suppressions = SuppressionEntry.objects.all().order_by("-created_at")[:50]
    recent_audits = AuditLog.objects.all().order_by("-occurred_at")[:50]

    # Handle suppression additions
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_suppression":
            target = request.POST.get("target", "").strip().lower()
            reason = request.POST.get("reason", "").strip()
            if target:
                SuppressionEntry.objects.get_or_create(
                    email_or_domain=target,
                    defaults={"reason": reason, "created_by": request.user}
                )
                log_audit_event("suppression_added_by_admin", actor=request.user, target_type="suppression", target_id=target)
                messages.success(request, f"Suppressed '{target}'.")
        elif action == "delete_suppression":
            entry_id = request.POST.get("entry_id")
            SuppressionEntry.objects.filter(id=entry_id).delete()
            messages.info(request, "Suppression entry removed.")
        return redirect("admin_dashboard")

    return render(request, "admin/dashboard.html", {
        "users": users,
        "total_users": total_users,
        "active_jobs": active_jobs,
        "suppressions": suppressions,
        "recent_audits": recent_audits,
    })


@login_required
@user_passes_test(is_admin_user)
def break_glass_user_view(request, user_id):
    """
    Break-glass inspection of a user's records.
    Mandatory reason must be logged to AuditLog per Part 8.8 and Decision D-12.
    """
    target_user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        if not reason:
            messages.error(request, "You must provide an operational justification reason to view user records.")
            return redirect("admin_dashboard")

        # Record audited break-glass action
        log_audit_event(
            action="break_glass_user_inspection",
            actor=request.user,
            target_type="user",
            target_id=str(target_user.id),
            metadata={"justification_reason": reason, "target_email": target_user.email}
        )

        user_verifications = target_user.verifications.all()[:50]
        user_finders = target_user.finder_jobs.all()[:20]
        user_bulks = target_user.bulk_jobs.all()[:20]

        return render(request, "admin/break_glass.html", {
            "target_user": target_user,
            "justification_reason": reason,
            "verifications": user_verifications,
            "finder_jobs": user_finders,
            "bulk_jobs": user_bulks,
        })

    return redirect("admin_dashboard")

