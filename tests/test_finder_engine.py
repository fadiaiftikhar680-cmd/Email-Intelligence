"""
Unit tests for Finder Engine, Pattern Detection, and HTML Extraction.
Fulfills Part 7.4, Part 7.5, and Decision D-06.
"""
from django.test import TestCase
from core.finder_engine.pattern_analyzer import detect_company_email_pattern, generate_inferred_candidate
from core.finder_engine.extractor import extract_data_from_html
from core.utilities.constants import ORIGIN_INFERRED, ORIGIN_DISCOVERED


class FinderEngineTests(TestCase):
    def test_pattern_detection_threshold(self):
        # 1 email only -> insufficient to establish pattern (Decision D-06 threshold)
        single_list = ["john.doe@example.com"]
        self.assertIsNone(detect_company_email_pattern(single_list))

        # 2 matching emails -> establishes {first}.{last}
        double_list = ["john.doe@example.com", "alice.smith@example.com"]
        match = detect_company_email_pattern(double_list)
        self.assertIsNotNone(match)
        self.assertEqual(match.pattern_name, "{first}.{last}")

        # Inferred candidate generated
        inferred = generate_inferred_candidate("Bob Marley", "example.com", match.pattern_name)
        self.assertEqual(inferred, "bob.marley@example.com")

    def test_html_extraction(self):
        sample_html = """
        <html>
            <head><title>Acme Inc</title><meta name="description" content="Leading widgets maker"></head>
            <body>
                <h1>Welcome to Acme</h1>
                <p>Call us at 555-123-4567 or email <a href="mailto:sales@acme.com">sales team</a>.</p>
                <div>For general inquiries: info@acme.com</div>
            </body>
        </html>
        """
        extracted = extract_data_from_html(sample_html, "https://acme.com")
        emails = {e.normalized_email: e for e in extracted.emails}

        self.assertIn("sales@acme.com", emails)
        self.assertEqual(emails["sales@acme.com"].method, "mailto_link")
        self.assertEqual(emails["sales@acme.com"].category, "sales")

        self.assertIn("info@acme.com", emails)
        self.assertEqual(emails["info@acme.com"].method, "page_text")
        self.assertEqual(emails["info@acme.com"].category, "general")

    def test_accuracy_email_filters(self):
        from core.finder_engine.extractor import is_valid_discovered_email
        # Valid business emails
        self.assertTrue(is_valid_discovered_email("contact@stripe.com"))
        self.assertTrue(is_valid_discovered_email("sales@company.co.uk"))
        self.assertTrue(is_valid_discovered_email("team@dayzero.ai"))

        # False positive assets (e.g. image retina icons)
        self.assertFalse(is_valid_discovered_email("logo@2x.png"))
        self.assertFalse(is_valid_discovered_email("avatar@3x.jpg"))
        self.assertFalse(is_valid_discovered_email("theme@1.2.3"))

        # Template placeholders
        self.assertFalse(is_valid_discovered_email("name@example.com"))
        self.assertFalse(is_valid_discovered_email("user@domain.com"))

    def test_extract_urls_from_text(self):
        from apps.email_finder.services import extract_urls_from_text
        raw_text = """
        https://stripe.com
        shopify.com
        https://airbnb.com/contact
        stripe.com
        invalid_random_string
        http://github.com
        """
        urls = extract_urls_from_text(raw_text)
        self.assertEqual(len(urls), 4)
        self.assertIn("https://stripe.com", urls)
        self.assertIn("https://shopify.com", urls)
        self.assertIn("https://airbnb.com/contact", urls)
        self.assertIn("http://github.com", urls)

    def test_extract_urls_from_csv(self):
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.email_finder.services import extract_urls_from_file

        csv_content = b"company_name,website,notes\nAcme,https://acme.com,test\nBeta,beta.io,demo\n"
        uploaded = SimpleUploadedFile("companies.csv", csv_content, content_type="text/csv")

        urls = extract_urls_from_file(uploaded, "companies.csv")
        self.assertEqual(len(urls), 2)
        self.assertEqual(urls[0], "https://acme.com")
        self.assertEqual(urls[1], "https://beta.io")

    def test_company_finder_multi_url_view(self):
        from unittest.mock import patch
        from apps.accounts.models import User
        from core.finder_engine.crawler import CrawlJobResult

        user = User.objects.create_user(email="finder_tester@example.com", password="Password123#Secure")
        self.client.force_login(user)

        with patch("apps.email_finder.services.crawl_company_website") as mock_crawl:
            mock_crawl.return_value = CrawlJobResult(
                domain="example.com",
                visited_pages=[],
                discovered_emails=[],
                company_metadata={"name": "Example"}
            )
            resp = self.client.post("/finder/company/", {
                "source": "direct",
                "urls": "https://stripe.com\nhttps://shopify.com",
                "verify": "on"
            }, follow=True)

            self.assertEqual(resp.status_code, 200)
            self.assertIn("Company Targets in This Batch", resp.content.decode("utf-8"))

    def test_social_url_classifier(self):
        from core.finder_engine.social_finder import clean_and_classify_social_url

        # Facebook
        fb = clean_and_classify_social_url("https://www.facebook.com/alexdeveloper")
        self.assertIsNotNone(fb)
        self.assertEqual(fb["platform"], "facebook")
        self.assertEqual(fb["url"], "https://www.facebook.com/alexdeveloper")

        # X / Twitter
        tw = clean_and_classify_social_url("https://x.com/alex_tech")
        self.assertIsNotNone(tw)
        self.assertEqual(tw["platform"], "twitter")
        self.assertEqual(tw["url"], "https://x.com/alex_tech")

        # Instagram
        insta = clean_and_classify_social_url("https://www.instagram.com/alex_photos/")
        self.assertIsNotNone(insta)
        self.assertEqual(insta["platform"], "instagram")
        self.assertEqual(insta["url"], "https://www.instagram.com/alex_photos/")

        # Threads
        threads = clean_and_classify_social_url("https://www.threads.net/@alex_thoughts")
        self.assertIsNotNone(threads)
        self.assertEqual(threads["platform"], "threads")
        self.assertEqual(threads["url"], "https://www.threads.net/@alex_thoughts")

        # TikTok
        tt = clean_and_classify_social_url("https://www.tiktok.com/@alex_clips")
        self.assertIsNotNone(tt)
        self.assertEqual(tt["platform"], "tiktok")
        self.assertEqual(tt["url"], "https://www.tiktok.com/@alex_clips")

        # Ignore share/login links
        self.assertIsNone(clean_and_classify_social_url("https://www.facebook.com/sharer/sharer.php?u=foo"))
        self.assertIsNone(clean_and_classify_social_url("https://twitter.com/intent/tweet?text=foo"))
        self.assertIsNone(clean_and_classify_social_url("https://www.instagram.com/accounts/login/"))

    def test_social_finder_view(self):
        from unittest.mock import patch
        from apps.accounts.models import User
        from apps.email_finder.models import SocialAccount

        user = User.objects.create_user(email="social_user@example.com", password="Password123#Secure")
        self.client.force_login(user)

        # GET request
        resp_get = self.client.get("/finder/social/")
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn("Discover Verified Social Media Accounts", resp_get.content.decode("utf-8"))

        # POST request with mock results
        mock_accounts = [
            {
                "platform": "facebook",
                "platform_name": "Facebook",
                "username": "alexdev",
                "url": "https://www.facebook.com/alexdev",
                "icon": "facebook",
                "source_method": "Official Domain (example.com)",
                "is_verified": True
            },
            {
                "platform": "twitter",
                "platform_name": "X (Twitter)",
                "username": "@alexdev",
                "url": "https://x.com/alexdev",
                "icon": "twitter",
                "source_method": "Official Domain (example.com)",
                "is_verified": True
            },
            {
                "platform": "instagram",
                "platform_name": "Instagram",
                "username": "@alexdev",
                "url": "https://www.instagram.com/alexdev/",
                "icon": "instagram",
                "source_method": "Official Domain (example.com)",
                "is_verified": True
            },
            {
                "platform": "threads",
                "platform_name": "Threads",
                "username": "@alexdev",
                "url": "https://www.threads.net/@alexdev",
                "icon": "threads",
                "source_method": "Official Domain (example.com)",
                "is_verified": True
            },
            {
                "platform": "tiktok",
                "platform_name": "TikTok",
                "username": "@alexdev",
                "url": "https://www.tiktok.com/@alexdev",
                "icon": "tiktok",
                "source_method": "Official Domain (example.com)",
                "is_verified": True
            }
        ]

        with patch("apps.email_finder.services.discover_social_accounts_for_email") as mock_disc:
            mock_disc.return_value = mock_accounts
            resp_post = self.client.post("/finder/social/", {"email": "alex@example.com"})
            self.assertEqual(resp_post.status_code, 200)
            content = resp_post.content.decode("utf-8")
            self.assertIn("alex@example.com", content)
            self.assertIn("5 Genuine Accounts Found", content)
            self.assertIn("https://www.facebook.com/alexdev", content)
            self.assertIn("https://x.com/alexdev", content)
            self.assertIn("https://www.instagram.com/alexdev/", content)
            self.assertIn("https://www.threads.net/@alexdev", content)
            self.assertIn("https://www.tiktok.com/@alexdev", content)
            self.assertIn("Directly Open Profile ↗", content)


