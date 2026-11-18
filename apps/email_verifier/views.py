"""
Single and Bulk Email Verifier Views.
Fulfills Part 10 (S-09 and S-10).
Supports up to 30 simultaneous email verifications in a single operation.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.email_verifier.services import (
    verify_single_email,
    verify_multiple_emails_concurrently,
    extract_emails_from_text,
)
from apps.bulk_processing.services import create_bulk_job_from_file, process_bulk_job
from apps.bulk_processing.models import BulkJob


@login_required
def single_verifier_view(request):
    """
    S-09: Single & Simultaneous Multi-Email Verifier (up to 30 emails).
    - If user submits 1–30 emails: verifies all emails together at the same time.
    - If user submits > 30 emails: automatically activates the existing Batch Processing option.
    """
    result = None
    results = []
    input_email = ""

    if request.method == "POST":
        raw_input = request.POST.get("email", "").strip()
        input_email = raw_input
        extracted = extract_emails_from_text(raw_input)

        # Fallback if raw text given without '@' to allow syntax validation failure testing
        if not extracted and raw_input:
            extracted = [raw_input]

        if not extracted:
            messages.error(request, "Please enter at least one email address to verify.")
        elif len(extracted) > 30:
            # Over 30 emails: automatically activate the existing Batch Processing option
            messages.info(
                request,
                f"You entered {len(extracted)} emails. Direct verification processes up to 30 emails simultaneously. "
                f"The existing Batch Processing option has been automatically activated for your list."
            )
            return redirect("bulk_verifier")
        elif len(extracted) == 1:
            result = verify_single_email(
                raw_email=extracted[0],
                owner=request.user,
                allow_smtp_probe=True
            )
            results = [result]
        else:
            # Verify 2 to 30 emails together simultaneously
            results = verify_multiple_emails_concurrently(
                emails=extracted,
                owner=request.user,
                allow_smtp_probe=True
            )

    return render(request, "verifier/single.html", {
        "result": result,
        "results": results,
        "input_email": input_email,
        "results_count": len(results),
    })


@login_required
def bulk_verifier_view(request):
    """S-10: Bulk Email Verifier (Existing Batch Processing Option)."""
    if request.method == "POST":
        uploaded_file = request.FILES.get("file")
        email_column = request.POST.get("email_column", "").strip()

        if not uploaded_file:
            messages.error(request, "Please select a .csv or .xlsx file to upload.")
            return redirect("bulk_verifier")

        try:
            bulk_job = create_bulk_job_from_file(
                file_obj=uploaded_file,
                filename=uploaded_file.name,
                owner=request.user,
                email_column=email_column
            )
            # Process synchronously or via background task
            process_bulk_job(str(bulk_job.id))
            messages.success(request, f"Bulk verification completed for {bulk_job.total_rows} rows!")
            return redirect("bulk_job_detail", job_id=bulk_job.id)
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"Processing error: {str(e)}")

    user_bulk_jobs = BulkJob.objects.filter(owner=request.user)[:10]
    return render(request, "verifier/bulk.html", {
        "recent_bulk_jobs": user_bulk_jobs,
    })


@login_required
def bulk_job_detail_view(request, job_id):
    """S-10: Bulk Job Detail & Progress."""
    job = get_object_or_404(BulkJob, id=job_id, owner=request.user)
    records = job.records.select_related("verification")[:100]
    return render(request, "verifier/bulk_detail.html", {
        "job": job,
        "records": records,
    })
