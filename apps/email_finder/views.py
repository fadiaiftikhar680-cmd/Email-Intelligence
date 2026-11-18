"""
Email Finder Views (Company Finder, Person Finder, Combined Finder & Verifier).
Fulfills Part 10 (S-07, S-08, S-11), Multi-URL Discovery (1–20 URLs), and Bulk File Upload.
"""
import csv
import io
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from core.utilities.normalization import neutralize_formula_injection
from apps.email_finder.models import FinderJob, DiscoveredEmail, Company, Person, SocialAccount
from apps.email_finder.services import (
    run_company_finder_job,
    run_person_finder_job,
    extract_urls_from_text,
    extract_urls_from_file,
    create_and_run_company_batch,
    run_social_finder_search,
)


@login_required
def company_finder_view(request):
    """
    S-07: Company Email Finder.
    Supports:
    1. Direct multi-URL input (1 to 20 URLs).
    2. Bulk file upload (.csv, .xlsx, .txt) for 20+ company URLs.
    """
    if request.method == "POST":
        source = request.POST.get("source", "direct")
        auto_verify = request.POST.get("verify") == "on"

        if source == "file":
            uploaded_file = request.FILES.get("file")
            if not uploaded_file:
                messages.error(request, "Please select a .txt, .csv, or .xlsx file to upload.")
                return redirect("company_finder")
            try:
                urls = extract_urls_from_file(uploaded_file, uploaded_file.name)
            except Exception as e:
                messages.error(request, f"File parsing error: {str(e)}")
                return redirect("company_finder")

            if not urls:
                messages.error(request, "No valid company URLs found in the uploaded file.")
                return redirect("company_finder")

            batch_id, jobs = create_and_run_company_batch(
                urls=urls,
                owner=request.user,
                auto_verify=auto_verify,
                batch_name=uploaded_file.name
            )
            messages.success(request, f"Bulk discovery completed! Processed {len(jobs)} company websites from {uploaded_file.name}.")
            return redirect("finder_batch_detail", batch_id=batch_id)

        else:
            # Direct text input: single or up to 20 URLs
            raw_text = request.POST.get("urls") or request.POST.get("url", "")
            urls = extract_urls_from_text(raw_text)

            if not urls:
                messages.error(request, "Please enter at least one valid company website URL.")
                return redirect("company_finder")

            if len(urls) > 20:
                messages.warning(
                    request,
                    f"You entered {len(urls)} URLs. Direct input processes up to 20 URLs at a time. The first 20 were processed. For 20+ URLs, please use the Bulk File Upload option below."
                )
                urls = urls[:20]

            if len(urls) == 1:
                job = FinderJob.objects.create(
                    owner=request.user,
                    kind="company",
                    input_json={"url": urls[0], "verify": auto_verify}
                )
                run_company_finder_job(str(job.id))
                return redirect("finder_job_detail", job_id=job.id)
            else:
                batch_id, jobs = create_and_run_company_batch(
                    urls=urls,
                    owner=request.user,
                    auto_verify=auto_verify,
                    batch_name=f"Batch of {len(urls)} Companies"
                )
                messages.success(request, f"Successfully processed {len(jobs)} company websites.")
                return redirect("finder_batch_detail", batch_id=batch_id)

    recent_jobs = FinderJob.objects.filter(owner=request.user, kind="company")[:10]
    return render(request, "finder/company.html", {
        "recent_jobs": recent_jobs,
    })


@login_required
def finder_batch_detail_view(request, batch_id):
    """View aggregated results of a multi-URL company discovery batch."""
    jobs = list(FinderJob.objects.filter(
        owner=request.user,
        kind="company",
        input_json__batch_id=str(batch_id)
    ).prefetch_related("discovered_emails", "visited_pages"))

    if not jobs:
        job = FinderJob.objects.filter(owner=request.user, id=batch_id).first()
        if job:
            return redirect("finder_job_detail", job_id=job.id)
        raise Http404("Discovery batch not found.")

    batch_name = jobs[0].batch_name or f"Batch of {len(jobs)} Companies"
    total_companies = len(jobs)
    all_discovered = DiscoveredEmail.objects.filter(job__in=jobs).select_related("company", "job")
    total_emails = all_discovered.count()
    completed_count = sum(1 for j in jobs if j.status == "completed")

    return render(request, "finder/batch_detail.html", {
        "batch_id": batch_id,
        "batch_name": batch_name,
        "jobs": jobs,
        "total_companies": total_companies,
        "total_emails": total_emails,
        "completed_count": completed_count,
        "discovered_emails": all_discovered[:200],
    })


