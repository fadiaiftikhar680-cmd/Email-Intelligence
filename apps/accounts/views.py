"""
Accounts and Authentication Views.
Fulfills Part 10 (S-01, S-02, S-03, S-04, S-05, S-19, S-21, S-22).
"""
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from apps.accounts.models import User, UserProfile
from apps.audit.models import log_audit_event
from apps.admin_management.models import SuppressionEntry


def landing_view(request):
    """S-01: Direct Access -> Redirects to Dashboard without login."""
    return redirect("dashboard")


def register_view(request):
    """Direct Access -> Sign-in / registration removed, redirects to Dashboard."""
    return redirect("dashboard")


def login_view(request):
    """Direct Access -> Sign-in / login removed, redirects to Dashboard."""
    return redirect("dashboard")


def logout_view(request):
    """Direct Access -> Redirects to Dashboard."""
    return redirect("dashboard")


def verify_email_view(request, token=None):
    """S-03: Email verification confirmation."""
    if token:
        user = User.objects.filter(verification_token=token).first()
        if user:
            user.email_verified_at = timezone.now()
            user.verification_token = None
            user.save()
            messages.success(request, "Your email has been verified successfully!")
            return redirect("login")
        else:
            messages.error(request, "Invalid or expired verification token.")
    return render(request, "accounts/verify_email.html")


def forgot_password_view(request):
    """S-05: Forgot password."""
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        user = User.objects.filter(email=email).first()
        if user:
            token = uuid.uuid4().hex
            user.reset_token = token
            user.reset_token_expires_at = timezone.now() + timezone.timedelta(hours=2)
            user.save()
            messages.info(request, f"Password reset instructions generated. Reset token: {token}")
        else:
            messages.info(request, "If that email is registered, password reset instructions have been sent.")
    return render(request, "accounts/forgot_password.html")


def reset_password_view(request, token):
    """S-05: Reset password with token."""
    user = get_object_or_404(User, reset_token=token)
    if user.reset_token_expires_at and user.reset_token_expires_at < timezone.now():
        messages.error(request, "Reset token has expired.")
        return redirect("forgot_password")

    if request.method == "POST":
        p1 = request.POST.get("password", "")
        p2 = request.POST.get("password_confirm", "")
        if len(p1) < 12:
            messages.error(request, "Password must be at least 12 characters long.")
            return render(request, "accounts/reset_password.html")
        if p1 != p2:
            messages.error(request, "Passwords do not match.")
            return render(request, "accounts/reset_password.html")

        user.set_password(p1)
        user.reset_token = None
        user.reset_token_expires_at = None
        user.save()
        messages.success(request, "Your password has been reset successfully. Please log in.")
        return redirect("login")

    return render(request, "accounts/reset_password.html")


@login_required
def profile_settings_view(request):
    """S-19: Profile and Settings."""
    profile = request.user.profile
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update_profile":
            profile.display_name = request.POST.get("display_name", "").strip()
            profile.timezone = request.POST.get("timezone", "UTC").strip()
            try:
                ret = int(request.POST.get("retention_days", 90))
                if 7 <= ret <= 365:
                    profile.retention_days = ret
            except ValueError:
                pass
            profile.save()
            messages.success(request, "Profile settings updated.")
        elif action == "change_password":
            old_p = request.POST.get("old_password", "")
            new_p = request.POST.get("new_password", "")
            if not request.user.check_password(old_p):
                messages.error(request, "Current password is incorrect.")
            elif len(new_p) < 12:
                messages.error(request, "New password must be at least 12 characters long.")
            else:
                request.user.set_password(new_p)
                request.user.save()
                login(request, request.user)
                messages.success(request, "Password changed successfully.")
        return redirect("settings")

    return render(request, "accounts/settings.html", {"profile": profile})


@login_required
def delete_account_view(request):
    """S-19: Account deletion with full cascade per Part 4.6."""
    if request.method == "POST":
        confirm_text = request.POST.get("confirm_email", "").strip().lower()
        if confirm_text == request.user.email.lower():
            user = request.user
            user_id = str(user.id)
            user_email = user.email
            logout(request)
            # Full cascade delete
            user.delete()
            log_audit_event("account_deleted", target_type="user", target_id=user_id, metadata={"email": user_email})
            messages.success(request, "Your account and associated data have been permanently deleted.")
            return redirect("landing")
        else:
            messages.error(request, "Confirmation email did not match. Account was not deleted.")
            return redirect("settings")
    return redirect("settings")


def terms_view(request):
    """S-21: Terms of Service."""
    return render(request, "legal/terms.html")


def privacy_view(request):
    """S-21: Privacy Policy."""
    return render(request, "legal/privacy.html")


def acceptable_use_view(request):
    """S-21: Acceptable Use Policy."""
    return render(request, "legal/acceptable_use.html")


def opt_out_view(request):
    """S-22: Opt-out / Suppression Request."""
    if request.method == "POST":
        target = request.POST.get("target", "").strip().lower()
        reason = request.POST.get("reason", "").strip()
        if target and ("@" in target or "." in target):
            SuppressionEntry.objects.get_or_create(
                email_or_domain=target,
                defaults={"reason": reason or "User requested opt-out"}
            )
            messages.success(request, f"Target '{target}' has been successfully added to our suppression list.")
        else:
            messages.error(request, "Please enter a valid email address or domain name.")
    return render(request, "legal/opt_out.html")

