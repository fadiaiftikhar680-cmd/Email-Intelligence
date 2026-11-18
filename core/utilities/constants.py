"""
Constants for Email Intelligence Platform.
Defines all status codes, reason codes, error codes, and operational taxonomy.
"""

# Verification Statuses (Part 6.3)
STATUS_DELIVERABLE = "deliverable"
STATUS_UNDELIVERABLE = "undeliverable"
STATUS_RISKY = "risky"
STATUS_UNKNOWN = "unknown"

VERIFICATION_STATUSES = [
    (STATUS_DELIVERABLE, "Deliverable"),
    (STATUS_UNDELIVERABLE, "Undeliverable"),
    (STATUS_RISKY, "Risky"),
    (STATUS_UNKNOWN, "Unknown"),
]

# Evidence Levels (Part 6.4, 6.6)
EVIDENCE_NONE = "none"
EVIDENCE_SYNTAX = "syntax"
EVIDENCE_DOMAIN = "domain"
EVIDENCE_MAILBOX = "mailbox"

# Finder Origins and States (Part 7.5)
ORIGIN_DISCOVERED = "discovered"
ORIGIN_INFERRED = "inferred"

FINDER_STATE_DISCOVERED = "discovered"
FINDER_STATE_INFERRED = "inferred"
FINDER_STATE_UNKNOWN = "unknown"
FINDER_STATE_NOT_FOUND = "not_found"
FINDER_STATE_ACCESS_RESTRICTED = "access_restricted"

# Job Statuses
JOB_STATUS_QUEUED = "queued"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_CANCELLED = "cancelled"

JOB_STATUS_CHOICES = [
    (JOB_STATUS_QUEUED, "Queued"),
    (JOB_STATUS_RUNNING, "Running"),
    (JOB_STATUS_COMPLETED, "Completed"),
    (JOB_STATUS_FAILED, "Failed"),
    (JOB_STATUS_CANCELLED, "Cancelled"),
]

# Verification Reason Codes (Part 6.4, Part 15.3)
INVALID_SYNTAX = "INVALID_SYNTAX"
DOMAIN_NOT_FOUND = "DOMAIN_NOT_FOUND"
NO_MX_RECORDS = "NO_MX_RECORDS"
DNS_TEMPORARY_FAILURE = "DNS_TEMPORARY_FAILURE"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
PROBE_UNAVAILABLE = "PROBE_UNAVAILABLE"
SMTP_TIMEOUT = "SMTP_TIMEOUT"
SMTP_REJECTION = "SMTP_REJECTION"
PROVIDER_BLOCKED_PROBING = "PROVIDER_BLOCKED_PROBING"
TEMPORARY_SERVER_FAILURE = "TEMPORARY_SERVER_FAILURE"
GREYLISTED = "GREYLISTED"
CATCH_ALL_DOMAIN = "CATCH_ALL_DOMAIN"
SMTP_ACCEPTED = "SMTP_ACCEPTED"
CATCH_ALL_NOT_DETERMINED = "CATCH_ALL_NOT_DETERMINED"
DISPOSABLE_ADDRESS = "DISPOSABLE_ADDRESS"
ROLE_BASED_ADDRESS = "ROLE_BASED_ADDRESS"
FREE_PROVIDER = "FREE_PROVIDER"
SUPPRESSED_ADDRESS = "SUPPRESSED_ADDRESS"

# Error Codes (Part 15.2)
INVALID_EMAIL = "INVALID_EMAIL"
INVALID_URL = "INVALID_URL"
UNSUPPORTED_URL = "UNSUPPORTED_URL"
SITE_UNREACHABLE = "SITE_UNREACHABLE"
DNS_FAILURE = "DNS_FAILURE"
DUPLICATE_EMAIL = "DUPLICATE_EMAIL"
NO_EMAIL_FOUND = "NO_EMAIL_FOUND"
ACCESS_RESTRICTED = "ACCESS_RESTRICTED"
CAPTCHA_ENCOUNTERED = "CAPTCHA_ENCOUNTERED"
CRAWL_TIMEOUT = "CRAWL_TIMEOUT"
UNSAFE_TARGET = "UNSAFE_TARGET"
FILE_TOO_LARGE = "FILE_TOO_LARGE"
INVALID_CSV = "INVALID_CSV"
INVALID_XLSX = "INVALID_XLSX"
MISSING_EMAIL_COLUMN = "MISSING_EMAIL_COLUMN"
DUPLICATE_BULK_JOB = "DUPLICATE_BULK_JOB"
WORKER_CRASH = "WORKER_CRASH"
REDIS_UNAVAILABLE = "REDIS_UNAVAILABLE"
DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
API_AUTH_FAILED = "API_AUTH_FAILED"
RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
VALIDATION_ERROR = "VALIDATION_ERROR"