@login_required
def finder_batch_export_view(request, batch_id):
    """Exports all discovered emails for a batch as a clean CSV."""
    jobs = FinderJob.objects.filter(
        owner=request.user,
        kind="company",
        input_json__batch_id=str(batch_id)
    )
    if not jobs.exists():
        raise Http404("Batch not found.")

    discovered_emails = DiscoveredEmail.objects.filter(job__in=jobs).select_related("company", "job")

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="company_batch_{str(batch_id)[:8]}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Company Name",
        "Company Domain",
        "Target URL",
        "Discovered Email",
        "Deliverability Status",
        "Origin",
        "Method",
        "Category",
        "Discovered At",
    ])

    for em in discovered_emails:
        comp_name = em.company.name if em.company else ""
        comp_domain = em.company.domain if em.company else ""
        target_url = em.job.input_json.get("url", "")
        ver_status = em.verification.status if em.verification else "unverified"

        writer.writerow([
            neutralize_formula_injection(comp_name),
            neutralize_formula_injection(comp_domain),
            neutralize_formula_injection(target_url),
            neutralize_formula_injection(em.email_normalized),
            neutralize_formula_injection(ver_status),
            neutralize_formula_injection(em.origin),
            neutralize_formula_injection(em.method),
            neutralize_formula_injection(em.category),
            em.found_at.strftime("%Y-%m-%d %H:%M:%S") if em.found_at else "",
        ])

    return response


@login_required
def person_finder_view(request):
    """S-08: Person Finder (Both-Plus)."""
    if request.method == "POST":
        method = request.POST.get("method", "name_company")
        auto_verify = request.POST.get("verify") == "on"

        if method == "profile_url":
            profile_url = request.POST.get("profile_url", "").strip()
            if not profile_url:
                messages.error(request, "Please enter a public profile URL.")
                return redirect("person_finder")
            input_data = {"method": "profile_url", "profile_url": profile_url, "verify": auto_verify}
        else:
            full_name = request.POST.get("full_name", "").strip()
            company_name = request.POST.get("company_name", "").strip()
            company_domain = request.POST.get("company_domain", "").strip()
            if not full_name or not company_name:
                messages.error(request, "Full name and company name are required.")
                return redirect("person_finder")
            input_data = {
                "method": "name_company",
                "full_name": full_name,
                "company_name": company_name,
                "company_domain": company_domain,
                "verify": auto_verify,
            }

        job = FinderJob.objects.create(
            owner=request.user,
            kind="person",
            input_json=input_data
        )
        run_person_finder_job(str(job.id))
        return redirect("finder_job_detail", job_id=job.id)

    recent_jobs = FinderJob.objects.filter(owner=request.user, kind="person")[:6]
    return render(request, "finder/person.html", {
        "recent_jobs": recent_jobs,
    })


@login_required
def combined_finder_view(request):
    """S-11: Combined Finder and Verifier 4-stage pipeline."""
    if request.method == "POST":
        target_url = request.POST.get("url", "").strip()
        if not target_url:
            messages.error(request, "Please provide a valid company website.")
            return redirect("combined_finder")

        job = FinderJob.objects.create(
            owner=request.user,
            kind="company",
            input_json={"url": target_url, "verify": True}
        )
        run_company_finder_job(str(job.id))
        return redirect("finder_job_detail", job_id=job.id)

    return render(request, "finder/combined.html")


@login_required
def finder_job_detail_view(request, job_id):
    """View details, pages crawled, and discovered emails of a FinderJob."""
    job = get_object_or_404(FinderJob, id=job_id, owner=request.user)
    discovered_emails = job.discovered_emails.all()
    visited_pages = job.visited_pages.all()[:20]
    return render(request, "finder/job_detail.html", {
        "job": job,
        "discovered_emails": discovered_emails,
        "visited_pages": visited_pages,
    })


@login_required
def social_finder_view(request):
    """
    Social Media Account Finder by Email.
    Discovers and displays genuine verified social media profiles (Facebook, X/Twitter,
    Instagram, Threads, TikTok, LinkedIn, GitHub, YouTube) associated with an email.
    """
    discovered_accounts = []
    input_email = ""
    searched = False

    if request.method == "POST":
        input_email = request.POST.get("email", "").strip()
        if not input_email:
            messages.error(request, "Please enter an email address to search.")
        else:
            searched = True
            discovered_accounts = run_social_finder_search(input_email, owner=request.user)

    recent_searches = (
        SocialAccount.objects.filter(owner=request.user)
        .order_by("-created_at")[:10]
    )

    return render(request, "finder/social.html", {
        "input_email": input_email,
        "discovered_accounts": discovered_accounts,
        "searched": searched,
        "recent_searches": recent_searches,
    })

