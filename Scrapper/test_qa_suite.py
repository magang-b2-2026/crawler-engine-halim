#!/usr/bin/env python3
"""
QA Scenario & Regression Test Suite for Crawler Engine v3.0
Verifies:
1. Semantic Deduplicator (Exact URL, syndicated press release, independent report, stub-guard)
2. CPT Quality Gatekeeper (Length, IP dump, Cloudflare WAF, paywall stubs, error screens)
3. CSS Selector Resolution (Exact URL, full domain, root domain, default fallback)
4. HTML entity unescaping & Markdown conversion
5. Dataset Multi-format Exporter (JSONL schema, Markdown structure)
"""

import html
import json
import os
import sys
import tempfile
import unittest

# Pastikan path Scrapper dapat diimpor
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Scrapper.pipeline import (
    SemanticDeduplicator,
    is_cpt_worthy_content,
    get_css_selector_for_url,
    convert_html_to_markdown,
    normalize_url_key,
    export_dataset,
)


class TestSemanticDeduplicator(unittest.TestCase):
    def setUp(self):
        self.dedup = SemanticDeduplicator(threshold=0.80, k_shingle=2)

    def test_exact_url_duplicate(self):
        """Uji deteksi duplikat URL yang persis sama."""
        url = "https://news.detik.com/berita/12345/uji-coba"
        content = "Ini adalah konten artikel berita pertama yang cukup panjang mengenai kecerdasan buatan di Indonesia."
        
        is_dup, info = self.dedup.check_duplicate(url, "Judul 1", "Detik", content)
        self.assertFalse(is_dup, "URL pertama tidak boleh dideteksi sebagai duplikat")

        # Cek ulang dengan URL yang sama
        is_dup2, info2 = self.dedup.check_duplicate(url, "Judul 1 Re-read", "Detik", content)
        self.assertTrue(is_dup2, "URL yang sama harus langsung dideteksi sebagai duplikat")
        self.assertEqual(info2["similarity_score"], 100.0)

    def test_syndicated_press_release_duplicate(self):
        """Uji deteksi berita rilis pers sindikasi (verbatim/near-duplicate >80%)."""
        wire_content_antara = (
            "Kementerian Komunikasi dan Digital Republik Indonesia mengumumkan inisiatif percepatan adopsi "
            "kecerdasan buatan nasional untuk sektor pelayanan publik dan kesehatan. Menteri Komdigi menyampaikan "
            "bahwa kolaborasi lintas sektor menjadi kunci keberhasilan transformasi digital yang berkeadilan di tanah air. "
            "Program ini mencakup pelatihan bagi puluhan ribu talenta digital dan penyediaan infrastruktur komputasi awan lokal "
            "yang aman serta mematuhi standar perlindungan data pribadi."
        )
        
        # Versi sindikasi oleh portal lain (sedikit modifikasi kalimat pembuka)
        wire_content_sindikasi = (
            "Kementerian Komunikasi dan Digital Republik Indonesia secara resmi mengumumkan inisiatif percepatan adopsi "
            "kecerdasan buatan nasional untuk sektor pelayanan publik serta kesehatan. Menteri Komdigi menegaskan "
            "bahwa kolaborasi lintas sektor menjadi kunci utama keberhasilan transformasi digital yang berkeadilan di tanah air. "
            "Program ini meliputi pelatihan bagi puluhan ribu talenta digital dan penyediaan infrastruktur komputasi awan lokal "
            "yang aman serta mematuhi regulasi perlindungan data pribadi nasional."
        )

        is_dup1, _ = self.dedup.check_duplicate("https://antaranews.com/1", "Judul Antara", "Antara", wire_content_antara)
        self.assertFalse(is_dup1)

        is_dup2, info2 = self.dedup.check_duplicate("https://portalb.com/1", "Judul Portal B", "Portal B", wire_content_sindikasi)
        self.assertTrue(is_dup2, f"Sindikasi rilis pers harus dideteksi sebagai duplikat (>80%). Info: {info2}")
        self.assertGreaterEqual(info2["similarity_score"], 80.0)

    def test_independent_reporting_preserved(self):
        """Uji bahwa liputan independen pada topik yang sama (<80%) TIDAK boleh dibuang."""
        report_a = (
            "Pemerintah mendorong hilirisasi industri kecerdasan buatan di Indonesia dengan membangun fasilitas "
            "pusat data ramah lingkungan di Batam. Investasi ini diperkirakan menyerap ribuan tenaga kerja lokal "
            "dan menarik modal asing dari berbagai perusahaan teknologi multinasional."
        )
        report_b = (
            "Para akademisi dan pengamat ekonomi mengingatkan tantangan pasokan listrik serta air bersih untuk pendinginan "
            "pusat data kecerdasan buatan. Menurut kajian Universitas Indonesia, regulasi tarif energi hijau harus jelas "
            "agar pertumbuhan fasilitas data center tidak membebani kapasitas jaringan listrik nasional."
        )

        is_dup1, _ = self.dedup.check_duplicate("https://media-a.com/1", "Artikel A", "Media A", report_a)
        self.assertFalse(is_dup1)

        is_dup2, info2 = self.dedup.check_duplicate("https://media-b.com/1", "Artikel B", "Media B", report_b)
        self.assertFalse(is_dup2, f"Liputan independen tidak boleh dibuang. Info: {info2}")

    def test_short_stub_vs_long_article_guard(self):
        """Uji pencegahan cacat logika: ringkasan pendek tidak boleh menyebabkan false positive duplikat."""
        long_article = (
            "Kementerian Komunikasi dan Digital terus melakukan evaluasi terhadap regulasi kecerdasan buatan "
            "di Indonesia guna menciptakan ruang digital yang sehat, aman, dan produktif bagi masyarakat. "
            "Dalam beberapa tahun terakhir, pertumbuhan pemanfaatan generative AI telah merambah berbagai sektor, "
            "mulai dari industri kreatif, perbankan, hingga penegakan hukum dan administrasi pemerintahan. "
            "Oleh karena itu, penyusunan panduan etika dan standar audit algoritma menjadi kebutuhan mendesak."
        )
        short_stub = "Kementerian Komunikasi dan Digital terus melakukan evaluasi terhadap regulasi kecerdasan buatan di Indonesia."

        is_dup1, _ = self.dedup.check_duplicate("https://media-a.com/long", "Artikel Panjang", "Media A", long_article)
        self.assertFalse(is_dup1)

        # Pendek vs Panjang tidak boleh menyebabkan containment 100% karena rasio panjang < 0.35
        is_dup2, info2 = self.dedup.check_duplicate("https://media-b.com/short", "Ringkasan Singkat", "Media B", short_stub)
        self.assertFalse(is_dup2, f"Ringkasan singkat tidak boleh memicu false positive duplikat. Info: {info2}")


