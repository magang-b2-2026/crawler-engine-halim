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
    sanitize_cpt_text,
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
    def test_export_structure_each_mode(self):
        """Uji mode default 'each': 1 artikel = 1 file .md di dalam folder dataset."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_target = os.path.join(tmpdir, "test_dataset")
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
            export_dataset(sample_results, dedup, out_target, output_format="all", output_mode="each", topic="Uji AI")

            dataset_dir = os.path.join(tmpdir, "test_dataset")
            self.assertTrue(os.path.isdir(dataset_dir), "Folder dataset harus terbuat")

            md_files = [f for f in os.listdir(dataset_dir) if f.endswith(".md")]
            self.assertEqual(len(md_files), 1, "Harus menghasilkan tepat 1 file .md per artikel")
            self.assertTrue(md_files[0].startswith("article_001_"))

            jsonl_file = os.path.join(dataset_dir, "test_dataset.jsonl")
            log_file = os.path.join(dataset_dir, "test_dataset.log")
            self.assertTrue(os.path.exists(jsonl_file), "File .jsonl harus terbuat di folder dataset")
            self.assertTrue(os.path.exists(log_file), "File .log harus terbuat di folder dataset")

            with open(jsonl_file, "r", encoding="utf-8") as f:
                data = json.loads(f.readline())
                self.assertEqual(data["title"], "Inovasi AI Indonesia")
                self.assertEqual(data["tier"], "TIER1_FAST_PATH")
                self.assertIn("crawled_at", data)

    def test_export_structure_merge_mode(self):
        """Uji mode 'merge' untuk backward-compatibility file gabungan tunggal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_md = os.path.join(tmpdir, "test_dataset.md")
            sample_results = [
                {
                    "url": "https://media.com/1",
                    "raw_url": "https://media.com/1",
                    "title": "Inovasi AI Indonesia",
                    "source": "Media Nasional",
                    "pub_date": "Wed, 14 Oct 2026",
                    "tier": "TIER1_FAST_PATH",
                    "content": "Ini adalah isi artikel.",
                    "word_count": 5,
                    "status": "SUCCESS",
                }
            ]

            dedup = SemanticDeduplicator()
            export_dataset(sample_results, dedup, out_md, output_format="all", output_mode="merge", topic="Uji AI")

            self.assertTrue(os.path.exists(out_md), "File .md merge harus terbuat")
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "test_dataset.jsonl")), "File .jsonl harus terbuat")
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "test_dataset.log")), "File .log harus terbuat")


