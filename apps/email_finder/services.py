"""
Email Finder Orchestration Services (Company and Person Finder).
Fulfills Part 7, Part 11.2, 11.3, 11.4, and Part 14 (Phases 5, 6, 8).
High-speed parallel multi-URL crawling and precision email discovery.
"""
import io
import csv
import re
import uuid
import urllib.parse
import openpyxl
import concurrent.futures
from django.utils import timezone
from core.utilities.constants import (
    JOB_STATUS_RUNNING,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    ORIGIN_DISCOVERED,
    ORIGIN_INFERRED,
    EVIDENCE_DOMAIN,
    EVIDENCE_MAILBOX,
    ACCESS_RESTRICTED,
    UNSUPPORTED_URL,
    NO_EMAIL_FOUND,
    DEFAULT_MAX_UPLOAD_SIZE_BYTES,
)
from core.finder_engine.crawler import crawl_company_website, CrawlJobResult
from core.finder_engine.pattern_analyzer import detect_company_email_pattern, generate_inferred_candidate
from core.finder_engine.safe_fetch import safe_fetch_url
from core.finder_engine.extractor import extract_data_from_html
from core.finder_engine.social_finder import discover_social_accounts_for_email
from apps.email_finder.models import FinderJob, CrawlPage, Company, Person, DiscoveredEmail, SocialAccount
from apps.admin_management.models import is_suppressed_target
from apps.email_verifier.services import verify_single_email
from apps.api_management.models import UsageRecord


def save_crawl_result_to_job(job: FinderJob, crawl_result: CrawlJobResult, auto_verify: bool = True) -> FinderJob:
    """Persists company metadata, visited pages, and discovered emails for a FinderJob."""
    target_url = job.input_json.get("url", "")

    # 1. Update or create Company record
    comp_meta = crawl_result.company_metadata
    company, _ = Company.objects.update_or_create(
        owner=job.owner,
        domain=crawl_result.domain,
        defaults={
            "name": comp_meta.get("name") or crawl_result.domain,
            "website": comp_meta.get("website", target_url),
            "description": comp_meta.get("description", ""),
            "phone": ", ".join(comp_meta.get("phones", []))[:100],
            "source_url": target_url,
            "evidence": comp_meta,
        }
    )

    # 2. Persist CrawlPage records
    page_records_map = {}
    for p in crawl_result.visited_pages:
        crawl_page, _ = CrawlPage.objects.update_or_create(
            job=job,
            url=p.url,
            defaults={
                "final_url": p.final_url,
                "http_status": p.http_status,
                "robots_allowed": p.robots_allowed,
                "content_hash": p.content_hash,
                "error_code": p.error_code or "",
            }
        )
        page_records_map[p.url] = crawl_page

    # 3. Persist DiscoveredEmail records
    saved_count = 0
    for email_item in crawl_result.discovered_emails:
        if is_suppressed_target(email_item.normalized_email):
            continue

        disc_email, created = DiscoveredEmail.objects.get_or_create(
            job=job,
            email_normalized=email_item.normalized_email,
            defaults={
                "owner": job.owner,
                "company": company,
                "origin": ORIGIN_DISCOVERED,
                "method": email_item.method,
                "source_page": page_records_map.get(target_url),
                "category": email_item.category,
                "evidence_level": EVIDENCE_DOMAIN,
            }
        )
        saved_count += 1

        if auto_verify:
            verify_single_email(
                raw_email=email_item.normalized_email,
                owner=job.owner,
                allow_smtp_probe=True,
                discovered_email_id=disc_email.id
            )

    job.status = JOB_STATUS_COMPLETED
    job.result_count = saved_count
    job.finished_at = timezone.now()
    job.save()

    UsageRecord.objects.create(
        owner=job.owner,
        kind="finder_company",
        quantity=1
    )
    return job