class TestCPTQualityGate(unittest.TestCase):
    def test_valid_article(self):
        text = "Ini adalah artikel berita yang cukup panjang dan informatif " * 10
        worthy, reason = is_cpt_worthy_content("https://detik.com/news/1", text, min_words=25)
        self.assertTrue(worthy)
        self.assertEqual(reason, "Valid CPT")

    def test_too_short_text(self):
        text = "Hanya sedikit kata."
        worthy, reason = is_cpt_worthy_content("https://detik.com/news/1", text, min_words=25)
        self.assertFalse(worthy)
        self.assertIn("terlalu pendek", reason)

    def test_raw_ip_dump_filter(self):
        text = "192.168.1.1\n10.0.0.1\n172.16.0.1\n8.8.8.8\n1.1.1.1\n" * 6
        worthy, reason = is_cpt_worthy_content("https://example.com/ips", text, min_words=10)
        self.assertFalse(worthy)
        self.assertIn("dump alamat IP", reason)

    def test_cloudflare_waf_screen_filter(self):
        text = "Just a moment... Enable JavaScript and cookies to continue. Attention Required! | Cloudflare"
        worthy, reason = is_cpt_worthy_content("https://arena.inilah.com/article", text, min_words=5)
        self.assertFalse(worthy)
        self.assertIn("WAF", reason)

    def test_paywall_stub_filter(self):
        text = "Pemerintah sedang mengkaji aturan baru mengenai perlindungan data pribadi dan kecerdasan buatan. Baca selengkapnya dengan berlangganan harian kompas.id untuk mendapatkan analisis mendalam."
        worthy, reason = is_cpt_worthy_content("https://kompas.id/baca/1", text, min_words=10)
        self.assertFalse(worthy)
        self.assertIn("WAF / Error screen", reason)

    def test_non_web_domains(self):
        worthy, reason = is_cpt_worthy_content("https://play.google.com/store/apps/details?id=com.app", "Konten panjang " * 20)
        self.assertFalse(worthy)
        self.assertIn("Bukan artikel", reason)


class TestCSSSelectorRouting(unittest.TestCase):
    def setUp(self):
        self.css_map = {
            "detik.com": "div.detail__body-text",
            "kontan.co.id": "div.content-news",
            "inilah.com": "h1, div.MuiContainer-root p",
            "khusus.tempo.co/read/123": "div.custom-selector",
        }

    def test_exact_url_routing(self):
        sel, defined = get_css_selector_for_url("https://khusus.tempo.co/read/123", self.css_map, default_css_path="body")
        self.assertTrue(defined)
        self.assertEqual(sel, "div.custom-selector")

    def test_subdomain_root_routing(self):
        # industri.kontan.co.id harus mencocokkan kontan.co.id
        sel, defined = get_css_selector_for_url("https://industri.kontan.co.id/news/ai-growth", self.css_map, default_css_path="body")
        self.assertTrue(defined)
        self.assertEqual(sel, "div.content-news")

    def test_domain_no_www_routing(self):
        sel, defined = get_css_selector_for_url("https://www.detik.com/edu/teknologi", self.css_map, default_css_path="body")
        self.assertTrue(defined)
        self.assertEqual(sel, "div.detail__body-text")

    def test_default_fallback_routing(self):
        sel, defined = get_css_selector_for_url("https://unknown-media.id/article", self.css_map, default_css_path="body")
        self.assertFalse(defined)
        self.assertEqual(sel, "body")


