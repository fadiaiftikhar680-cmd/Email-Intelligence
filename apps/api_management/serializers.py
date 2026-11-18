"""
Serializers for Public API (v1).
Fulfills Part 5.3 and Part 5.4.
"""
from rest_framework import serializers


class SingleVerifyRequestSerializer(serializers.Serializer):
    email = serializers.CharField(help_text="Email address to verify")


class VerificationEvidenceSerializer(serializers.Serializer):
    syntax_valid = serializers.BooleanField()
    domain_exists = serializers.BooleanField()
    mx_present = serializers.BooleanField()
    smtp_attempted = serializers.BooleanField()
    smtp_accepted = serializers.BooleanField(required=False)
    smtp_rejected = serializers.BooleanField(required=False)
    catch_all_state = serializers.CharField(required=False)


class SingleVerifyResponseSerializer(serializers.Serializer):
    email = serializers.CharField()
    status = serializers.CharField(help_text="deliverable | undeliverable | risky | unknown")
    reason_codes = serializers.ListField(child=serializers.CharField())
    evidence = serializers.DictField()
    is_role_based = serializers.BooleanField()
    is_disposable = serializers.BooleanField()
    verified_at = serializers.DateTimeField()


class BulkVerifyRequestSerializer(serializers.Serializer):
    emails = serializers.ListField(child=serializers.CharField(), required=False)
    file = serializers.FileField(required=False)
    email_column = serializers.CharField(required=False, allow_blank=True)


class BulkVerifyResponseSerializer(serializers.Serializer):
    job_id = serializers.UUIDField()
    status = serializers.CharField()
    total_rows = serializers.IntegerField()


class CompanyFinderRequestSerializer(serializers.Serializer):
    url = serializers.CharField(help_text="Target website URL e.g. https://example.com")
    verify = serializers.BooleanField(default=True, help_text="Automatically verify discovered emails")


class PersonFinderRequestSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=["name_company", "profile_url"])
    full_name = serializers.CharField(required=False, allow_blank=True)
    company_name = serializers.CharField(required=False, allow_blank=True)
    company_domain = serializers.CharField(required=False, allow_blank=True)
    profile_url = serializers.CharField(required=False, allow_blank=True)
    verify = serializers.BooleanField(default=True)


class DiscoveredEmailResultSerializer(serializers.Serializer):
    email = serializers.CharField()
    origin = serializers.CharField(help_text="discovered | inferred")
    method = serializers.CharField()
    category = serializers.CharField()
    source_url = serializers.CharField(allow_null=True)
    verification = serializers.DictField(allow_null=True)
    evidence_level = serializers.CharField()


class JobStatusResponseSerializer(serializers.Serializer):
    job_id = serializers.UUIDField()
    kind = serializers.CharField()
    status = serializers.CharField()
    progress_counts = serializers.DictField(required=False)
    result_count = serializers.IntegerField()
    error_code = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()
    finished_at = serializers.DateTimeField(allow_null=True)


class UsageResponseSerializer(serializers.Serializer):
    owner_email = serializers.CharField()
    total_verifications = serializers.IntegerField()
    total_finder_runs = serializers.IntegerField()
    recent_usage = serializers.ListField(child=serializers.DictField())


class AccountSummaryResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    role = serializers.CharField()
    retention_days = serializers.IntegerField()
    created_at = serializers.DateTimeField()