def run_company_finder_job(job_id: str) -> FinderJob:
    """
    Executes Company Finder pipeline (Part 7.4):
    1. Crawls target website within bounded depth and page caps.
    2. Records visited pages and extracts public emails.
    3. Normalizes, deduplicates, and classifies categories.
    4. Optionally verifies each discovered email with SMTP.
    """
    job = FinderJob.objects.get(id=job_id)
    job.status = JOB_STATUS_RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    input_data = job.input_json
    target_url = input_data.get("url", "")
    auto_verify = input_data.get("verify", True)

    try:
        crawl_result: CrawlJobResult = crawl_company_website(target_url)
        return save_crawl_result_to_job(job, crawl_result, auto_verify=auto_verify)
    except Exception as e:
        job.status = JOB_STATUS_FAILED
        job.error_code = str(e)[:50]
        job.finished_at = timezone.now()
        job.save()
        return job


def run_person_finder_job(job_id: str) -> FinderJob:
    """
    Executes Person Finder Both-Plus pipeline (Part 7.5):
    - Method A: Profile URL (respects access restrictions & terms)
    - Method B: Name + Company (searches company pages + pattern analysis)
    """
    job = FinderJob.objects.get(id=job_id)
    job.status = JOB_STATUS_RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    input_data = job.input_json
    method = input_data.get("method", "name_company")
    auto_verify = input_data.get("verify", True)

    try:
        if method == "profile_url":
            profile_url = input_data.get("profile_url", "")
            # Decision D-05: If URL is LinkedIn or login-gated platform, return ACCESS_RESTRICTED
            if any(domain in profile_url.lower() for domain in ["linkedin.com", "facebook.com", "instagram.com"]):
                job.status = JOB_STATUS_COMPLETED
                job.error_code = ACCESS_RESTRICTED
                job.finished_at = timezone.now()
                job.save()
                return job

            # Fetch public profile page
            fetch_res = safe_fetch_url(profile_url)
            if not fetch_res.success:
                job.status = JOB_STATUS_FAILED
                job.error_code = fetch_res.error_code or ACCESS_RESTRICTED
                job.finished_at = timezone.now()
                job.save()
                return job

            extracted = extract_data_from_html(fetch_res.content, profile_url)
            full_name = extracted.title or "Professional Contact"
            person = Person.objects.create(
                owner=job.owner,
                full_name=full_name,
                profile_url=profile_url,
                source_url=profile_url,
            )

            # Check if any explicit email was listed on the profile
            found_count = 0
            for em in extracted.emails:
                if not is_suppressed_target(em.normalized_email):
                    disc = DiscoveredEmail.objects.create(
                        owner=job.owner,
                        job=job,
                        person=person,
                        email_normalized=em.normalized_email,
                        origin=ORIGIN_DISCOVERED,
                        method="page_text",
                        category=em.category,
                        evidence_level=EVIDENCE_DOMAIN
                    )
                    found_count += 1
                    if auto_verify:
                        verify_single_email(em.normalized_email, job.owner, discovered_email_id=disc.id)

            job.result_count = found_count
            job.status = JOB_STATUS_COMPLETED
            job.finished_at = timezone.now()
            job.save()

        else:
            # Method B: Name + Company
            full_name = input_data.get("full_name", "")
            company_name = input_data.get("company_name", "")
            domain = input_data.get("company_domain", "")

            # If domain not provided, infer basic domain from company name
            if not domain and company_name:
                domain = f"{company_name.lower().replace(' ', '').replace(',', '')}.com"

            # Create or get Company and Person
            company, _ = Company.objects.get_or_create(
                owner=job.owner,
                domain=domain,
                defaults={"name": company_name or domain, "website": f"https://{domain}"}
            )

            person = Person.objects.create(
                owner=job.owner,
                full_name=full_name,
                company=company,
                job_title=input_data.get("job_title", "Professional"),
            )

            # Discover existing company emails to establish patterns (D-06 threshold)
            existing_emails = list(DiscoveredEmail.objects.filter(
                company__domain=domain,
                origin=ORIGIN_DISCOVERED
            ).values_list("email_normalized", flat=True)[:20])

            pattern_match = detect_company_email_pattern(existing_emails)
            inferred_email = None
            if pattern_match:
                inferred_email = generate_inferred_candidate(full_name, domain, pattern_match.pattern_name)

            found_count = 0
            if inferred_email and not is_suppressed_target(inferred_email):
                disc = DiscoveredEmail.objects.create(
                    owner=job.owner,
                    job=job,
                    person=person,
                    company=company,
                    email_normalized=inferred_email,
                    origin=ORIGIN_INFERRED,
                    method="company_pattern",
                    category="management",
                    evidence_level="inferred_pattern"
                )
                found_count += 1
                if auto_verify:
                    verify_single_email(inferred_email, job.owner, discovered_email_id=disc.id)

            job.result_count = found_count
            job.status = JOB_STATUS_COMPLETED
            job.finished_at = timezone.now()
            job.save()

        UsageRecord.objects.create(
            owner=job.owner,
            kind="finder_person",
            quantity=1
        )

    except Exception as e:
        job.status = JOB_STATUS_FAILED
        job.error_code = str(e)[:50]
        job.finished_at = timezone.now()
        job.save()

    return job