# User-Safe Error Messages (Part 15.2)
ERROR_MESSAGES = {
    INVALID_EMAIL: "Email is not valid.",
    INVALID_URL: "The URL is not valid.",
    UNSUPPORTED_URL: "This URL type is not supported.",
    SITE_UNREACHABLE: "The website could not be reached.",
    DNS_FAILURE: "Domain could not be resolved.",
    NO_MX_RECORDS: "Domain has no mail route.",
    SMTP_TIMEOUT: "Mail server did not respond in time.",
    SMTP_REJECTION: "Mail server rejected the recipient.",
    CATCH_ALL_DOMAIN: "Domain accepts all addresses.",
    DISPOSABLE_ADDRESS: "Disposable provider detected.",
    DUPLICATE_EMAIL: "Duplicate removed.",
    NO_EMAIL_FOUND: "No public emails found.",
    ACCESS_RESTRICTED: "Access to this page is restricted; it was not accessed.",
    CAPTCHA_ENCOUNTERED: "Page requires a CAPTCHA; skipped.",
    CRAWL_TIMEOUT: "Crawl exceeded its time budget.",
    UNSAFE_TARGET: "Target is not allowed.",
    FILE_TOO_LARGE: "File exceeds the size limit.",
    INVALID_CSV: "File could not be read as CSV.",
    INVALID_XLSX: "File could not be read as XLSX.",
    MISSING_EMAIL_COLUMN: "No email column selected or detected.",
    DUPLICATE_BULK_JOB: "An identical job already exists.",
    WORKER_CRASH: "Processing was interrupted; it will resume.",
    REDIS_UNAVAILABLE: "Service temporarily unavailable.",
    DATABASE_UNAVAILABLE: "Service temporarily unavailable.",
    API_AUTH_FAILED: "Authentication failed.",
    RATE_LIMIT_EXCEEDED: "Too many requests. Please wait before retrying.",
    VALIDATION_ERROR: "The provided parameters are invalid.",
}

# Finder categories
CATEGORY_GENERAL = "general"
CATEGORY_SUPPORT = "support"
CATEGORY_SALES = "sales"
CATEGORY_CAREERS = "careers"
CATEGORY_HR = "hr"
CATEGORY_MANAGEMENT = "management"
CATEGORY_PRESS = "press"
CATEGORY_OTHER = "other"
CATEGORY_UNKNOWN = "unknown"

CATEGORY_CHOICES = [
    (CATEGORY_GENERAL, "General"),
    (CATEGORY_SUPPORT, "Support"),
    (CATEGORY_SALES, "Sales"),
    (CATEGORY_CAREERS, "Careers"),
    (CATEGORY_HR, "HR"),
    (CATEGORY_MANAGEMENT, "Management"),
    (CATEGORY_PRESS, "Press"),
    (CATEGORY_OTHER, "Other"),
    (CATEGORY_UNKNOWN, "Unknown"),
]

# Roles
ROLE_USER = "user"
ROLE_ADMIN = "admin"

ROLE_CHOICES = [
    (ROLE_USER, "User"),
    (ROLE_ADMIN, "Admin"),
]

# API Scopes
SCOPE_EMAIL_VERIFY = "email:verify"
SCOPE_BULK_WRITE = "bulk:write"
SCOPE_FINDER_RUN = "finder:run"
SCOPE_JOBS_READ = "jobs:read"
SCOPE_USAGE_READ = "usage:read"
SCOPE_ACCOUNT_READ = "account:read"

ALL_API_SCOPES = [
    SCOPE_EMAIL_VERIFY,
    SCOPE_BULK_WRITE,
    SCOPE_FINDER_RUN,
    SCOPE_JOBS_READ,
    SCOPE_USAGE_READ,
    SCOPE_ACCOUNT_READ,
]

# Default limits (Part 21.1)
DEFAULT_MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_MAX_BULK_ROWS = 10000
DEFAULT_MAX_CONCURRENT_JOBS = 2
DEFAULT_MAX_CRAWL_DEPTH = 2
DEFAULT_MAX_CRAWL_PAGES = 8  # High-yield targeted crawl limit
DEFAULT_MAX_PAGE_RESPONSE_SIZE = 2 * 1024 * 1024  # 2 MB
DEFAULT_CONNECT_TIMEOUT = 3.5
DEFAULT_READ_TIMEOUT = 5.0
DEFAULT_DNS_TIMEOUT = 3.0
DEFAULT_SMTP_TIMEOUT = 5.0
DEFAULT_USER_RETENTION_DAYS = 90

