"""
Bulk Verification Engine and File Processing Services.
Fulfills Part 4.1, Part 11.6, and Part 23.5.
"""
import io
import csv
import openpyxl
from django.utils import timezone
from core.utilities.constants import (
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    DEFAULT_MAX_UPLOAD_SIZE_BYTES,
    DEFAULT_MAX_BULK_ROWS,
    FILE_TOO_LARGE,
    INVALID_CSV,
    INVALID_XLSX,
    MISSING_EMAIL_COLUMN,
)
from core.utilities.normalization import normalize_email, neutralize_formula_injection
from core.storage.storage import save_uploaded_file, save_export_file, get_full_storage_path
from apps.bulk_processing.models import BulkJob, BulkChunk, BulkRecord
from apps.email_verifier.services import verify_single_email
from apps.history_reports.models import ExportRecord
from apps.api_management.models import UsageRecord


def detect_csv_delimiter(sample_text: str) -> str:
    """Detects delimiter among comma, semicolon, tab."""
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample_text, delimiters=",\t;")
        return dialect.delimiter
    except Exception:
        return ","


def create_bulk_job_from_file(file_obj, filename: str, owner, email_column: str = "") -> BulkJob:
    """
    Parses uploaded file (.csv or .xlsx), validates limits, detects email column,
    and creates BulkJob + BulkRecords + BulkChunks.
    """
    if file_obj.size > DEFAULT_MAX_UPLOAD_SIZE_BYTES:
        raise ValueError(FILE_TOO_LARGE)

    ext = filename.lower().split(".")[-1]
    if ext not in ("csv", "xlsx"):
        raise ValueError("Unsupported file format. Please upload a .csv or .xlsx file.")

    relative_ref, full_path = save_uploaded_file(file_obj, filename)

    raw_rows: list[str] = []
    headers: list[str] = []

    if ext == "csv":
        try:
            with open(full_path, "r", encoding="utf-8-sig", errors="replace") as f:
                content = f.read()
            sample = content[:4096]
            delim = detect_csv_delimiter(sample)
            reader = csv.reader(content.splitlines(), delimiter=delim)
            all_lines = list(reader)
            if not all_lines:
                raise ValueError(INVALID_CSV)

            # Header detection
            first_row = all_lines[0]
            col_idx = 0
            if email_column and email_column in first_row:
                col_idx = first_row.index(email_column)
                data_lines = all_lines[1:]
            else:
                # Find column containing 'email' in header or containing '@'
                detected_idx = -1
                for idx, col in enumerate(first_row):
                    if "email" in str(col).lower():
                        detected_idx = idx
                        break
                if detected_idx != -1:
                    col_idx = detected_idx
                    data_lines = all_lines[1:]
                else:
                    # Check first row has '@'
                    if any("@" in str(c) for c in first_row):
                        data_lines = all_lines
                    else:
                        data_lines = all_lines[1:]

            for row in data_lines[:DEFAULT_MAX_BULK_ROWS]:
                if len(row) > col_idx:
                    raw_rows.append(row[col_idx].strip())
        except Exception as e:
            raise ValueError(f"{INVALID_CSV}: {str(e)}")

    elif ext == "xlsx":
        try:
            wb = openpyxl.load_workbook(full_path, read_only=True, data_only=True)
            sheet = wb.active
            rows_iter = sheet.iter_rows(values_only=True)
            first_row = next(rows_iter, None)
            if not first_row:
                raise ValueError(INVALID_XLSX)

            col_idx = 0
            detected = False
            for idx, cell in enumerate(first_row):
                if cell and "email" in str(cell).lower():
                    col_idx = idx
                    detected = True
                    break

            for r in rows_iter:
                if len(raw_rows) >= DEFAULT_MAX_BULK_ROWS:
                    break
                if r and len(r) > col_idx and r[col_idx]:
                    raw_rows.append(str(r[col_idx]).strip())
        except Exception as e:
            raise ValueError(f"{INVALID_XLSX}: {str(e)}")

    if not raw_rows:
        raise ValueError(MISSING_EMAIL_COLUMN)

    # Create BulkJob
    bulk_job = BulkJob.objects.create(
        owner=owner,
        filename=filename,
        file_ref=relative_ref,
        email_column=email_column,
        total_rows=len(raw_rows),
        status=JOB_STATUS_QUEUED,
        progress_counts={"total": len(raw_rows), "processed": 0, "deliverable": 0, "risky": 0, "undeliverable": 0, "unknown": 0}
    )

    # Create Records and deduplicate
    seen_emails = set()
    valid_count = 0
    duplicate_count = 0
    invalid_count = 0

    records_to_create = []
    for idx, raw_val in enumerate(raw_rows, start=1):
        norm_email, lp, dom = normalize_email(raw_val)
        if not norm_email or "@" not in norm_email or not dom:
            state = "invalid"
            invalid_count += 1
        elif norm_email in seen_emails:
            state = "duplicate"
            duplicate_count += 1
        else:
            state = "pending"
            seen_emails.add(norm_email)
            valid_count += 1

        records_to_create.append(BulkRecord(
            bulk_job=bulk_job,
            row_number=idx,
            raw_value=raw_val,
            email_normalized=norm_email,
            state=state
        ))

    BulkRecord.objects.bulk_create(records_to_create, batch_size=500)

    # Create BulkChunks (50 items per chunk)
    chunk_size = 50
    chunks_to_create = []
    for i in range(0, len(records_to_create), chunk_size):
        seq = (i // chunk_size) + 1
        chunks_to_create.append(BulkChunk(
            bulk_job=bulk_job,
            seq=seq,
            status=JOB_STATUS_QUEUED
        ))
    BulkChunk.objects.bulk_create(chunks_to_create)

    bulk_job.valid_rows = valid_count
    bulk_job.duplicate_rows = duplicate_count
    bulk_job.invalid_rows = invalid_count
    bulk_job.save(update_fields=["valid_rows", "duplicate_rows", "invalid_rows"])

    return bulk_job


def process_bulk_job(job_id: str) -> BulkJob:
    """Processes all chunks of a bulk verification job."""
    job = BulkJob.objects.get(id=job_id)
    job.status = JOB_STATUS_RUNNING
    job.save(update_fields=["status"])

    records = job.records.filter(state="pending").order_by("row_number")
    counts = job.progress_counts or {"total": job.total_rows, "processed": 0, "deliverable": 0, "risky": 0, "undeliverable": 0, "unknown": 0}

    for record in records:
        ver = verify_single_email(
            raw_email=record.email_normalized,
            owner=job.owner,
            bulk_record_id=record.id
        )
        record.verification = ver
        record.state = "verified"
        record.save(update_fields=["verification", "state"])

        counts["processed"] = counts.get("processed", 0) + 1
        counts[ver.status] = counts.get(ver.status, 0) + 1

    # Mark chunks completed
    job.chunks.update(status=JOB_STATUS_COMPLETED, finished_at=timezone.now())

    job.status = JOB_STATUS_COMPLETED
    job.finished_at = timezone.now()
    job.progress_counts = counts
    job.save(update_fields=["status", "finished_at", "progress_counts"])

    UsageRecord.objects.create(
        owner=job.owner,
        kind="verify_bulk",
        quantity=counts["processed"]
    )

    return job


def generate_bulk_export(job_id: str, fmt: str = "csv") -> ExportRecord:
    """
    Exports bulk verification results to CSV or XLSX with formula-injection neutralization.
    Fulfills Part 8.4 and Part 23.5.
    """
    job = BulkJob.objects.get(id=job_id)
    records = job.records.select_related("verification").order_by("row_number")

    header = ["Row", "Original Input", "Normalized Email", "Status", "Reason Codes", "Evidence Level", "Verified At"]
    rows = []

    for r in records:
        status = r.verification.status if r.verification else r.state
        reasons = "; ".join(r.verification.reason_codes) if r.verification else ""
        ev_level = r.verification.evidence_level if r.verification else "none"
        v_at = r.verification.verified_at.isoformat() if r.verification else ""

        rows.append([
            str(r.row_number),
            neutralize_formula_injection(r.raw_value),
            neutralize_formula_injection(r.email_normalized),
            neutralize_formula_injection(status),
            neutralize_formula_injection(reasons),
            neutralize_formula_injection(ev_level),
            v_at,
        ])

    if fmt == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(header)
        writer.writerows(rows)
        content_bytes = out.getvalue().encode("utf-8-sig")
        ext = "csv"
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Verification Results"
        ws.append(header)
        for row in rows:
            ws.append(row)
        out = io.BytesIO()
        wb.save(out)
        content_bytes = out.getvalue()
        ext = "xlsx"

    ref, _ = save_export_file(content_bytes, f"bulk_{job.id}.{ext}")

    export_rec = ExportRecord.objects.create(
        owner=job.owner,
        source_type="bulk_job",
        source_id=str(job.id),
        format=ext,
        file_ref=ref,
        expires_at=timezone.now() + timezone.timedelta(days=7)
    )
    return export_rec