def normalize_company_url(raw: str) -> str:
    """Cleans and standardizes a company URL (e.g. 'stripe.com' -> 'https://stripe.com')."""
    if not raw or not isinstance(raw, str):
        return ""
    clean = raw.strip().strip("'\"<>,;()[]* \t\r\n")
    if not clean:
        return ""
    if not clean.startswith(("http://", "https://")):
        clean = "https://" + clean
    try:
        parsed = urllib.parse.urlsplit(clean)
        netloc = parsed.netloc.lower()
        if not netloc or "." not in netloc:
            return ""
        path = parsed.path.rstrip("/")
        if path:
            return f"{parsed.scheme}://{netloc}{path}"
        return f"{parsed.scheme}://{netloc}"
    except Exception:
        return ""


def extract_urls_from_text(raw_text: str) -> list[str]:
    """Extracts, cleans, and deduplicates company URLs from multiline or delimited text."""
    if not raw_text:
        return []
    tokens = re.split(r"[\r\n,;\t]+", raw_text)
    seen = set()
    results = []
    for t in tokens:
        clean = normalize_company_url(t)
        if clean and clean not in seen:
            seen.add(clean)
            results.append(clean)
    return results


def extract_urls_from_file(file_obj, filename: str) -> list[str]:
    """
    Parses an uploaded .txt, .csv, or .xlsx file to extract company URLs.
    Supports up to 5MB file sizes and auto-detects URL columns.
    """
    if getattr(file_obj, "size", 0) > DEFAULT_MAX_UPLOAD_SIZE_BYTES:
        raise ValueError("File exceeds maximum allowed size of 5 MB.")

    ext = filename.lower().split(".")[-1]
    if ext not in ("txt", "csv", "xlsx"):
        raise ValueError("Unsupported file format. Please upload a .txt, .csv, or .xlsx file.")

    results: list[str] = []
    seen: set[str] = set()

    if ext == "txt":
        content = file_obj.read().decode("utf-8", errors="replace")
        return extract_urls_from_text(content)

    elif ext == "csv":
        content = file_obj.read().decode("utf-8-sig", errors="replace")
        sample = content[:4096]
        delimiter = ","
        try:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample, delimiters=",\t;")
            delimiter = dialect.delimiter
        except Exception:
            delimiter = ","

        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        rows = list(reader)
        if not rows:
            return []

        header = [h.strip().lower() for h in rows[0]]
        url_idx = -1
        has_header = False
        target_keywords = ("website", "url", "domain", "web", "link", "site")
        exclude_keywords = ("name", "title", "id", "notes", "description", "owner")

        for i, h in enumerate(header):
            if any(k in h for k in target_keywords) and not any(k in h for k in exclude_keywords):
                url_idx = i
                has_header = True
                break

        if url_idx == -1:
            for col_i in range(len(rows[0])):
                for r in rows[1:6]:
                    if len(r) > col_i and normalize_company_url(r[col_i]):
                        url_idx = col_i
                        has_header = True
                        break
                if url_idx != -1:
                    break

        if url_idx == -1:
            url_idx = 0
            has_header = False

        start_row = 1 if has_header else 0
        for row in rows[start_row:]:
            if len(row) > url_idx:
                clean = normalize_company_url(row[url_idx])
                if clean and clean not in seen:
                    seen.add(clean)
                    results.append(clean)

    elif ext == "xlsx":
        wb = openpyxl.load_workbook(file_obj, read_only=True, data_only=True)
        sheet = wb.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return []

        first_row = [str(c).strip().lower() for c in rows[0] if c is not None]
        url_idx = -1
        has_header = False
        target_keywords = ("website", "url", "domain", "web", "link", "site")
        exclude_keywords = ("name", "title", "id", "notes", "description", "owner")

        for i, val in enumerate(first_row):
            if any(k in val for k in target_keywords) and not any(k in val for k in exclude_keywords):
                url_idx = i
                has_header = True
                break

        if url_idx == -1:
            for col_i in range(len(rows[0])):
                for r in rows[1:6]:
                    if len(r) > col_i and r[col_i] and normalize_company_url(str(r[col_i])):
                        url_idx = col_i
                        has_header = True
                        break
                if url_idx != -1:
                    break

        if url_idx == -1:
            url_idx = 0
            has_header = False

        start_row = 1 if has_header else 0
        for row in rows[start_row:]:
            if len(row) > url_idx and row[url_idx] is not None:
                clean = normalize_company_url(str(row[url_idx]))
                if clean and clean not in seen:
                    seen.add(clean)
                    results.append(clean)

    return results


