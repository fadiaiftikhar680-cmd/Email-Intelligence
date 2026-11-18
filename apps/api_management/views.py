"""
API Management Web Views and Public API v1 Endpoints.
Fulfills Part 5, Part 10 (S-17, S-18), and Part 14 (Phase 9).
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, serializers
from drf_spectacular.utils import extend_schema, OpenApiResponse

from core.utilities.constants import (
    SCOPE_EMAIL_VERIFY,
    SCOPE_BULK_WRITE,
    SCOPE_FINDER_RUN,
    SCOPE_JOBS_READ,
    SCOPE_USAGE_READ,
    SCOPE_ACCOUNT_READ,
    ALL_API_SCOPES,
)
from core.security.api_keys import generate_api_key
from apps.api_management.models import APIKey, UsageRecord, APIRequestLog
from apps.api_management.authentication import APIKeyAuthentication, HasAPIScope
from apps.api_management.serializers import (
    SingleVerifyRequestSerializer,
    SingleVerifyResponseSerializer,
    BulkVerifyRequestSerializer,
    BulkVerifyResponseSerializer,
    CompanyFinderRequestSerializer,
    PersonFinderRequestSerializer,
    JobStatusResponseSerializer,
    UsageResponseSerializer,
    AccountSummaryResponseSerializer,
)
from apps.email_verifier.services import verify_single_email
from apps.bulk_processing.models import BulkJob
from apps.bulk_processing.services import create_bulk_job_from_file, process_bulk_job
from apps.email_finder.models import FinderJob
from apps.email_finder.services import run_company_finder_job, run_person_finder_job
from apps.audit.models import log_audit_event


# Inline helper serializers for OpenAPI doc completion
class JobResultsResponseSerializer(serializers.Serializer):
    job_id = serializers.UUIDField()
    results = serializers.ListField(child=serializers.DictField())

class GenericStatusResponseSerializer(serializers.Serializer):
    status = serializers.CharField()


# ========================================================
# UI Views (S-17 & S-18)
# ========================================================

@login_required
def api_keys_view(request):
    """S-17: API Key Management UI."""
    new_key_raw = None
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_key":
            name = request.POST.get("name", "").strip() or "Default Key"
            selected_scopes = request.POST.getlist("scopes") or ALL_API_SCOPES

            full_key, prefix, key_hash = generate_api_key()
            APIKey.objects.create(
                user=request.user,
                name=name,
                prefix=prefix,
                key_hash=key_hash,
                scopes=selected_scopes,
                status="active"
            )
            new_key_raw = full_key
            log_audit_event("api_key_created", actor=request.user, target_type="api_key", target_id=prefix)
            messages.success(request, "API Key created successfully. Please copy it now as it will not be shown again.")
        elif action == "revoke_key":
            key_id = request.POST.get("key_id")
            key_obj = get_object_or_404(APIKey, id=key_id, user=request.user)
            key_obj.status = "revoked"
            key_obj.revoked_at = timezone.now()
            key_obj.save()
            log_audit_event("api_key_revoked", actor=request.user, target_type="api_key", target_id=key_obj.prefix)
            messages.info(request, f"Key '{key_obj.name}' has been revoked.")

    keys = APIKey.objects.filter(user=request.user)
    request_logs = APIRequestLog.objects.filter(api_key__user=request.user)[:20]

    return render(request, "api/keys.html", {
        "keys": keys,
        "new_key_raw": new_key_raw,
        "request_logs": request_logs,
        "all_scopes": ALL_API_SCOPES,
    })


def api_docs_view(request):
    """S-18: API Documentation Page."""
    return render(request, "api/docs.html")


# ========================================================
# Public API v1 Endpoints (Part 5.3)
# ========================================================

class SingleVerifyAPIView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIScope(SCOPE_EMAIL_VERIFY)]

    @extend_schema(
        request=SingleVerifyRequestSerializer,
        responses={200: SingleVerifyResponseSerializer},
        summary="Verify single email address",
        description="Synchronous deliverability signals check. Returns Deliverable, Undeliverable, Risky, or Unknown."
    )
    def post(self, request):
        serializer = SingleVerifyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_email = serializer.validated_data["email"]
        ver = verify_single_email(
            raw_email=target_email,
            owner=request.user,
            allow_smtp_probe=True,
            api_key=getattr(request, "auth", None)
        )

        resp_data = {
            "email": ver.email_normalized,
            "status": ver.status,
            "reason_codes": ver.reason_codes,
            "evidence": ver.evidence_json,
            "is_role_based": ver.evidence_json.get("is_role_based", False),
            "is_disposable": ver.evidence_json.get("is_disposable", False),
            "verified_at": ver.verified_at,
        }
        return Response(resp_data, status=status.HTTP_200_OK)


class BulkVerifyAPIView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIScope(SCOPE_BULK_WRITE)]

    @extend_schema(
        request=BulkVerifyRequestSerializer,
        responses={202: BulkVerifyResponseSerializer},
        summary="Create bulk verification job",
        description="Asynchronous bulk verification. Accepts list of emails or CSV/XLSX file upload."
    )
    def post(self, request):
        file_obj = request.FILES.get("file")
        emails_list = request.data.get("emails")

        if file_obj:
            bulk_job = create_bulk_job_from_file(
                file_obj=file_obj,
                filename=file_obj.name,
                owner=request.user,
                email_column=request.data.get("email_column", "")
            )
        elif emails_list and isinstance(emails_list, list):
            import io
            csv_io = io.StringIO()
            csv_io.write("email\n")
            for em in emails_list:
                csv_io.write(f"{em}\n")
            bytes_io = io.BytesIO(csv_io.getvalue().encode("utf-8"))
            bytes_io.size = len(bytes_io.getvalue())
            bytes_io.name = "api_bulk_list.csv"
            bulk_job = create_bulk_job_from_file(
                file_obj=bytes_io,
                filename="api_bulk_list.csv",
                owner=request.user
            )
        else:
            return Response({"detail": "Provide 'emails' array or a 'file' upload."}, status=status.HTTP_400_BAD_REQUEST)

        process_bulk_job(str(bulk_job.id))

        return Response({
            "job_id": bulk_job.id,
            "status": bulk_job.status,
            "total_rows": bulk_job.total_rows,
        }, status=status.HTTP_202_ACCEPTED)


class JobStatusAPIView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIScope(SCOPE_JOBS_READ)]

    @extend_schema(
        responses={200: JobStatusResponseSerializer},
        summary="Get status of a job"
    )
    def get(self, request, job_id):
        b_job = BulkJob.objects.filter(id=job_id, owner=request.user).first()
        if b_job:
            return Response({
                "job_id": b_job.id,
                "kind": "bulk_verify",
                "status": b_job.status,
                "progress_counts": b_job.progress_counts,
                "result_count": b_job.valid_rows,
                "error_code": "",
                "created_at": b_job.created_at,
                "finished_at": b_job.finished_at,
            })

        f_job = FinderJob.objects.filter(id=job_id, owner=request.user).first()
        if f_job:
            return Response({
                "job_id": f_job.id,
                "kind": f_job.kind,
                "status": f_job.status,
                "result_count": f_job.result_count,
                "error_code": f_job.error_code,
                "created_at": f_job.created_at,
                "finished_at": f_job.finished_at,
            })

        return Response({"detail": "Job not found."}, status=status.HTTP_404_NOT_FOUND)


class JobResultsAPIView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIScope(SCOPE_JOBS_READ)]

    @extend_schema(
        responses={200: JobResultsResponseSerializer},
        summary="Get paginated results of a job"
    )
    def get(self, request, job_id):
        b_job = BulkJob.objects.filter(id=job_id, owner=request.user).first()
        if b_job:
            records = b_job.records.select_related("verification")[:100]
            items = []
            for r in records:
                items.append({
                    "row": r.row_number,
                    "email": r.email_normalized,
                    "state": r.state,
                    "status": r.verification.status if r.verification else None,
                    "reason_codes": r.verification.reason_codes if r.verification else [],
                })
            return Response({"job_id": b_job.id, "total": b_job.total_rows, "results": items})

        f_job = FinderJob.objects.filter(id=job_id, owner=request.user).first()
        if f_job:
            emails = f_job.discovered_emails.all()
            items = []
            for em in emails:
                items.append({
                    "email": em.email_normalized,
                    "origin": em.origin,
                    "method": em.method,
                    "category": em.category,
                    "evidence_level": em.evidence_level,
                })
            return Response({"job_id": f_job.id, "result_count": f_job.result_count, "results": items})

        return Response({"detail": "Job not found."}, status=status.HTTP_404_NOT_FOUND)


class JobCancelAPIView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIScope(SCOPE_BULK_WRITE)]

    @extend_schema(
        request=None,
        responses={200: GenericStatusResponseSerializer},
        summary="Cancel an active job"
    )
    def post(self, request, job_id):
        job = BulkJob.objects.filter(id=job_id, owner=request.user).first() or \
              FinderJob.objects.filter(id=job_id, owner=request.user).first()
        if not job:
            return Response({"detail": "Job not found."}, status=status.HTTP_404_NOT_FOUND)

        job.status = "cancelled"
        job.save()
        return Response({"status": "cancelled"})


class CompanyFinderAPIView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIScope(SCOPE_FINDER_RUN)]

    @extend_schema(
        request=CompanyFinderRequestSerializer,
        responses={202: GenericStatusResponseSerializer},
        summary="Start company email finder job"
    )
    def post(self, request):
        serializer = CompanyFinderRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_url = serializer.validated_data["url"]
        auto_verify = serializer.validated_data.get("verify", True)

        job = FinderJob.objects.create(
            owner=request.user,
            kind="company",
            input_json={"url": target_url, "verify": auto_verify}
        )
        run_company_finder_job(str(job.id))

        return Response({"job_id": job.id, "status": job.status}, status=status.HTTP_202_ACCEPTED)


class PersonFinderAPIView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIScope(SCOPE_FINDER_RUN)]

    @extend_schema(
        request=PersonFinderRequestSerializer,
        responses={202: GenericStatusResponseSerializer},
        summary="Start person finder job"
    )
    def post(self, request):
        serializer = PersonFinderRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        job = FinderJob.objects.create(
            owner=request.user,
            kind="person",
            input_json=serializer.validated_data
        )
        run_person_finder_job(str(job.id))

        return Response({"job_id": job.id, "status": job.status}, status=status.HTTP_202_ACCEPTED)


class UsageAPIView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIScope(SCOPE_USAGE_READ)]

    @extend_schema(
        responses={200: UsageResponseSerializer},
        summary="Get account usage metrics"
    )
    def get(self, request):
        total_ver = UsageRecord.objects.filter(owner=request.user, kind__startswith="verify").count()
        total_find = UsageRecord.objects.filter(owner=request.user, kind__startswith="finder").count()
        recent = UsageRecord.objects.filter(owner=request.user)[:10].values("kind", "quantity", "occurred_at")

        return Response({
            "owner_email": request.user.email,
            "total_verifications": total_ver,
            "total_finder_runs": total_find,
            "recent_usage": list(recent)
        })


class AccountSummaryAPIView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIScope(SCOPE_ACCOUNT_READ)]

    @extend_schema(
        responses={200: AccountSummaryResponseSerializer},
        summary="Get account profile summary"
    )
    def get(self, request):
        user = request.user
        return Response({
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "retention_days": user.profile.retention_days,
            "created_at": user.created_at,
        })
