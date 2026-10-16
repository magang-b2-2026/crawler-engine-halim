#!/usr/bin/env python3
"""
Pipeline Orchestrator & Hybrid Crawler (Edisi Produksi v3.0)
Arsitektur Terpadu:
- Opsi 1: Async Concurrency Worker Pool (asyncio.Semaphore)
- Opsi 2: Hybrid Two-Tier Extraction (Tier 1: HTTPX + Trafilatura; Tier 2: Async Playwright Stealth)
- Opsi 3: Semantic Deduplication (N-gram Shingling Jaccard & Containment Overlap)
- Opsi 5: One-Click End-to-End CLI Pipeline (Discovery -> Extraction -> Quality Gate -> Deduplication -> Dataset Export)

Author: Naufal Halim
Proyek: Continual Pre-Training (CPT) Dataset Engine - KOMDIGI
"""

import argparse
import asyncio
import csv
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

# Dependencies
import httpx
import trafilatura
from markdownify import markdownify as md


# ==============================================================================
# 1. URL & CSS SELECTOR UTILITIES
# ==============================================================================

def normalize_url_key(url_str: str) -> str:
    """Normalisasi string URL / domain untuk pencocokan dictionary."""
    url_str = url_str.strip()
    url_no_proto = re.sub(r"^https?://", "", url_str, flags=re.IGNORECASE)
    return url_no_proto.rstrip("/").lower()


def load_css_paths(csv_file_path: str) -> Dict[str, str]:
    """
    Membaca pemetaan domain/URL ke css_path dari file CSV (separator ';' atau ',').
    """
    mapping: Dict[str, str] = {}
    if not os.path.isfile(csv_file_path):
        return mapping

    with open(csv_file_path, mode="r", encoding="utf-8-sig") as f:
        first_line = f.readline()
        f.seek(0)
        delimiter = ";" if ";" in first_line else ","

        reader = csv.DictReader(f, delimiter=delimiter)
        field_map = {}
        if reader.fieldnames:
            for field in reader.fieldnames:
                clean_field = field.strip().lower()
                if clean_field in ["url", "urls", "domain"]:
                    field_map["url"] = field
                elif clean_field in ["css_path", "csspath", "css", "selector"]:
                    field_map["css_path"] = field

        if "url" not in field_map or "css_path" not in field_map:
            f.seek(0)
            raw_reader = csv.reader(f, delimiter=delimiter)
            for row in raw_reader:
                if len(row) >= 2:
                    u_key = normalize_url_key(row[0])
                    mapping[u_key] = row[1].strip()
        else:
            for row in reader:
                url_val = row.get(field_map["url"], "").strip()
                css_val = row.get(field_map["css_path"], "").strip()
                if url_val and css_val:
                    u_key = normalize_url_key(url_val)
                    mapping[u_key] = css_val

    return mapping


def get_css_selector_for_url(
    url: str,
    css_paths_map: Optional[Dict[str, str]],
    default_css_path: str = "body",
    silent: bool = False,
) -> Tuple[str, bool]:
    """
    Mengembalikan tuple (css_path, is_defined).
    Mencari kecocokan: exact URL -> domain lengkap -> root domain -> substring.
    """
    if not css_paths_map:
        return default_css_path, True

    parsed = urlparse(url if url.startswith(("http://", "https://")) else f"https://{url}")
    domain = parsed.netloc.lower()
    full_url_norm = normalize_url_key(url)

    # 1. Exact full URL match
    if full_url_norm in css_paths_map:
        return css_paths_map[full_url_norm], True

    # 2. Full domain match (misal: industri.kontan.co.id)
    domain_norm = normalize_url_key(domain)
    if domain_norm in css_paths_map:
        return css_paths_map[domain_norm], True

    # 3. Domain tanpa www (misal: kompas.com dari www.kompas.com)
    domain_no_www = domain_norm.replace("www.", "")
    if domain_no_www in css_paths_map:
        return css_paths_map[domain_no_www], True

    # 4. Root domain match (misal: kontan.co.id dari industri.kontan.co.id)
    parts = domain.split(".")
    if len(parts) > 2:
        root_domain = ".".join(parts[-2:])
        if root_domain in css_paths_map:
            return css_paths_map[root_domain], True
        if len(parts) > 3 and parts[-2] in ["co", "ac", "go", "or", "biz"]:
            second_level_root = ".".join(parts[-3:])
            if second_level_root in css_paths_map:
                return css_paths_map[second_level_root], True

    # 5. Substring match
    for key, selector in css_paths_map.items():
        if key in full_url_norm or key in domain_norm:
            return selector, True

    if not silent:
        pass  # Gunakan default secara halus tanpa membanjiri log
    return default_css_path, False