class TestHTMLEntityAndMarkdown(unittest.TestCase):
    def test_html_unescaping(self):
        raw_title = "Dunia Energi &amp; Kecerdasan Buatan &#8211; Catatan Denny JA"
        unescaped = html.unescape(raw_title)
        self.assertEqual(unescaped, "Dunia Energi & Kecerdasan Buatan – Catatan Denny JA")

    def test_convert_html_to_markdown_basic(self):
        html_input = "<h1>Judul</h1><p>Paragraf pertama berita kecerdasan buatan.</p><p>Paragraf kedua kelanjutan teks.</p>"
        md_res = convert_html_to_markdown(html_input, url="https://detik.com", title="Judul")
        self.assertIn("Paragraf pertama", md_res)
        self.assertIn("Paragraf kedua", md_res)

    def test_nextjs_and_script_noise_suppressed(self):
        """Memastikan data streaming Next.js, script JSON, dan inline CSS tidak bocor ke markdown."""
        dirty_html = (
            "<style>.bar{color:red;}</style>"
            "<article><h1>Berita Hilirisasi Nikel</h1><p>Indonesia terus memperkuat rantai pasok hilirisasi tambang nikel nasional untuk industri baterai.</p></article>"
            "<script id='__NEXT_DATA__' type='application/json'>{\"props\":{\"pageProps\":{\"extra\":\"payload_noise\"}}}</script>"
            "<script>window.dataLayer = window.dataLayer || [];</script>"
        )
        clean_md = convert_html_to_markdown(dirty_html, url="https://example.com", title="Berita Hilirisasi")
        self.assertIn("Hilirisasi Nikel", clean_md)
        self.assertNotIn("payload_noise", clean_md, "JSON payload tidak boleh bocor ke dataset")
        self.assertNotIn("dataLayer", clean_md, "Script tags tidak boleh bocor ke dataset")
        self.assertNotIn(".bar{color:red;}", clean_md, "CSS styles tidak boleh bocor ke dataset")

    def test_unwrapped_html_fragment_safe(self):
        """Memastikan potongan HTML tanpa tag html/body tetap aman diekstrak tanpa error."""
        fragment = "<div><p>Ini adalah fragmen artikel berita tanpa tag root html atau body dari querySelector.</p></div>"
        res = convert_html_to_markdown(fragment)
        self.assertIn("fragmen artikel", res)

    def test_truncation_and_unhydrated_spa_detection(self):
        """Uji logika auto-fallback jika terdeteksi konten terpotong atau unhydrated SPA."""
        truncated_md = "Pemerintah merencanakan hilirisasi nikel secara bertahap di berbagai wilayah timur Indonesia. Baca selengkapnya di halaman berikutnya..."
        tail = truncated_md[-250:].lower()
        trunc_markers = ("baca selengkapnya", "halaman selanjutnya", "halaman berikutnya", "baca kelanjutannya", "bersambung ke")
        self.assertTrue(any(tm in tail for tm in trunc_markers), "Harus mendeteksi marker pemotongan teks")

        html_spa = "<html><script id='__NEXT_DATA__'>{}</script><body><p>Teaser singkat artikel.</p></body></html>"
        spa_markers = ("__NEXT_DATA__", "window.__INITIAL_STATE__", "__NUXT__", "window.__remixContext")
        has_spa = any(m in html_spa for m in spa_markers)
        word_count = len("Teaser singkat artikel.".split())
        self.assertTrue(has_spa and word_count < 120, "Harus mendeteksi SPA yang belum ter-hydrate")


class TestDatasetExporter(unittest.TestCase):
    def test_export_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_md = os.path.join(tmpdir, "test_dataset.md")
            out_jsonl = os.path.join(tmpdir, "test_dataset.jsonl")
            out_log = os.path.join(tmpdir, "test_dataset.log")

            sample_results = [
                {
                    "url": "https://media.com/1",
                    "raw_url": "https://media.com/1",
                    "title": "Inovasi AI Indonesia",
                    "source": "Media Nasional",
                    "pub_date": "Wed, 14 Oct 2026",
                    "tier": "TIER1_FAST_PATH",
                    "content": "Ini adalah isi artikel tentang inovasi kecerdasan buatan di Indonesia yang sangat menarik dan berbobot.",
                    "word_count": 15,
                    "status": "SUCCESS",
                }
            ]

            dedup = SemanticDeduplicator()
            export_dataset(sample_results, dedup, out_md, output_format="all", topic="Uji AI")

            self.assertTrue(os.path.exists(out_md), "File .md harus terbuat")
            self.assertTrue(os.path.exists(out_jsonl), "File .jsonl harus terbuat")
            self.assertTrue(os.path.exists(out_log), "File .log harus terbuat")

            # Verifikasi isi JSONL valid JSON per baris
            with open(out_jsonl, "r", encoding="utf-8") as f:
                line = f.readline()
                data = json.loads(line)
                self.assertEqual(data["title"], "Inovasi AI Indonesia")
                self.assertEqual(data["tier"], "TIER1_FAST_PATH")
                self.assertIn("crawled_at", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
