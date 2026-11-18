"""
Unit tests for Email Verification Engine, Multi-MX Failover, and Decision Rules 1 to 13.
Fulfills Part 6.4, Part 12, Part 23.4, and Phase 4 requirements.
"""
from django.test import TestCase
from unittest.mock import patch
from core.email_engine.syntax import validate_email_syntax
from core.email_engine.rules import evaluate_verification_rules
from core.email_engine.data_lists.disposable import is_disposable_domain
from core.email_engine.smtp_client import probe_smtp_multi_mx, SMTPProbeResult
from core.utilities.constants import (
    STATUS_DELIVERABLE,
    STATUS_UNDELIVERABLE,
    STATUS_RISKY,
    STATUS_UNKNOWN,
    INVALID_SYNTAX,
    DOMAIN_NOT_FOUND,
    NO_MX_RECORDS,
    DNS_TEMPORARY_FAILURE,
    INSUFFICIENT_EVIDENCE,
    PROBE_UNAVAILABLE,
    SMTP_TIMEOUT,
    SMTP_REJECTION,
    PROVIDER_BLOCKED_PROBING,
    TEMPORARY_SERVER_FAILURE,
    GREYLISTED,
    CATCH_ALL_DOMAIN,
    SMTP_ACCEPTED,
    CATCH_ALL_NOT_DETERMINED,
    DISPOSABLE_ADDRESS,
    ROLE_BASED_ADDRESS,
    FREE_PROVIDER,
    SUPPRESSED_ADDRESS,
)