# ==============================================================================
# 2. QUALITY GATEKEEPER & MARKDOWN CONVERTER
# ==============================================================================

def convert_html_to_markdown(html_content: str, url: str = "", title: str = "") -> str:
    """
    Konversi konten HTML ke Markdown bersih untuk dataset Continual Pre-Training LLM.
    Menggunakan Trafilatura sebagai filter boilerplate utama atau Markdownify sebagai DOM parser.
    """
    if not html_content or not html_content.strip():
        return ""

    markdown_text = ""

    # Strategi 1: Trafilatura (Kualitas terbaik, membuang nav/footer/iklan/rekomendasi otomatis)
    try:
        extracted = trafilatura.extract(
            html_content,
            output_format="markdown",
            include_tables=True,
            include_links=False,
            favor_precision=True,
        )
        if extracted and len(extracted.split()) >= 25:
            markdown_text = extracted.strip()
    except Exception:
        pass

    # Strategi 2: Markdownify (DOM selector tag-to-markdown)
    if not markdown_text:
        try:
            converted = md(
                html_content,
                heading_style="ATX",
                strip=["script", "style", "nav", "footer", "aside", "noscript", "iframe", "form"],
            )
            converted = re.sub(r"\n{3,}", "\n\n", converted).strip()
            if converted and len(converted.split()) >= 15:
                markdown_text = converted
        except Exception:
            pass

    # Strategi 3: Regex tag stripper fallback
    if not markdown_text:
        clean_text = re.sub(r"<[^>]+>", " ", html_content)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        markdown_text = clean_text

    return markdown_text.strip()