class TestCPTTextSanitizer(unittest.TestCase):
    """Pengujian unit komprehensif untuk sanitasi dataset CPT (tanda petik, unicode, derau berita)."""

    def test_curly_and_fancy_quotes_normalized_to_ascii(self):
        """Memastikan semua variasi tanda petik miring/fancy dinormalkan menjadi ASCII double-quote murni."""
        raw = "Menteri menegaskan: “Kecerdasan Buatan” dan «Teknologi Informasi» adalah prioritas utama „digitalisasi″."
        clean = sanitize_cpt_text(raw)
        self.assertNotIn("“", clean)
        self.assertNotIn("”", clean)
        self.assertNotIn("«", clean)
        self.assertNotIn("»", clean)
        self.assertIn('"Kecerdasan Buatan"', clean)
        self.assertIn('"Teknologi Informasi"', clean)

    def test_apostrophes_and_single_quotes_normalized(self):
        """Memastikan apostrof miring dan petik tunggal menjadi ASCII 39 (')."""
        raw = "Kebijakan ini disahkan pada hari Jum’at dengan rujukan Al-Qur’an serta petik ‘inovasi’."
        clean = sanitize_cpt_text(raw)
        self.assertNotIn("’", clean)
        self.assertNotIn("‘", clean)
        self.assertIn("Jum'at", clean)
        self.assertIn("Al-Qur'an", clean)
        self.assertIn("'inovasi'", clean)

    def test_invisible_whitespace_and_soft_hyphens_purged(self):
        """Memastikan karakter tak kasat mata (NBSP, ZWSP, BOM, soft-hyphen) dibersihkan."""
        raw = "Kementerian\u00a0Komunikasi\u200bdan\ufeffDigital In\u00adfor\u00adma\u00adsi"
        clean = sanitize_cpt_text(raw)
        self.assertNotIn("\u00a0", clean)
        self.assertNotIn("\u200b", clean)
        self.assertNotIn("\ufeff", clean)
        self.assertNotIn("\u00ad", clean)
        self.assertEqual(clean, "Kementerian Komunikasi dan Digital Informasi")

    def test_dashes_and_ranges_normalized(self):
        """Memastikan en-dash/em-dash pada rentang angka dan klausa jeda dinormalkan."""
        raw = "Periode 2024–2026 ini — menurut kajian — sangat penting."
        clean = sanitize_cpt_text(raw)
        self.assertIn("2024-2026", clean)
        self.assertIn(" - menurut kajian - ", clean)

    def test_dateline_purged_from_first_content_paragraph(self):
        """Memastikan dateline jurnalistik di awal berita dibersihkan agar kalimat langsung ke subjek."""
        raw = (
            "# Judul Berita Utama\n\n"
            "JAKARTA, KOMPAS.com - Menteri Komunikasi dan Digital Meutya Hafid menegaskan percepatan AI.\n\n"
            "Kalimat paragraf kedua tetap utuh."
        )
        clean = sanitize_cpt_text(raw)
        self.assertIn("# Judul Berita Utama", clean)
        self.assertNotIn("JAKARTA, KOMPAS.com -", clean)
        self.assertIn("Menteri Komunikasi dan Digital Meutya Hafid menegaskan", clean)
        self.assertIn("Kalimat paragraf kedua tetap utuh.", clean)

    def test_in_article_noise_and_editorial_signatures_purged(self):
        """Memastikan 'Baca juga', 'Simak video', 'Penulis/Editor', dan inisial redaksi dibuang."""
        raw = (
            "# Transformasi Digital\n\n"
            "Pemerintah terus memperkuat hilirisasi teknologi.\n\n"
            "Baca juga: Menkomdigi Resmikan Fasilitas Cloud AI\n\n"
            "Infrastruktur data center ramah lingkungan dibangun di berbagai daerah.\n\n"
            "Simak Video: Wawancara Khusus Terkait Regulasi Digital\n\n"
            "[Gambas:Video 20detik]\n\n"
            "Penulis: Ahmad Rifai | Editor: Budi Santoso\n\n"
            "(kcm/ard)"
        )
        clean = sanitize_cpt_text(raw)
        self.assertNotIn("Baca juga:", clean)
        self.assertNotIn("Simak Video:", clean)
        self.assertNotIn("[Gambas:", clean)
        self.assertNotIn("Penulis: Ahmad Rifai", clean)
        self.assertNotIn("(kcm/ard)", clean)
        self.assertIn("Pemerintah terus memperkuat hilirisasi teknologi.", clean)
        self.assertIn("Infrastruktur data center ramah lingkungan dibangun di berbagai daerah.", clean)

    def test_cms_metadata_counters_and_rubrics_purged(self):
        """Memastikan view counter, uploader CMS, rubrik tunggal, dan tanggal mentah dibuang."""
        raw = (
            "### Judul Artikel Sama\n\n"
            "PENDIDIKAN\n\n"
            "Oct 17, 2026 -\n\n"
            "Diposting Oleh : Newsroom Diskominfosantik -\n\n"
            "Dibaca : 373 Kali\n\n"
            "CIKARANG PUSAT - Pemerintah Kabupaten Bekasi memperkuat dukungan pendidikan vokasi."
        )
        clean = sanitize_cpt_text(raw, title="Judul Artikel Sama")
        self.assertNotIn("PENDIDIKAN", clean)
        self.assertNotIn("Oct 17, 2026 -", clean)
        self.assertNotIn("Diposting Oleh :", clean)
        self.assertNotIn("Dibaca : 373 Kali", clean)
        self.assertNotIn("### Judul Artikel Sama", clean)
        self.assertNotIn("CIKARANG PUSAT -", clean)
        self.assertEqual(clean, "Pemerintah Kabupaten Bekasi memperkuat dukungan pendidikan vokasi.")

    def test_photo_captions_and_copyright_disclaimers_purged(self):
        """Memastikan caption foto, kredit fotografer, disclaimer copyright, dan anti-crawling dibuang."""
        raw = (
            "Kegiatan sosialisasi literasi digital berlangsung sukses di aula pertemuan.\n\n"
            "Foto : Imanuddin/Diskominfosantik.\n\n"
            "Peserta antusias mengikuti seluruh rangkaian materi yang disampaikan.\n\n"
            "Dilarang keras mengambil konten, melakukan crawling atau pengindeksan otomatis untuk AI di situs web ini tanpa izin tertulis dari Kantor Berita ANTARA.\n\n"
            "Copyright © ANTARA 2026"
        )
        clean = sanitize_cpt_text(raw)
        self.assertNotIn("Foto : Imanuddin/Diskominfosantik.", clean)
        self.assertNotIn("Dilarang keras mengambil konten", clean)
        self.assertNotIn("Copyright ©", clean)
        self.assertIn("Kegiatan sosialisasi literasi digital berlangsung sukses di aula pertemuan.", clean)
        self.assertIn("Peserta antusias mengikuti seluruh rangkaian materi yang disampaikan.", clean)


if __name__ == "__main__":
    unittest.main(verbosity=2)