class EmailEngineRulesTests(TestCase):
    def test_syntax_validation(self):
        v1 = validate_email_syntax("info@example.com")
        self.assertTrue(v1.is_valid)
        self.assertEqual(v1.local_part, "info")
        self.assertEqual(v1.ascii_domain, "example.com")

        v2 = validate_email_syntax("plainaddress")
        self.assertFalse(v2.is_valid)

        v3 = validate_email_syntax("@missinglocal.com")
        self.assertFalse(v3.is_valid)

    def test_expanded_disposable_database(self):
        # Test core and expanded disposable providers
        self.assertTrue(is_disposable_domain("mailinator.com"))
        self.assertTrue(is_disposable_domain("tempmail.com"))
        self.assertTrue(is_disposable_domain("yopmail.net"))
        self.assertTrue(is_disposable_domain("10minutemail.co.uk"))
        self.assertTrue(is_disposable_domain("sub.mailinator.com"))  # Subdomain fallback
        self.assertTrue(is_disposable_domain("fakemailgenerator.com"))
        self.assertTrue(is_disposable_domain("burnermail.io"))

        # Valid corporate and free domains are NOT disposable
        self.assertFalse(is_disposable_domain("google.com"))
        self.assertFalse(is_disposable_domain("microsoft.com"))
        self.assertFalse(is_disposable_domain("gmail.com"))

    def test_multi_mx_failover(self):
        # Simulate primary MX timeout, secondary MX accepts recipient
        with patch("core.email_engine.smtp_client.probe_single_host") as mock_probe:
            mock_probe.side_effect = [
                SMTPProbeResult(attempted=True, is_timeout=True, reason_code=SMTP_TIMEOUT, connected_mx="mx1.example.com"),
                SMTPProbeResult(attempted=True, accepted=True, reply_code=250, reason_code=SMTP_ACCEPTED, connected_mx="mx2.example.com")
            ]

            res = probe_smtp_multi_mx(["mx1.example.com", "mx2.example.com"], "contact@example.com")
            self.assertTrue(res.accepted)
            self.assertEqual(res.connected_mx, "mx2.example.com")
            self.assertEqual(mock_probe.call_count, 2)

    def test_rule_1_syntax_invalid(self):
        dec = evaluate_verification_rules(
            is_suppressed=False,
            syntax_valid=False,
            domain_exists=True,
            dns_temporary_failure=False,
            has_mx_or_fallback=True,
            smtp_probing_enabled=False,
            smtp_attempted=False,
            smtp_timeout=False,
            smtp_rejected=False,
            smtp_policy_blocked=False,
            smtp_temporary_failure=False,
            smtp_greylisted=False,
            smtp_accepted=False,
            catch_all_state="unknown",
            domain="example.com",
            local_part="bad email"
        )
        self.assertEqual(dec.status, STATUS_UNDELIVERABLE)
        self.assertIn(INVALID_SYNTAX, dec.reason_codes)

    def test_rule_2_domain_not_found(self):
        dec = evaluate_verification_rules(
            is_suppressed=False,
            syntax_valid=True,
            domain_exists=False,
            dns_temporary_failure=False,
            has_mx_or_fallback=False,
            smtp_probing_enabled=False,
            smtp_attempted=False,
            smtp_timeout=False,
            smtp_rejected=False,
            smtp_policy_blocked=False,
            smtp_temporary_failure=False,
            smtp_greylisted=False,
            smtp_accepted=False,
            catch_all_state="unknown",
            domain="nonexistentdomain9912.xyz",
            local_part="user"
        )
        self.assertEqual(dec.status, STATUS_UNDELIVERABLE)
        self.assertIn(DOMAIN_NOT_FOUND, dec.reason_codes)

    def test_rule_3_no_mx_records(self):
        dec = evaluate_verification_rules(
            is_suppressed=False,
            syntax_valid=True,
            domain_exists=True,
            dns_temporary_failure=False,
            has_mx_or_fallback=False,
            smtp_probing_enabled=False,
            smtp_attempted=False,
            smtp_timeout=False,
            smtp_rejected=False,
            smtp_policy_blocked=False,
            smtp_temporary_failure=False,
            smtp_greylisted=False,
            smtp_accepted=False,
            catch_all_state="unknown",
            domain="example.com",
            local_part="user"
        )
        self.assertEqual(dec.status, STATUS_UNDELIVERABLE)
        self.assertIn(NO_MX_RECORDS, dec.reason_codes)

    def test_rule_4_dns_temporary_failure(self):
        dec = evaluate_verification_rules(
            is_suppressed=False,
            syntax_valid=True,
            domain_exists=False,
            dns_temporary_failure=True,
            has_mx_or_fallback=False,
            smtp_probing_enabled=False,
            smtp_attempted=False,
            smtp_timeout=False,
            smtp_rejected=False,
            smtp_policy_blocked=False,
            smtp_temporary_failure=False,
            smtp_greylisted=False,
            smtp_accepted=False,
            catch_all_state="unknown",
            domain="example.com",
            local_part="user"
        )
        self.assertEqual(dec.status, STATUS_UNKNOWN)
        self.assertIn(DNS_TEMPORARY_FAILURE, dec.reason_codes)

    def test_rule_5_smtp_probe_unavailable(self):
        dec = evaluate_verification_rules(
            is_suppressed=False,
            syntax_valid=True,
            domain_exists=True,
            dns_temporary_failure=False,
            has_mx_or_fallback=True,
            smtp_probing_enabled=False,
            smtp_attempted=False,
            smtp_timeout=False,
            smtp_rejected=False,
            smtp_policy_blocked=False,
            smtp_temporary_failure=False,
            smtp_greylisted=False,
            smtp_accepted=False,
            catch_all_state="unknown",
            domain="example.com",
            local_part="user"
        )
        self.assertEqual(dec.status, STATUS_UNKNOWN)
        self.assertIn(INSUFFICIENT_EVIDENCE, dec.reason_codes)
        self.assertIn(PROBE_UNAVAILABLE, dec.reason_codes)

    def test_rule_6_smtp_timeout(self):
        dec = evaluate_verification_rules(
            is_suppressed=False,
            syntax_valid=True,
            domain_exists=True,
            dns_temporary_failure=False,
            has_mx_or_fallback=True,
            smtp_probing_enabled=True,
            smtp_attempted=True,
            smtp_timeout=True,
            smtp_rejected=False,
            smtp_policy_blocked=False,
            smtp_temporary_failure=False,
            smtp_greylisted=False,
            smtp_accepted=False,
            catch_all_state="unknown",
            domain="example.com",
            local_part="user"
        )
        self.assertEqual(dec.status, STATUS_UNKNOWN)
        self.assertIn(SMTP_TIMEOUT, dec.reason_codes)

    def test_rule_7_smtp_rejection(self):
        dec = evaluate_verification_rules(
            is_suppressed=False,
            syntax_valid=True,
            domain_exists=True,
            dns_temporary_failure=False,
            has_mx_or_fallback=True,
            smtp_probing_enabled=True,
            smtp_attempted=True,
            smtp_timeout=False,
            smtp_rejected=True,
            smtp_policy_blocked=False,
            smtp_temporary_failure=False,
            smtp_greylisted=False,
            smtp_accepted=False,
            catch_all_state="unknown",
            domain="example.com",
            local_part="nonexistent_user"
        )
        self.assertEqual(dec.status, STATUS_UNDELIVERABLE)
        self.assertIn(SMTP_REJECTION, dec.reason_codes)

    def test_rule_8_provider_blocked_probing(self):
        dec = evaluate_verification_rules(
            is_suppressed=False,
            syntax_valid=True,
            domain_exists=True,
            dns_temporary_failure=False,
            has_mx_or_fallback=True,
            smtp_probing_enabled=True,
            smtp_attempted=True,
            smtp_timeout=False,
            smtp_rejected=False,
            smtp_policy_blocked=True,
            smtp_temporary_failure=False,
            smtp_greylisted=False,
            smtp_accepted=False,
            catch_all_state="unknown",
            domain="example.com",
            local_part="user"
        )
        self.assertEqual(dec.status, STATUS_UNKNOWN)
        self.assertIn(PROVIDER_BLOCKED_PROBING, dec.reason_codes)

    def test_rule_9_greylisting(self):
        dec = evaluate_verification_rules(
            is_suppressed=False,
            syntax_valid=True,
            domain_exists=True,
            dns_temporary_failure=False,
            has_mx_or_fallback=True,
            smtp_probing_enabled=True,
            smtp_attempted=True,
            smtp_timeout=False,
            smtp_rejected=False,
            smtp_policy_blocked=False,
            smtp_temporary_failure=True,
            smtp_greylisted=True,
            smtp_accepted=False,
            catch_all_state="unknown",
            domain="example.com",
            local_part="user"
        )
        self.assertEqual(dec.status, STATUS_UNKNOWN)
        self.assertIn(GREYLISTED, dec.reason_codes)

    def test_rule_10_catch_all_domain(self):
        dec = evaluate_verification_rules(
            is_suppressed=False,
            syntax_valid=True,
            domain_exists=True,
            dns_temporary_failure=False,
            has_mx_or_fallback=True,
            smtp_probing_enabled=True,
            smtp_attempted=True,
            smtp_timeout=False,
            smtp_rejected=False,
            smtp_policy_blocked=False,
            smtp_temporary_failure=False,
            smtp_greylisted=False,
            smtp_accepted=True,
            catch_all_state="yes",
            domain="example.com",
            local_part="user"
        )
        self.assertEqual(dec.status, STATUS_RISKY)
        self.assertIn(CATCH_ALL_DOMAIN, dec.reason_codes)

    def test_rule_11_smtp_accepted(self):
        dec = evaluate_verification_rules(
            is_suppressed=False,
            syntax_valid=True,
            domain_exists=True,
            dns_temporary_failure=False,
            has_mx_or_fallback=True,
            smtp_probing_enabled=True,
            smtp_attempted=True,
            smtp_timeout=False,
            smtp_rejected=False,
            smtp_policy_blocked=False,
            smtp_temporary_failure=False,
            smtp_greylisted=False,
            smtp_accepted=True,
            catch_all_state="no",
            domain="example.com",
            local_part="user"
        )
        self.assertEqual(dec.status, STATUS_DELIVERABLE)
        self.assertIn(SMTP_ACCEPTED, dec.reason_codes)

    def test_rule_13_disposable_modifier(self):
        dec = evaluate_verification_rules(
            is_suppressed=False,
            syntax_valid=True,
            domain_exists=True,
            dns_temporary_failure=False,
            has_mx_or_fallback=True,
            smtp_probing_enabled=True,
            smtp_attempted=True,
            smtp_timeout=False,
            smtp_rejected=False,
            smtp_policy_blocked=False,
            smtp_temporary_failure=False,
            smtp_greylisted=False,
            smtp_accepted=True,
            catch_all_state="no",
            domain="mailinator.com",
            local_part="user"
        )
        self.assertEqual(dec.status, STATUS_RISKY)
        self.assertIn(DISPOSABLE_ADDRESS, dec.reason_codes)

    def test_informational_flags_and_suppression(self):
        dec = evaluate_verification_rules(
            is_suppressed=False,
            syntax_valid=True,
            domain_exists=True,
            dns_temporary_failure=False,
            has_mx_or_fallback=True,
            smtp_probing_enabled=False,
            smtp_attempted=False,
            smtp_timeout=False,
            smtp_rejected=False,
            smtp_policy_blocked=False,
            smtp_temporary_failure=False,
            smtp_greylisted=False,
            smtp_accepted=False,
            catch_all_state="unknown",
            domain="gmail.com",
            local_part="info"
        )
        self.assertTrue(dec.is_role_based)
        self.assertTrue(dec.is_free_provider)
        self.assertIn(ROLE_BASED_ADDRESS, dec.reason_codes)
        self.assertIn(FREE_PROVIDER, dec.reason_codes)

        dec_sup = evaluate_verification_rules(
            is_suppressed=True,
            syntax_valid=True,
            domain_exists=True,
            dns_temporary_failure=False,
            has_mx_or_fallback=True,
            smtp_probing_enabled=False,
            smtp_attempted=False,
            smtp_timeout=False,
            smtp_rejected=False,
            smtp_policy_blocked=False,
            smtp_temporary_failure=False,
            smtp_greylisted=False,
            smtp_accepted=False,
            catch_all_state="unknown",
            domain="example.com",
            local_part="optout"
        )
        self.assertEqual(dec_sup.status, STATUS_UNDELIVERABLE)
        self.assertIn(SUPPRESSED_ADDRESS, dec_sup.reason_codes)

    def test_extract_emails_from_text(self):
        from apps.email_verifier.services import extract_emails_from_text
        text = """
        user1@example.com
        user2@example.com, user3@example.com; user4@example.com
        user1@example.com
        """
        extracted = extract_emails_from_text(text)
        self.assertEqual(len(extracted), 4)
        self.assertEqual(extracted, ["user1@example.com", "user2@example.com", "user3@example.com", "user4@example.com"])

    def test_simultaneous_multi_verification(self):
        from apps.email_verifier.services import verify_multiple_emails_concurrently
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user, _ = User.objects.get_or_create(email="tester@example.com")
        
        # Verify 3 emails simultaneously
        test_emails = ["alpha@example.com", "beta@example.com", "gamma@example.com"]
        results = verify_multiple_emails_concurrently(test_emails, owner=user, allow_smtp_probe=False)
        self.assertEqual(len(results), 3)
        self.assertEqual([r.email_normalized for r in results], ["alpha@example.com", "beta@example.com", "gamma@example.com"])

    def test_over_30_emails_redirects_to_batch_processing(self):
        from django.test import Client
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user, _ = User.objects.get_or_create(email="tester2@example.com")
        client = Client()
        client.force_login(user)

        # 32 emails submitted
        over_30 = "\n".join([f"user{i}@example.com" for i in range(1, 33)])
        response = client.post("/verifier/single/", {"email": over_30})
        # Should redirect to bulk_verifier (existing Batch Processing option)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/verifier/bulk/", response.url)

    def test_single_email_view_renders_correctly(self):
        from django.test import Client
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user, _ = User.objects.get_or_create(email="tester3@example.com")
        client = Client()
        client.force_login(user)

        response = client.post("/verifier/single/", {"email": "hello@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("result", response.context)
        self.assertIn("results", response.context)
        self.assertEqual(len(response.context["results"]), 1)


