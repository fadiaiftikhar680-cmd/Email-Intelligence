"""
Unit tests for SSRF Guard and Outbound URL Security.
Fulfills Part 7.2, Part 8.3, and Phase 5 acceptance criteria.
"""
from django.test import TestCase
from core.security.ssrf import validate_target_url, SSRFValidationError
from core.utilities.constants import UNSAFE_TARGET, INVALID_URL


class SSRFGuardTests(TestCase):
    def test_blocks_loopback(self):
        with self.assertRaises(SSRFValidationError) as ctx:
            validate_target_url("http://127.0.0.1/admin")
        self.assertEqual(ctx.exception.code, UNSAFE_TARGET)

    def test_blocks_rfc1918_private_ranges(self):
        private_urls = [
            "http://10.0.0.1/internal",
            "https://172.16.0.5/api",
            "http://192.168.1.100:80/router",
        ]
        for url in private_urls:
            with self.assertRaises(SSRFValidationError) as ctx:
                validate_target_url(url)
            self.assertEqual(ctx.exception.code, UNSAFE_TARGET)

    def test_blocks_cloud_metadata_address(self):
        metadata_url = "http://169.254.169.254/latest/meta-data/"
        with self.assertRaises(SSRFValidationError) as ctx:
            validate_target_url(metadata_url)
        self.assertEqual(ctx.exception.code, UNSAFE_TARGET)

    def test_blocks_ipv6_loopback(self):
        ipv6_url = "http://[::1]/"
        with self.assertRaises(SSRFValidationError) as ctx:
            validate_target_url(ipv6_url)
        self.assertEqual(ctx.exception.code, UNSAFE_TARGET)

    def test_blocks_disallowed_schemes(self):
        disallowed = [
            "file:///etc/passwd",
            "gopher://127.0.0.1:70",
            "ftp://files.example.com",
            "javascript:alert(1)",
        ]
        for url in disallowed:
            with self.assertRaises(SSRFValidationError) as ctx:
                validate_target_url(url)
            self.assertEqual(ctx.exception.code, UNSAFE_TARGET)

    def test_blocks_disallowed_ports(self):
        with self.assertRaises(SSRFValidationError) as ctx:
            validate_target_url("http://example.com:22")
        self.assertEqual(ctx.exception.code, UNSAFE_TARGET)

        with self.assertRaises(SSRFValidationError) as ctx:
            validate_target_url("http://example.com:25")
        self.assertEqual(ctx.exception.code, UNSAFE_TARGET)