def is_cpt_worthy_content(url: str, text: str, min_words: int = 25) -> Tuple[bool, str]:
    """
    Mengevaluasi apakah teks hasil ekstraksi memenuhi standar CPT (Continual Pre-Training).
    Menyaring halaman non-artikel, error dumps, IP mentah, dan Cloudflare/WAF block screens.
    """
    parsed = urlparse(url)
    bad_domains = ["play.google.com", "apps.apple.com", "accounts.google.com", "facebook.com/login"]
    if any(bd in parsed.netloc.lower() for bd in bad_domains):
        return False, f"Bukan artikel/dokumen web ({parsed.netloc})"

    cleaned = text.strip()
    if not cleaned:
        return False, "Konten teks kosong"

    words = cleaned.split()
    if len(words) < min_words:
        return False, f"Teks terlalu pendek ({len(words)} kata < batas minimal {min_words} kata)"

    # Deteksi dump IP mentah
    lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
    if all(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", line) for line in lines):
        return False, "Deteksi dump alamat IP mentah (bukan artikel informatif)"

    # Deteksi WAF / Cloudflare block screen patterns & paywall stubs
    block_phrases = [
        "attention required! | cloudflare",
        "just a moment...",
        "access denied",
        "403 forbidden",
        "enable javascript and cookies",
        "security check to access",
        "sorry, you have been blocked",
        "error 400 (bad request)",
        "page not found",
        "halaman tidak ditemukan",
        "baca selengkapnya dengan berlangganan",
        "konten ini eksklusif untuk pelanggan",
        "silakan login untuk membaca",
        "berlangganan kompas.id",
        "anda telah mencapai batas gratis",
    ]
    first_800 = cleaned[:800].lower()
    for phrase in block_phrases:
        if phrase in first_800:
            return False, f"Deteksi halaman blokir WAF / Error screen ('{phrase}')"

    return True, "Valid CPT"


# ==============================================================================
# 3. SEMANTIC DEDUPLICATION (N-gram Shingling & Jaccard/Containment Overlap)
# ==============================================================================

class SemanticDeduplicator:
    """
    Opsi 3: Mendeteksi dan mengeliminasi berita sindikasi ganda (syndicated wire news / press release)
    yang dilaporkan oleh banyak media berita secara verbatim atau dengan sedikit parafrase.
    """

    def __init__(self, threshold: float = 0.80, k_shingle: int = 2):
        self.threshold = threshold
        self.k_shingle = k_shingle
        self.seen_articles: List[Dict] = []
        self.seen_urls: Set[str] = set()

    def _get_shingles(self, text: str) -> Set[str]:
        words = re.findall(r"\b[a-zA-Z0-9\u00C0-\u024F]{2,}\b", text.lower())
        if len(words) < self.k_shingle:
            return set(words)
        return set(" ".join(words[i : i + self.k_shingle]) for i in range(len(words) - self.k_shingle + 1))

    def check_duplicate(self, url: str, title: str, source: str, content: str) -> Tuple[bool, Optional[Dict]]:
        """
        Memeriksa apakah konten artikel ini duplikat dari artikel yang telah terdaftar sebelumnya.
        Menggunakan kombinasi Jaccard Similarity dan Containment (Overlap) Coefficient.
        """
        # Cek 1: Duplikat URL Persis (O(1))
        norm_url = normalize_url_key(url)
        if norm_url in self.seen_urls:
            return True, {
                "matched_url": url,
                "matched_title": title,
                "matched_source": source,
                "jaccard": 100.0,
                "containment": 100.0,
                "similarity_score": 100.0,
            }

        shingles = self._get_shingles(content)
        if not shingles:
            return False, None

        for seen in self.seen_articles:
            seen_shingles = seen["shingles"]
            intersection = len(shingles & seen_shingles)
            union = len(shingles | seen_shingles)
            jaccard = intersection / union if union > 0 else 0.0

            min_len = min(len(shingles), len(seen_shingles))
            max_len = max(len(shingles), len(seen_shingles))

            # Mitigasi Cacat Logika: Containment hanya dihitung jika dokumen memiliki
            # minimal 25 shingles dan rasio panjang dokumen sebanding (>= 0.35)
            # agar ringkasan pendek tidak keliru dianggap duplikat dokumen panjang.
            if min_len >= 25 and (min_len / max_len) >= 0.35:
                containment = intersection / min_len
            else:
                containment = 0.0

            max_sim = max(jaccard, containment)
            if max_sim >= self.threshold:
                return True, {
                    "matched_url": seen["url"],
                    "matched_title": seen["title"],
                    "matched_source": seen["source"],
                    "jaccard": round(jaccard * 100, 1),
                    "containment": round(containment * 100, 1),
                    "similarity_score": round(max_sim * 100, 1),
                }

        # Jika unik, daftarkan ke seen_articles dan seen_urls
        self.seen_urls.add(norm_url)
        self.seen_articles.append({
            "url": url,
            "title": title,
            "source": source,
            "shingles": shingles,
            "content_len": len(content),
        })
        return False, None


# ==============================================================================
# 4. GOOGLE NEWS RSS DISCOVERY & DECODER
# ==============================================================================

def fetch_google_news_rss(query: str, when: str = "7d", limit: int = 30) -> List[Dict[str, str]]:
    """
    Mengambil daftar artikel berita terverifikasi dari endpoint RSS Google News.
    """
    clean_query = query.strip()
    if when:
        clean_query = f"{clean_query} when:{when}"

    encoded_query = urllib.parse.quote_plus(clean_query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=id&gl=ID&ceid=ID:id"

    print(f"[*] Menghubungi Google News RSS: {rss_url}")
    req = urllib.request.Request(
        rss_url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    )

    articles = []
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        print(f"[*] Ditemukan {len(items)} artikel di feed Google News.")

        for item in items[:limit]:
            title = item.findtext("title", default="").strip()
            link = item.findtext("link", default="").strip()
            pub_date = item.findtext("pubDate", default="").strip()
            source = item.findtext("source", default="Media Nasional").strip()

            if link:
                articles.append({
                    "title": title,
                    "link": link,
                    "source": source,
                    "pub_date": pub_date,
                    "decoded_url": "",
                })

    except Exception as e:
        print(f"[!] Gagal mengambil Google News RSS: {e}")

    return articles


def batch_decode_google_news_urls(articles: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Mendekode token URL Google News RSS (/rss/articles/CBMi...) menjadi URL langsung portal berita.
    Menggunakan googlenewsdecoder jika tersedia, dengan fallback gracefully jika gagal.
    """
    if not articles:
        return articles

    print(f"[*] Mendekode {len(articles)} URL Google News RSS ke URL asli penerbit...")
    try:
        from googlenewsdecoder import GoogleDecoder

        urls_to_decode = [a["link"] for a in articles]
        with GoogleDecoder(timeout=10.0) as decoder:
            results = decoder.decode_google_news_urls(urls_to_decode)

        decoded_count = 0
        for a, res in zip(articles, results):
            if res.get("success") and res.get("decoded_url"):
                a["decoded_url"] = res["decoded_url"]
                decoded_count += 1
            else:
                a["decoded_url"] = a["link"]  # Biarkan Playwright menangani redirect

        print(f"[OK] Berhasil mendekode {decoded_count}/{len(articles)} URL secara instan.")
    except Exception as e:
        print(f"[!] Info decoder: {e}. Menggunakan URL asli untuk resolusi browser dinamis.")
        for a in articles:
            a["decoded_url"] = a["link"]

    return articles


# ==============================================================================
# 5. HYBRID TWO-TIER ASYNC CRAWLER (Opsi 1 & Opsi 2)
# ==============================================================================

class HybridAsyncCrawler:
    """
    Crawler Asinkron Dua Tingkat (Two-Tier Hybrid):
    - Tier 1 (Fast-Path): Direct HTTPX asynchronous client + Trafilatura extraction (< 500ms).
    - Tier 2 (Browser Fallback): Async Playwright Chromium pool dengan stealth script untuk
      halaman dengan proteksi WAF, client-side JS rendering (Next.js/React), atau dynamic redirects.
    """

    def __init__(
        self,
        css_paths_map: Dict[str, str],
        default_css_path: str = "body",
        concurrency: int = 8,
        timeout: int = 15,
        min_words: int = 25,
        headless: bool = True,
    ):
        self.css_paths_map = css_paths_map
        self.default_css_path = default_css_path
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)
        self.timeout = timeout
        self.min_words = min_words
        self.headless = headless

        self.http_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "id,en-US;q=0.9,en;q=0.8",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

    async def _fetch_tier1_fastpath(
        self, client: httpx.AsyncClient, url: str, css_path: str
    ) -> Optional[Tuple[str, str, str]]:
        """
        Tier 1: Ekstraksi cepat menggunakan HTTPX + Trafilatura.
        Return: (final_url, markdown_content, page_title) atau None jika butuh Tier 2.
        """
        # Lewati Tier 1 jika URL masih berupa token Google News redirect yang belum didekode
        if "news.google.com/rss/articles" in url or "google.com/url" in url:
            return None

        try:
            resp = await client.get(url, headers=self.http_headers, follow_redirects=True, timeout=self.timeout)
            if resp.status_code != 200:
                return None

            html_text = resp.text
            final_url = str(resp.url)

            # Ekstrak judul sederhana dari tag <title>
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
            page_title = title_match.group(1).strip() if title_match else ""

            # Ekstraksi Trafilatura
            markdown_content = convert_html_to_markdown(html_text, url=final_url, title=page_title)
            is_worthy, _ = is_cpt_worthy_content(final_url, markdown_content, min_words=self.min_words)

            if is_worthy:
                return final_url, markdown_content, page_title

        except Exception:
            pass

        return None

    async def _crawl_single_article(
        self,
        article: Dict[str, str],
        client: httpx.AsyncClient,
        playwright_browser,
        idx: int,
        total: int,
    ) -> Dict:
        """
        Menjalankan alur ekstraksi dua tingkat (Fast-Path -> Fallback) untuk 1 artikel.
        """
        target_url = article.get("decoded_url") or article.get("link")
        raw_url = article.get("link")
        source = article.get("source", "Media")
        title = html.unescape(article.get("title", ""))
        title = re.sub(r"\s+", " ", title).strip()
        pub_date = article.get("pub_date", "")

        is_redirect_link = "google.com" in target_url or "news.google.com" in target_url
        css_path, is_defined = get_css_selector_for_url(
            target_url, self.css_paths_map, self.default_css_path, silent=is_redirect_link
        )

        async with self.semaphore:
            # -------------------------------------------------------------
            # TIER 1: FAST-PATH (HTTPX + Trafilatura)
            # -------------------------------------------------------------
            t0 = time.time()
            tier1_res = await self._fetch_tier1_fastpath(client, target_url, css_path)
            if tier1_res:
                final_url, markdown_text, page_title = tier1_res
                clean_title = html.unescape(page_title) if page_title else title
                clean_title = re.sub(r"\s+", " ", clean_title).strip()
                elapsed_ms = (time.time() - t0) * 1000
                words = len(markdown_text.split())
                print(f"[{idx}/{total}] [TIER 1 - FAST PATH] ({elapsed_ms:.0f}ms | {words} kata) [{source}] {target_url[:75]}...")
                return {
                    "url": final_url,
                    "raw_url": raw_url,
                    "title": clean_title,
                    "source": source,
                    "pub_date": pub_date,
                    "tier": "TIER1_FAST_PATH",
                    "content": markdown_text,
                    "word_count": words,
                    "status": "SUCCESS",
                }

            # -------------------------------------------------------------
            # TIER 2: BROWSER FALLBACK (Async Playwright Stealth)
            # -------------------------------------------------------------
            t0 = time.time()
            final_url = target_url
            markdown_text = ""
            status = "SUCCESS"
            page_title = title
            context = None
            page = None

            try:
                context = await playwright_browser.new_context(
                    user_agent=self.http_headers["User-Agent"],
                    viewport={"width": 1920, "height": 1080},
                    ignore_https_errors=True,
                )
                await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
                page = await context.new_page()

                await page.goto(target_url, wait_until="domcontentloaded", timeout=self.timeout * 1000)

                # Stabilisasi redirect Google / pemendek URL
                if "google.com" in target_url:
                    try:
                        await page.wait_for_url(lambda u: "google.com" not in u, timeout=5000)
                    except Exception:
                        pass
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=4000)
                except Exception:
                    pass

                await page.wait_for_timeout(1000)

                final_url = page.url
                raw_page_title = await page.title()
                if raw_page_title:
                    page_title = html.unescape(raw_page_title)
                    page_title = re.sub(r"\s+", " ", page_title).strip()

                # Resolusi CSS path dinamis setelah redirect
                if final_url != target_url:
                    final_css, final_defined = get_css_selector_for_url(
                        final_url, self.css_paths_map, self.default_css_path, silent=True
                    )
                    if final_defined or not is_defined:
                        css_path = final_css

                # Ekstraksi innerHTML dari target selektor (dengan proteksi context destroyed)
                eval_js = """(cssPath) => {
                    let el = document.querySelector(cssPath);
                    if (el) return el.innerHTML;
                    let nodes = document.querySelectorAll(cssPath);
                    if (nodes.length > 0) {
                        let res = '';
                        nodes.forEach(n => res += '\\n' + n.innerHTML);
                        return res;
                    }
                    let semantic = document.querySelector('article') || document.querySelector('main') || document.querySelector('.article-content');
                    if (semantic) return semantic.innerHTML;
                    return document.body ? document.body.innerHTML : '';
                }"""

                try:
                    raw_html = await page.evaluate(eval_js, css_path)
                except Exception:
                    # Retry evaluasi jika terjadi late-navigation / redirect susulan
                    await page.wait_for_timeout(1500)
                    final_url = page.url
                    raw_html = await page.evaluate(eval_js, css_path)

                # Konversi ke Markdown
                markdown_text = convert_html_to_markdown(raw_html, url=final_url, title=page_title)
                is_worthy, reason = is_cpt_worthy_content(final_url, markdown_text, min_words=self.min_words)

                if not is_worthy:
                    status = f"FILTERED: {reason}"
                else:
                    status = "SUCCESS"

                elapsed_ms = (time.time() - t0) * 1000
                words = len(markdown_text.split()) if markdown_text else 0
                if status == "SUCCESS":
                    print(f"[{idx}/{total}] [TIER 2 - PLAYWRIGHT] ({elapsed_ms:.0f}ms | {words} kata) [{source}] {final_url[:75]}...")
                else:
                    print(f"[{idx}/{total}] [QUALITY GATE FILTERED] {reason} | [{source}] {final_url[:70]}...")

            except Exception as e:
                status = f"ERROR: {str(e)}"
                print(f"[{idx}/{total}] [CRAWL ERROR] {e} | {target_url[:70]}")
            finally:
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass
                if context:
                    try:
                        await context.close()
                    except Exception:
                        pass

            return {
                "url": final_url,
                "raw_url": raw_url,
                "title": page_title or title,
                "source": source,
                "pub_date": pub_date,
                "tier": "TIER2_PLAYWRIGHT",
                "content": markdown_text if status == "SUCCESS" else "",
                "word_count": len(markdown_text.split()) if status == "SUCCESS" else 0,
                "status": status,
            }

    async def crawl_articles(self, articles: List[Dict[str, str]]) -> List[Dict]:
        """
        Menjalankan crawling asinkron paralel untuk seluruh daftar artikel.
        """
        from playwright.async_api import async_playwright

        results = []
        print(f"\n[*] Memulai Hybrid Async Pool (Concurrency: {self.concurrency}, Headless: {self.headless})...")

        limits = httpx.Limits(
            max_connections=max(self.concurrency * 2, 20),
            max_keepalive_connections=self.concurrency,
        )
        async with httpx.AsyncClient(timeout=self.timeout, limits=limits, verify=False) as http_client:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                )

                tasks = [
                    self._crawl_single_article(art, http_client, browser, idx, len(articles))
                    for idx, art in enumerate(articles, 1)
                ]

                results = await asyncio.gather(*tasks)
                await browser.close()

        return results


# ==============================================================================
# 6. PIPELINE EXPORT & AUDIT REPORTING (Opsi 5)
# ==============================================================================

def export_dataset(
    results: List[Dict],
    deduplicator: SemanticDeduplicator,
    output_path: str,
    output_format: str = "all",
    topic: str = "",
    when: str = "",
    total_time_sec: float = 0.0,
):
    """
    Menyimpan hasil crawling bersih ke format Markdown, JSONL, dan file audit Log.
    Melakukan deduplikasi semantik sebelum penulisan akhir.
    """
    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(output_path))[0]

    md_file = os.path.join(out_dir, f"{base_name}.md")
    jsonl_file = os.path.join(out_dir, f"{base_name}.jsonl")
    log_file = os.path.join(out_dir, f"{base_name}.log")

    valid_cpt_items = [r for r in results if r["status"] == "SUCCESS" and r["content"]]
    failed_or_filtered = [r for r in results if r["status"] != "SUCCESS" or not r["content"]]

    # Tahap Deduplikasi Semantik
    unique_items: List[Dict] = []
    duplicate_items: List[Dict] = []

    for item in valid_cpt_items:
        is_dup, dup_info = deduplicator.check_duplicate(
            url=item["url"],
            title=item["title"],
            source=item["source"],
            content=item["content"],
        )
        if is_dup:
            item["status"] = f"FILTERED: DUPLICATE ({dup_info['similarity_score']}% serupa dengan {dup_info['matched_source']})"
            item["duplicate_info"] = dup_info
            duplicate_items.append(item)
            print(f"[DUPLICATE DROPPED] Sim: {dup_info['similarity_score']}% | [{item['source']}] -> [{dup_info['matched_source']}] {item['url'][:70]}")
        else:
            unique_items.append(item)

    # 1. Export ke Markdown
    if output_format in ["md", "all"]:
        md_articles = []
        for idx, item in enumerate(unique_items, 1):
            header = f"# {item['title']}\n\n"
            header += f"> **Sumber:** [{item['source']}]({item['url']})\n"
            if item.get("pub_date"):
                header += f"> **Tanggal Publikasi:** {item['pub_date']}\n"
            header += f"> **Jalur Ekstraksi:** `{item['tier']}` | **Jumlah Kata:** {item['word_count']} kata\n\n"

            # Bersihkan jika konten sudah mengandung judul di baris pertama
            body = item["content"].strip()
            if body.startswith("# "):
                body = re.sub(r"^#\s+[^\n]+\n+", "", body)

            md_articles.append(header + body)

        with open(md_file, "w", encoding="utf-8") as f:
            f.write("\n\n---\n\n".join(md_articles))
            f.write("\n")
        print(f"[OK] Dataset Markdown disimpan ke: {md_file}")

    # 2. Export ke JSONL (HuggingFace / PyTorch CPT format)
    if output_format in ["jsonl", "all"]:
        with open(jsonl_file, "w", encoding="utf-8") as f:
            for idx, item in enumerate(unique_items, 1):
                json_record = {
                    "id": f"cpt_doc_{idx:05d}",
                    "title": item["title"],
                    "url": item["url"],
                    "source": item["source"],
                    "published_at": item.get("pub_date", ""),
                    "tier": item["tier"],
                    "word_count": item["word_count"],
                    "content": item["content"],
                    "crawled_at": datetime.now().isoformat(),
                }
                f.write(json.dumps(json_record, ensure_ascii=False) + "\n")
        print(f"[OK] Dataset JSONL disimpan ke: {jsonl_file}")

    # 3. Export ke Audit Log (.log)
    total_words = sum(item["word_count"] for item in unique_items)
    tier1_count = sum(1 for item in unique_items if item["tier"] == "TIER1_FAST_PATH")
    tier2_count = sum(1 for item in unique_items if item["tier"] == "TIER2_PLAYWRIGHT")

    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"=== PIPELINE AUDIT REPORT & QUALITY LOG ===\n")
        f.write(f"Waktu Eksekusi       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Topik Pencarian      : {topic or 'Direct URLs'}\n")
        f.write(f"Filter Waktu Kebaruan: {when or 'None'}\n")
        f.write(f"Total URL Diproses   : {len(results)}\n")
        f.write(f"Total Lolos CPT Bersih: {len(unique_items)} artikel ({total_words:,} kata)\n")
        f.write(f"  - Jalur Tier 1 (Fast-Path) : {tier1_count} artikel ({tier1_count/len(results)*100:.1f}%)\n" if results else "0\n")
        f.write(f"  - Jalur Tier 2 (Playwright): {tier2_count} artikel ({tier2_count/len(results)*100:.1f}%)\n" if results else "0\n")
        f.write(f"Total Duplikat Dieliminasi : {len(duplicate_items)} artikel (Ambang batas: {deduplicator.threshold*100:.0f}%)\n")
        f.write(f"Total Ditolak Quality Gate : {len(failed_or_filtered)} artikel\n")
        f.write(f"Total Durasi Eksekusi: {total_time_sec:.2f} detik ({len(results)/total_time_sec:.2f} artikel/detik)\n\n" if total_time_sec > 0 else "")

        if duplicate_items:
            f.write("--- DAFTAR ARTIKEL DUPLIKAT (DIELIMINASI) ---\n")
            for dup in duplicate_items:
                info = dup["duplicate_info"]
                f.write(f"• [{dup['source']}] {dup['url']}\n")
                f.write(f"  -> Duplikat dari: [{info['matched_source']}] {info['matched_url']}\n")
                f.write(f"  -> Skor Kesamaan: Jaccard={info['jaccard']}%, Overlap={info['containment']}%\n\n")

        if failed_or_filtered:
            f.write("--- DAFTAR ARTIKEL DITOLAK / GAGAL ---\n")
            for flt in failed_or_filtered:
                f.write(f"• URL: {flt.get('url') or flt.get('raw_url')}\n")
                f.write(f"  Status: {flt['status']}\n\n")

    print(f"[OK] Audit Quality Log disimpan ke: {log_file}")

    # Cetak ringkasan eksekutif ke terminal
    print("\n" + "=" * 65)
    print("           RINGKASAN EKSEKUTIF PIPELINE CRAWLER")
    print("=" * 65)
    print(f"Topik Berita       : {topic or 'URLs'}")
    print(f"Total Diproses     : {len(results)} artikel")
    print(f"Lolos CPT Bersih   : {len(unique_items)} artikel ({total_words:,} kata)")
    print(f"Efisiensi Fast-Path: {tier1_count} artikel (Tier 1)")
    print(f"Fallback Playwright: {tier2_count} artikel (Tier 2)")
    print(f"Duplikat Dibuang   : {len(duplicate_items)} artikel")
    print(f"Ditolak Filter/WAF : {len(failed_or_filtered)} artikel")
    if total_time_sec > 0:
        print(f"Kecepatan Pipeline : {total_time_sec:.2f} detik ({len(results)/total_time_sec:.2f} artikel/detik)")
    print("=" * 65 + "\n")


# ==============================================================================
# 7. MAIN ENTRYPOINT (CLI)
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Unified Pipeline Orchestrator (Google News RSS -> Hybrid Async Crawler -> Quality Gate -> Deduplication -> Dataset Export)"
    )
    # Sumber URL (Bisa dari Topic atau file URLs)
    src_group = parser.add_mutually_exclusive_group(required=True)
    src_group.add_argument(
        "-t", "--topic", "-q", "--query",
        help="Topik/kata kunci pencarian Google News (misal: 'Kecerdasan Buatan Indonesia')",
    )
    src_group.add_argument(
        "-u", "--urls",
        help="Path file teks berisi daftar URL kustom (1 URL per baris)",
    )

    # Filter & Pengaturan Ekstraksi
    parser.add_argument(
        "-w", "--when",
        default="7d",
        help="Filter kebaruan Google News (misal: 1d, 3d, 7d, 30d). Default: 7d",
    )
    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=30,
        help="Batas maksimal artikel yang diambil. Default: 30",
    )
    parser.add_argument(
        "-o", "--output",
        default="Scrapper/output/dataset_cpt.md",
        help="Path file output dataset. Default: Scrapper/output/dataset_cpt.md",
    )
    parser.add_argument(
        "-f", "--format",
        choices=["md", "jsonl", "all"],
        default="all",
        help="Format output dataset: 'md', 'jsonl', atau 'all'. Default: all",
    )
    parser.add_argument(
        "-c", "--concurrency",
        type=int,
        default=8,
        help="Batas maksimal async worker paralel. Default: 8",
    )
    parser.add_argument(
        "-s", "--sim-threshold",
        type=float,
        default=0.80,
        help="Ambang batas kemiripan deduplikasi semantik (0.0 - 1.0). Default: 0.80 (80%%)",
    )
    parser.add_argument(
        "--css-paths",
        default="Scrapper/sample_css_paths.csv",
        help="Path ke file CSV pemetaan CSS selector per domain. Default: Scrapper/sample_css_paths.csv",
    )
    parser.add_argument(
        "--default-css",
        default="body",
        help="Default CSS selector jika domain tidak terdaftar. Default: 'body'",
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=25,
        help="Batas minimal kata agar artikel lolos CPT Quality Gate. Default: 25",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="Timeout ekstraksi per artikel (detik). Default: 15",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Jalankan browser Playwright dalam mode terlihat (GUI). Default: headless",
    )

    args = parser.parse_args()

    # Catat waktu mulai
    start_time = time.time()

    # 1. Muat pemetaan CSS selector
    css_paths_map = load_css_paths(args.css_paths) if os.path.exists(args.css_paths) else {}
    print(f"[*] Memuat {len(css_paths_map)} pemetaan CSS selector dari {args.css_paths}")

    # 2. Pengambilan Daftar Artikel (Google News RSS atau File URLs)
    articles: List[Dict[str, str]] = []
    if args.topic:
        raw_articles = fetch_google_news_rss(args.topic, when=args.when, limit=args.limit)
        if not raw_articles:
            print("[!] Tidak ada artikel yang ditemukan dari Google News RSS.")
            return
        articles = batch_decode_google_news_urls(raw_articles)
    elif args.urls:
        if not os.path.isfile(args.urls):
            print(f"[Error] File daftar URL '{args.urls}' tidak ditemukan.")
            return
        with open(args.urls, "r", encoding="utf-8") as f:
            for line in f:
                u = line.strip()
                if u and not u.startswith("#") and u.lower() != "url":
                    articles.append({
                        "title": "",
                        "link": u,
                        "source": "Custom URL",
                        "pub_date": "",
                        "decoded_url": u,
                    })
        articles = articles[:args.limit]
        print(f"[*] Memuat {len(articles)} URL dari file {args.urls}")

    if not articles:
        print("[!] Daftar artikel kosong.")
        return

    # 3. Jalankan Hybrid Async Crawler (Opsi 1 & Opsi 2)
    crawler = HybridAsyncCrawler(
        css_paths_map=css_paths_map,
        default_css_path=args.default_css,
        concurrency=args.concurrency,
        timeout=args.timeout,
        min_words=args.min_words,
        headless=not args.headful,
    )

    crawl_results = asyncio.run(crawler.crawl_articles(articles))

    # 4. Deduplikasi Semantik & Ekspor Dataset (Opsi 3 & Opsi 5)
    deduplicator = SemanticDeduplicator(threshold=args.sim_threshold)
    total_duration = time.time() - start_time

    export_dataset(
        results=crawl_results,
        deduplicator=deduplicator,
        output_path=args.output,
        output_format=args.format,
        topic=args.topic or "",
        when=args.when,
        total_time_sec=total_duration,
    )


if __name__ == "__main__":
    main()
