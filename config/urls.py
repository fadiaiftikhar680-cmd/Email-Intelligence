"""
Master URL Configuration for Email Intelligence Platform.
Fulfills Part 5, Part 10 (S-01 to S-23), and Part 3.9.
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

import apps.accounts.views as accounts_views
import apps.dashboard.views as dashboard_views
import apps.email_verifier.views as verifier_views
import apps.email_finder.views as finder_views
import apps.intelligence.views as intelligence_views
import apps.history_reports.views as history_views
import apps.api_management.views as api_views
import apps.admin_management.views as admin_views

handler400 = "apps.accounts.error_views.handler400"
handler403 = "apps.accounts.error_views.handler403"
handler404 = "apps.accounts.error_views.handler404"
handler500 = "apps.accounts.error_views.handler500"

urlpatterns = [
    # Django Admin
    path("django-admin/", admin.site.urls),

    # Public Auth & Marketing Screens (Part 10: S-01, S-02, S-03, S-04, S-05, S-21, S-22)
    path("", accounts_views.landing_view, name="landing"),
    path("register/", accounts_views.register_view, name="register"),
    path("login/", accounts_views.login_view, name="login"),
    path("logout/", accounts_views.logout_view, name="logout"),
    path("verify-email/", accounts_views.verify_email_view, name="verify_email_notice"),
    path("verify-email/<str:token>/", accounts_views.verify_email_view, name="verify_email_token"),
    path("forgot-password/", accounts_views.forgot_password_view, name="forgot_password"),
    path("reset-password/<str:token>/", accounts_views.reset_password_view, name="reset_password"),
    path("terms/", accounts_views.terms_view, name="terms"),
    path("privacy/", accounts_views.privacy_view, name="privacy"),
    path("acceptable-use/", accounts_views.acceptable_use_view, name="acceptable_use"),
    path("opt-out/", accounts_views.opt_out_view, name="opt_out"),

    # Authenticated User Screens
    path("dashboard/", dashboard_views.dashboard_view, name="dashboard"),  # S-06
    path("verifier/single/", verifier_views.single_verifier_view, name="single_verifier"),  # S-09
    path("verifier/bulk/", verifier_views.bulk_verifier_view, name="bulk_verifier"),  # S-10
    path("verifier/bulk/<uuid:job_id>/", verifier_views.bulk_job_detail_view, name="bulk_job_detail"),

    path("finder/company/", finder_views.company_finder_view, name="company_finder"),  # S-07
    path("finder/person/", finder_views.person_finder_view, name="person_finder"),  # S-08
    path("finder/social/", finder_views.social_finder_view, name="social_finder"),  # Social Media Finder
    path("finder/combined/", finder_views.combined_finder_view, name="combined_finder"),  # S-11
    path("finder/jobs/<uuid:job_id>/", finder_views.finder_job_detail_view, name="finder_job_detail"),
    path("finder/batch/<uuid:batch_id>/", finder_views.finder_batch_detail_view, name="finder_batch_detail"),
    path("finder/batch/<uuid:batch_id>/export/", finder_views.finder_batch_export_view, name="finder_batch_export"),

    path("intelligence/", intelligence_views.intelligence_directory_view, name="intelligence_directory"),
    path("intelligence/company/<uuid:company_id>/", intelligence_views.company_intelligence_view, name="company_intelligence"),  # S-12
    path("intelligence/person/<uuid:person_id>/", intelligence_views.person_intelligence_view, name="person_intelligence"),  # S-13

    path("history/finder/", history_views.finder_history_view, name="finder_history"),  # S-14
    path("history/verifications/", history_views.verification_history_view, name="verification_history"),  # S-15
    path("reports/", history_views.reports_view, name="reports"),  # S-16
    path("reports/download/<uuid:export_id>/", history_views.download_export_view, name="download_export"),

    path("api-keys/", api_views.api_keys_view, name="api_keys"),  # S-17
    path("api-docs/", api_views.api_docs_view, name="api_docs"),  # S-18
    path("settings/", accounts_views.profile_settings_view, name="settings"),  # S-19
    path("settings/delete-account/", accounts_views.delete_account_view, name="delete_account"),

    # Admin Portal (S-20)
    path("admin-portal/", admin_views.admin_dashboard_view, name="admin_dashboard"),
    path("admin-portal/break-glass/<uuid:user_id>/", admin_views.break_glass_user_view, name="break_glass_user"),

    # Public REST API v1 (Part 5)
    path("api/v1/email/verify", api_views.SingleVerifyAPIView.as_view(), name="api_verify_single"),
    path("api/v1/email/verify/bulk", api_views.BulkVerifyAPIView.as_view(), name="api_verify_bulk"),
    path("api/v1/jobs/<uuid:job_id>", api_views.JobStatusAPIView.as_view(), name="api_job_status"),
    path("api/v1/jobs/<uuid:job_id>/results", api_views.JobResultsAPIView.as_view(), name="api_job_results"),
    path("api/v1/jobs/<uuid:job_id>/cancel", api_views.JobCancelAPIView.as_view(), name="api_job_cancel"),
    path("api/v1/finder/company", api_views.CompanyFinderAPIView.as_view(), name="api_finder_company"),
    path("api/v1/finder/person", api_views.PersonFinderAPIView.as_view(), name="api_finder_person"),
    path("api/v1/finder/jobs/<uuid:job_id>", api_views.JobStatusAPIView.as_view(), name="api_finder_job_status"),
    path("api/v1/usage", api_views.UsageAPIView.as_view(), name="api_usage"),
    path("api/v1/account", api_views.AccountSummaryAPIView.as_view(), name="api_account"),

    # OpenAPI Schema & Swagger
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])