def create_and_run_company_batch(
    urls: list[str],
    owner,
    auto_verify: bool = True,
    batch_name: str = ""
) -> tuple[str, list[FinderJob]]:
    """
    Creates and executes FinderJobs for a list of company URLs under a shared batch_id.
    Performs high-speed parallel network crawling across worker threads, then safely persists results.
    """
    batch_id = str(uuid.uuid4())
    jobs: list[FinderJob] = []

    # 1. Parallel network crawling (all network calls run concurrently)
    def _fetch_worker(target_url: str):
        try:
            return target_url, crawl_company_website(target_url), None
        except Exception as e:
            return target_url, None, str(e)

    crawl_results_map = {}
    max_workers = min(len(urls), 8)
    if max_workers > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(_fetch_worker, u): u for u in urls}
            for future in concurrent.futures.as_completed(future_to_url):
                u, result, err = future.result()
                crawl_results_map[u] = (result, err)
    else:
        for u in urls:
            u, result, err = _fetch_worker(u)
            crawl_results_map[u] = (result, err)

    # 2. Main thread database persistence (100% thread safe, zero SQLite locks!)
    for url in urls:
        crawl_res, err = crawl_results_map.get(url, (None, "Unknown crawl error"))
        job = FinderJob.objects.create(
            owner=owner,
            kind="company",
            input_json={
                "url": url,
                "verify": auto_verify,
                "batch_id": batch_id,
                "batch_name": batch_name or f"Batch of {len(urls)} Companies",
            },
            status=JOB_STATUS_RUNNING,
            started_at=timezone.now(),
        )
        if crawl_res:
            save_crawl_result_to_job(job, crawl_res, auto_verify=auto_verify)
        else:
            job.status = JOB_STATUS_FAILED
            job.error_code = str(err)[:50]
            job.finished_at = timezone.now()
            job.save()

        jobs.append(job)

    return batch_id, jobs


def run_social_finder_search(email: str, owner):
    """
    Executes social media discovery for an email address, verifies profiles,
    persists records, and records usage telemetry.
    Strict: Purges any previous records for this email and saves only strictly verified accounts.
    """
    clean_email = email.strip().lower()
    discovered_list = discover_social_accounts_for_email(clean_email)

    # Purge stale records for this email so only strictly verified accounts remain
    SocialAccount.objects.filter(owner=owner, email_searched=clean_email).delete()

    saved_accounts = []
    for item in discovered_list:
        acc = SocialAccount.objects.create(
            owner=owner,
            email_searched=clean_email,
            platform=item["platform"],
            platform_display_name=item["platform_name"],
            profile_url=item["url"],
            username=item.get("username", ""),
            is_verified=item.get("is_verified", True),
            source_method=item.get("source_method", "verified_web"),
        )
        saved_accounts.append(acc)

    UsageRecord.objects.create(
        owner=owner,
        kind="finder_social",
        quantity=1
    )

    return saved_accounts

