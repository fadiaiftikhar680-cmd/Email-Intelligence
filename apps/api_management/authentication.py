"""
API Key Authentication and Scope Permissions for DRF.
Fulfills Part 5.2 and Part 8.5.
"""
import secrets
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions, permissions
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from core.security.api_keys import hash_api_key
from core.utilities.constants import API_AUTH_FAILED
from apps.api_management.models import APIKey
from apps.audit.models import log_audit_event


class APIKeyAuthentication(BaseAuthentication):
    """
    Authenticates requests using the header:
    Authorization: Api-Key <full_key>
    """
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "api-key":
            return None

        raw_key = parts[1].strip()
        if "_" not in raw_key:
            raise exceptions.AuthenticationFailed(detail={"error_code": API_AUTH_FAILED, "message": "Invalid API key format."})

        # Extract prefix (eip_xxxx)
        prefix_parts = raw_key.split("_")
        if len(prefix_parts) < 3:
            raise exceptions.AuthenticationFailed(detail={"error_code": API_AUTH_FAILED, "message": "Invalid API key format."})

        prefix = f"{prefix_parts[0]}_{prefix_parts[1]}"
        api_key = APIKey.objects.filter(prefix=prefix, status="active").first()
        if not api_key:
            log_audit_event("api_key_auth_failed", target_type="api_key", target_id=prefix, ip_address=self._get_client_ip(request))
            raise exceptions.AuthenticationFailed(detail={"error_code": API_AUTH_FAILED, "message": "Invalid or revoked API key."})

        # Compare SHA-256 hash
        computed_hash = hash_api_key(raw_key)
        if not secrets.compare_digest(computed_hash, api_key.key_hash):
            log_audit_event("api_key_auth_failed", actor=api_key.user, target_type="api_key", target_id=prefix, ip_address=self._get_client_ip(request))
            raise exceptions.AuthenticationFailed(detail={"error_code": API_AUTH_FAILED, "message": "Invalid or revoked API key."})

        # Update last used timestamp
        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=["last_used_at"])

        return (api_key.user, api_key)

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")


class HasAPIScope(permissions.BasePermission):
    """
    Permission check that enforces specific scope requirements on API keys.
    """
    def __init__(self, required_scope: str):
        self.required_scope = required_scope

    def __call__(self):
        return self

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # If authenticated via session (UI), allow if verified
        if not hasattr(request, "auth") or not isinstance(request.auth, APIKey):
            return request.user.is_authenticated

        # If authenticated via APIKey, verify scope
        return request.auth.has_scope(self.required_scope)


class APIKeyScheme(OpenApiAuthenticationExtension):
    target_class = "apps.api_management.authentication.APIKeyAuthentication"
    name = "ApiKeyAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Format: 'Api-Key <key>'",
        }
