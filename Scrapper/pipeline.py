#!/usr/bin/env python3
"""
Pipeline Orchestrator & Hybrid Crawler (Edisi Produksi v3.0 - Ponytail Streamlined)
Arsitektur Terpadu:
- Opsi 1: Async Concurrency Worker Pool (asyncio.Semaphore)
- Opsi 2: Hybrid Two-Tier Extraction (Tier 1: HTTPX + Trafilatura; Tier 2: Async Playwright Stealth)
- Opsi 3: Semantic Deduplication (N-gram Shingling Jaccard & Containment Overlap)
- Opsi 5: One-Click End-to-End CLI Pipeline (Discovery -> Extraction -> Quality Gate -> Deduplication -> Dataset Export)

Author: Naufal Halim | Proyek: Continual Pre-Training (CPT) Dataset Engine - KOMDIGI
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

# Auto-switch to project .venv python if executed under an unactivated/incompatible python (e.g. Python 3.14)
venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "Scripts", "python.exe"))
if os.path.isfile(venv_py) and os.path.abspath(sys.executable).lower() != venv_py.lower() and not os.environ.get("_CRAWLER_VENV_ACTIVE"):
    os.environ["_CRAWLER_VENV_ACTIVE"] = "1"
    import subprocess
    sys.exit(subprocess.call([venv_py] + sys.argv))

import httpx
import urllib.parse
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

# Windows UTF-8 console output guard (cegah charmap cp1252 crash pada karakter internasional)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ==============================================================================
# 1. URL & CSS SELECTOR UTILITIES (Ponytail Streamlined)
# ==============================================================================

def normalize_url_key(url_str: str) -> str:
    """Normalisasi string URL / domain untuk pencocokan dictionary."""
    return url_str.strip().split("://")[-1].rstrip("/").lower()


def load_css_paths(csv_file_path: str) -> Dict[str, str]:
    """Membaca pemetaan domain/URL ke css_path dari CSV (separator ';' atau ',')."""
    if not os.path.isfile(csv_file_path):
        return {}
    mapping = {}
    with open(csv_file_path, mode="r", encoding="utf-8-sig") as f:
        delim = ";" if ";" in f.readline() else ","
        f.seek(0)
        for row in csv.reader(f, delimiter=delim):
            if len(row) >= 2 and row[0].strip().lower() not in ("url", "urls", "domain"):
                mapping[normalize_url_key(row[0])] = row[1].strip()
    return mapping


def get_css_selector_for_url(
    url: str,
    css_paths_map: Optional[Dict[str, str]],
    default_css_path: str = "body",
    silent: bool = False,
) -> Tuple[str, bool]:
    """Mengembalikan tuple (css_path, is_defined) dengan pencocokan hierarkis."""
    if not css_paths_map:
        return default_css_path, True

    norm = normalize_url_key(url)
    domain = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
    dom_no_www = domain.removeprefix("www.")

    for k in (norm, domain, dom_no_www):
        if k in css_paths_map:
            return css_paths_map[k], True

    for k, sel in css_paths_map.items():
        if k in norm or k in domain:
            return sel, True

    return default_css_path, False


# ==============================================================================
# 2. QUALITY GATEKEEPER & MARKDOWN CONVERTER
# ==============================================================================

def sanitize_cpt_text(text: str, title: str = "") -> str:
    """Normalisasi tipografi, pembersihan invisible space, tanda petik ASCII, dan derau berita untuk training LLM."""
    if not text or not text.strip():
        return ""

    # 1. Normalisasi bentuk kanonikal Unicode (NFKC)
    text = unicodedata.normalize("NFKC", text)

    # 2. Pembersihan invisible spaces, zero-width characters, dan soft-hyphens
    text = text.replace("\u00a0", " ")   # Non-breaking space (&nbsp;)
    text = text.replace("\u200b", " ")   # Zero-width space (cegah kata menempel)
    text = text.replace("\u200c", "")    # Zero-width non-joiner
    text = text.replace("\u200d", "")    # Zero-width joiner
    text = text.replace("\ufeff", " ")   # Byte order mark (BOM)
    text = text.replace("\u00ad", "")    # Soft hyphen (suku kata bersatu kembali)
    text = text.replace("\u200e", "")    # LTR mark
    text = text.replace("\u200f", "")    # RTL mark
    for sp in ("\u2009", "\u202f", "\u2007", "\u2008", "\u3000"):
        text = text.replace(sp, " ")

    # 3. Normalisasi tanda petik ganda tipografi ke ASCII 34 (")
    for q in ("“", "”", "«", "»", "„", "″", "❝", "❞", "『", "』", "﹁", "﹂"):
        text = text.replace(q, '"')

    # 4. Normalisasi tanda petik tunggal tipografi & apostrof ke ASCII 39 (')
    for q in ("‘", "’", "‚", "′", "❛", "❜", "ʻ", "ʼ", "ʹ", "ʽ"):
        text = text.replace(q, "'")

    # 5. Normalisasi dash & hyphen
    text = re.sub(r"(\d+)\s*[–—―‒]\s*(\d+)", r"\1-\2", text)
    text = re.sub(r"\s*[–—―‒]+\s*", " - ", text)
    text = text.replace("…", "...")

    # 6. Pembersihan tag embed dan derau multimedia
    text = re.sub(r"\[gambas:[^\]]+\]", "", text, flags=re.I)

    # 7. Pembersihan baris demi baris (Metadata CMS, Rubrik, View Counter, CTA, Iklan, dan Caption Foto)
    RUBRIC_KEYWORDS = {
        "PENDIDIKAN", "POLITIK", "EKONOMI", "HUKUM", "KESEHATAN", "OLAHRAGA",
        "INTERNASIONAL", "NASIONAL", "TEKNO", "TEKNOLOGI", "HIBURAN", "NEWS", "DAERAH",
        "REGIONAL", "METRO", "HUMANIORA", "OPINI", "FINANCE", "LIFESTYLE",
        "JABAR", "JATENG", "JATIM", "SUMUT", "SULSEL", "BALI", "OTOMOTIF", "EDUKASI",
        "KAMPUS", "BERITA", "ARTIKEL", "PROFIL", "FOTO", "VIDEO", "LIPUTAN KHUSUS",
        "SOROTAN", "HEADLINE", "INDEX", "INDEKS", "KABAR", "EVENT", "AGENDA", "PUBLIKASI"
    }

    norm_title = re.sub(r"[^\w\s]", "", title).lower().strip() if title else ""
    clean_lines = []

    for line in text.splitlines():
        line_str = line.strip()
        if not line_str:
            clean_lines.append("")
            continue

        # A. Eliminasi judul duplikat di dalam body (heading ### yang sama dengan title)
        norm_line = re.sub(r"^[#\s\*\_]+|[#\s\*\_]+$", "", line_str).strip()
        clean_norm_line = re.sub(r"[^\w\s]", "", norm_line).lower().strip()
        if norm_title and clean_norm_line and (
            clean_norm_line == norm_title
            or (len(clean_norm_line) > 20 and clean_norm_line in norm_title)
            or (len(norm_title) > 20 and norm_title in clean_norm_line)
        ):
            continue

        if line_str.startswith("#"):
            clean_lines.append(line_str)
            continue

        # B. Eliminasi view/hit counter (misal: "Dibaca : 373 Kali", "Views: 1200")
        if re.match(r"^(?:\*\*|__)?\s*(?:dibaca|dilihat|view(?:s|ed)?|reads?|tayang)\s*:\s*\d+.*$", line_str, re.I):
            continue
        if re.match(r"^\d+\s+(?:kali\s+dibaca|views?|reads?)$", line_str, re.I):
            continue

        # C. Eliminasi metadata author/uploader CMS (misal: "Diposting Oleh : Newsroom Diskominfosantik -")
        if re.match(r"^(?:\*\*|__)?\s*(?:diposting(?:\s+oleh)?|diterbitkan(?:\s+oleh)?|dipublikasikan(?:\s+pada)?|posted(?:\s+by)?|penulis|reporter|editor|kontributor|redaktur|alih\s+bahasa|rilis|tanggal(?:\s+rilis)?|update)\s*:\s*[^\n]+$", line_str, re.I):
            continue

        # D. Eliminasi rubrik/kategori terisolasi (misal: "PENDIDIKAN", "EKONOMI")
        if (line_str.upper() in RUBRIC_KEYWORDS) or (re.match(r"^[A-Z\s]{3,20}$", line_str) and len(line_str.split()) <= 2):
            continue

        # E. Eliminasi timestamp/tanggal mentah (misal: "Oct 17, 2026 -", "14 Okt 2026 10:18 WIB")
        if re.match(r"^(?:(?:senin|selasa|rabu|kamis|jumat|sabtu|minggu|monday|tuesday|wednesday|thursday|friday|saturday|sunday)[,\s]+)?(?:(?:jan|feb|mar|apr|mei|may|jun|jul|agu|aug|sep|okt|oct|nov|des|dec)[a-z]*|\d{1,2})\s+\d{1,2}[,\s\-]+(?:\d{4})?(?:\s+[-–—|•]\s*)?(?:\s*\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:wib|wita|wit|gmt|utc))?)?\s*[-–—]?$", line_str, re.I):
            continue

        # F. Eliminasi derau navigasi & CTA sosial media
        if re.match(r"^(?:\*\*|__)?\s*(?:baca\s+juga|simak\s+juga|simak\s+video|pilihan\s+editor|artikel\s+ini\s+telah\s+tayang|tonton\s+video|lihat\s+juga|lire\s+l'article\s+complet|read\s+more|baca\s+selengkapnya)\s*:?", line_str, re.I):
            continue
        if re.match(r"^(?:\*\*|__)?\s*(?:dapatkan\s+update\s+berita|ikuti\s+saluran\s+whatsapp|simak\s+berita\s+terbaru\s+di|download\s+aplikasi|klik\s+di\s+sini\s+untuk\s+berlangganan|bergabunglah\s+dengan\s+saluran)", line_str, re.I):
            continue

        # G. Eliminasi caption gambar & kredit foto
        if re.search(r"(?:foto|photo|dok(?:umen)?|ilustrasi|sumber\s+foto)\s*:\s*[A-Za-z0-9/\.\s\-\*\_]+$", line_str, re.I) and len(line_str) < 300:
            continue
        if re.match(r"^\(?(?:foto|photo|dok(?:umen)?|ilustrasi)\s*[:/]\s*[^\n\)]+\)?$", line_str, re.I):
            continue

        # H. Eliminasi copyright, disclaimer anti-crawler, dan arsip paywall
        if re.search(r"(?:dilarang keras mengambil|copyright\s*(?:©|\(c\)|&copy;)|hak cipta dilindungi|all rights reserved|artikel ini telah masuk arsip|artikel ini telah tayang di|crawling atau pengindeksan otomatis untuk ai|simak breaking news)", line_str, re.I):
            continue

        clean_lines.append(line_str)

    # 8. Pembersihan dateline pembuka jurnalistik (pada paragraf narasi pertama yang substansial)
    new_lines = []
    dateline_checked = False
    dateline_pattern = r"^(?:\*\*|__)?\s*[A-Za-z\s,\.\-/\(\)]{2,35}?(?:\*\*|__)?\s*[-–—]{1,2}\s*(?:\*\*|__)?\s*(?=[A-Z])"

    for line in clean_lines:
        stripped = line.strip()
        if not dateline_checked and stripped and not stripped.startswith("#") and not stripped.startswith(">"):
            cleaned_line = re.sub(dateline_pattern, "", stripped).strip()
            if len(cleaned_line.split()) >= 3:
                dateline_checked = True
                if cleaned_line:
                    new_lines.append(cleaned_line)
                continue
        new_lines.append(line)

    text = "\n".join(new_lines)

    # 9. Pembersihan inisial redaksi di akhir teks (misal: (kcm/ard), (dna/dna), (ant/red))
    text = re.sub(r"\s*\(\s*[a-zA-Z0-9]{2,5}\s*/\s*[a-zA-Z0-9]{2,5}\s*\)\s*$", "", text.strip(), flags=re.I)
    text = re.sub(r"\s*\(\s*(?:ant|red|tim)\s*\)\s*$", "", text.strip(), flags=re.I)

    # 10. Rasionalisasi spasi dan baris kosong
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def convert_html_to_markdown(html_content: str, url: str = "", title: str = "") -> str:
    """Konversi HTML ke Markdown bersih untuk dataset CPT via Trafilatura / Markdownify, disanitasi untuk training LLM."""
    if not html_content or not html_content.strip():
        return ""

    raw = html_content if ("<html" in html_content[:300].lower() or "<body" in html_content[:300].lower()) else f"<!DOCTYPE html><html><body>{html_content}</body></html>"
    raw_md = ""
    try:
        import trafilatura
        ext = trafilatura.extract(raw, output_format="markdown", include_tables=True, include_links=False, favor_precision=True)
        if ext and len(ext.split()) >= 15:
            raw_md = ext.strip()
    except Exception:
        pass

    if not raw_md:
        try:
            from markdownify import markdownify as md
            sanitized = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", "", html_content, flags=re.I | re.S)
            res = md(sanitized, heading_style="ATX", strip=["nav", "footer", "aside", "iframe", "form"])
            res = re.sub(r"\n{3,}", "\n\n", res).strip()
            if res and len(res.split()) >= 15:
                raw_md = res
        except Exception:
            pass

    if not raw_md:
        clean_strip = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", "", html_content, flags=re.I | re.S)
        raw_md = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", clean_strip)).strip()

    return sanitize_cpt_text(raw_md, title=title)


BLOCK_PHRASES = (
    "attention required! | cloudflare", "just a moment...", "access denied", "403 forbidden",
    "enable javascript and cookies", "security check to access", "sorry, you have been blocked",
    "error 400 (bad request)", "page not found", "halaman tidak ditemukan",
    "baca selengkapnya dengan berlangganan", "konten ini eksklusif untuk pelanggan",
    "silakan login untuk membaca", "berlangganan kompas.id", "anda telah mencapai batas gratis",
)
BAD_DOMAINS = ("play.google.com", "apps.apple.com", "accounts.google.com", "facebook.com/login")


def is_cpt_worthy_content(url: str, text: str, min_words: int = 25) -> Tuple[bool, str]:
    """Mengevaluasi apakah teks hasil ekstraksi memenuhi standar CPT."""
    domain = urlparse(url).netloc.lower()
    if any(bd in domain for bd in BAD_DOMAINS):
        return False, f"Bukan artikel/dokumen web ({domain})"

    cleaned = text.strip()
    if not cleaned:
        return False, "Konten teks kosong"

    words = cleaned.split()
    if len(words) < min_words:
        return False, f"Teks terlalu pendek ({len(words)} kata < batas minimal {min_words} kata)"

    if all(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", line.strip()) for line in cleaned.splitlines() if line.strip()):
        return False, "Deteksi dump alamat IP mentah (bukan artikel informatif)"

    first_800 = cleaned[:800].lower()
    for phrase in BLOCK_PHRASES:
        if phrase in first_800:
            return False, f"Deteksi halaman blokir WAF / Error screen ('{phrase}')"

    return True, "Valid CPT"


# ==============================================================================
# 3. SEMANTIC DEDUPLICATION (N-gram Shingling & Overlap)
# ==============================================================================

class SemanticDeduplicator:
    """Opsi 3: Eliminasi berita sindikasi ganda via N-gram Shingling Jaccard & Containment."""

    def __init__(self, threshold: float = 0.80, k_shingle: int = 2):
        self.threshold = threshold
        self.k_shingle = k_shingle
        self.seen_articles: List[Dict] = []
        self.seen_urls: Set[str] = set()

    def _get_shingles(self, text: str) -> Set[str]:
        words = re.findall(r"\b[a-zA-Z0-9\u00C0-\u024F]{2,}\b", text.lower())
        return set(words) if len(words) < self.k_shingle else {" ".join(words[i : i + self.k_shingle]) for i in range(len(words) - self.k_shingle + 1)}

    def check_duplicate(self, url: str, title: str, source: str, content: str) -> Tuple[bool, Optional[Dict]]:
        norm_url = normalize_url_key(url)
        if norm_url in self.seen_urls:
            return True, {"matched_url": url, "matched_title": title, "matched_source": source, "jaccard": 100.0, "containment": 100.0, "similarity_score": 100.0}

        shingles = self._get_shingles(content)
        if not shingles:
            return False, None

        for seen in self.seen_articles:
            s_seen = seen["shingles"]
            inter, union = len(shingles & s_seen), len(shingles | s_seen)
            jaccard = inter / union if union > 0 else 0.0
            min_l, max_l = min(len(shingles), len(s_seen)), max(len(shingles), len(s_seen))
            containment = (inter / min_l) if (min_l >= 25 and min_l / max_l >= 0.35) else 0.0
            max_sim = max(jaccard, containment)

            if max_sim >= self.threshold:
                return True, {
                    "matched_url": seen["url"], "matched_title": seen["title"], "matched_source": seen["source"],
                    "jaccard": round(jaccard * 100, 1), "containment": round(containment * 100, 1), "similarity_score": round(max_sim * 100, 1),
                }

        self.seen_urls.add(norm_url)
        self.seen_articles.append({"url": url, "title": title, "source": source, "shingles": shingles, "content_len": len(content)})
        return False, None


# ==============================================================================
# 4. GOOGLE NEWS RSS DISCOVERY & DECODER
# ==============================================================================

def fetch_google_news_rss(query: str, when: str = "7d", limit: int = 30) -> List[Dict[str, str]]:
    """Mengambil daftar artikel berita terverifikasi dari endpoint RSS Google News."""
    clean_q = f"{query.strip()} when:{when}" if when else query.strip()
    rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote_plus(clean_q)}&hl=id&gl=ID&ceid=ID:id"
    print(f"[*] Menghubungi Google News RSS: {rss_url}")

    try:
        resp = httpx.get(rss_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        items = ET.fromstring(resp.content).findall(".//item")
        print(f"[*] Ditemukan {len(items)} artikel di feed Google News.")
        return [
            {
                "title": (it.findtext("title") or "").strip(),
                "link": (it.findtext("link") or "").strip(),
                "source": (it.findtext("source") or "Media Nasional").strip(),
                "pub_date": (it.findtext("pubDate") or "").strip(),
                "decoded_url": "",
            }
            for it in items[:limit] if it.findtext("link")
        ]
    except Exception as e:
        print(f"[!] Gagal mengambil Google News RSS: {e}")
        return []


def batch_decode_google_news_urls(articles: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Mendekode token URL Google News RSS ke URL asli penerbit."""
    if not articles:
        return articles

    print(f"[*] Mendekode {len(articles)} URL Google News RSS...")
    try:
        from googlenewsdecoder import GoogleDecoder
        with GoogleDecoder(timeout=10.0) as dec:
            results = dec.decode_google_news_urls([a["link"] for a in articles])
        for a, res in zip(articles, results):
            a["decoded_url"] = res.get("decoded_url") if res.get("success") else a["link"]
        print(f"[OK] Berhasil mendekode {sum(1 for r in results if r.get('success'))}/{len(articles)} URL.")
    except Exception as e:
        print(f"[!] Info decoder: {e}")
        for a in articles:
            a["decoded_url"] = a["link"]
    return articles


# ==============================================================================
# 5. HYBRID TWO-TIER ASYNC CRAWLER (Opsi 1 & Opsi 2)
# ==============================================================================

class HybridAsyncCrawler:
    """Crawler Asinkron Dua Tingkat: Tier 1 (Fast-Path HTTPX) + Tier 2 (Playwright Stealth)."""

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

    async def _fetch_tier1_fastpath(self, client: httpx.AsyncClient, url: str) -> Optional[Tuple[str, str, str]]:
        if "google.com" in url:
            return None
        try:
            resp = await client.get(url, headers=self.http_headers, follow_redirects=True, timeout=self.timeout)
            if resp.status_code == 200:
                final_url = str(resp.url)
                title_m = re.search(r"<title[^>]*>(.*?)</title>", resp.text, re.I | re.S)
                title = re.sub(r"\s+", " ", html.unescape(title_m.group(1))).strip() if title_m else ""
                md_content = convert_html_to_markdown(resp.text, url=final_url, title=title)
                worthy, _ = is_cpt_worthy_content(final_url, md_content, min_words=self.min_words)
                if worthy:
                    # Deteksi konten terpotong / Unhydrated SPA Mismatch (Auto-fallback ke Tier 2)
                    words = md_content.split()
                    spa_markers = ("__NEXT_DATA__", "window.__INITIAL_STATE__", "__NUXT__", "window.__remixContext")
                    if any(m in resp.text for m in spa_markers) and len(words) < 120:
                        return None

                    tail = md_content[-250:].lower()
                    trunc_markers = ("baca selengkapnya", "halaman selanjutnya", "halaman berikutnya", "baca kelanjutannya", "bersambung ke")
                    if any(tm in tail for tm in trunc_markers):
                        return None

                    return final_url, md_content, title
        except Exception:
            pass
        return None

    async def _crawl_single_article(
        self, article: Dict[str, str], client: httpx.AsyncClient, playwright_browser, idx: int, total: int
    ) -> Dict:
        target_url = article.get("decoded_url") or article.get("link", "")
        raw_url = article.get("link", "")
        source = article.get("source", "Media")
        title = re.sub(r"\s+", " ", html.unescape(article.get("title", ""))).strip()
        pub_date = article.get("pub_date", "")

        async with self.semaphore:
            try:
                # ---------------- TIER 1: FAST-PATH ----------------
                t0 = time.time()
                tier1_res = await self._fetch_tier1_fastpath(client, target_url)
                if tier1_res:
                    final_url, md_text, p_title = tier1_res
                    elapsed_ms = (time.time() - t0) * 1000
                    words = len(md_text.split())
                    print(f"[{idx}/{total}] [TIER 1 - FAST PATH] ({elapsed_ms:.0f}ms | {words} kata) [{source}] {target_url[:75]}...")
                    return {
                        "url": final_url, "raw_url": raw_url, "title": p_title or title, "source": source,
                        "pub_date": pub_date, "tier": "TIER1_FAST_PATH", "content": md_text, "word_count": words, "status": "SUCCESS",
                    }

                # ---------------- TIER 2: PLAYWRIGHT FALLBACK ----------------
                t0 = time.time()
                final_url = target_url
                md_text = ""
                status = "SUCCESS"
                page_title = title
                context = None
                page = None

                try:
                    context = await playwright_browser.new_context(
                        user_agent=self.http_headers["User-Agent"], viewport={"width": 1920, "height": 1080}, ignore_https_errors=True
                    )
                    await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
                    page = await context.new_page()

                    await page.goto(target_url, wait_until="domcontentloaded", timeout=self.timeout * 1000)

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
                    raw_t = await page.title()
                    if raw_t:
                        page_title = re.sub(r"\s+", " ", html.unescape(raw_t)).strip()

                    css_path, is_def = get_css_selector_for_url(final_url, self.css_paths_map, self.default_css_path, silent=True)

                    eval_js = """(css) => {
                        let el = document.querySelector(css);
                        if (el) return el.innerHTML;
                        let nodes = document.querySelectorAll(css);
                        if (nodes.length > 0) return Array.from(nodes).map(n => n.innerHTML).join('\\n');
                        let sem = document.querySelector('article, main, .article-content');
                        return sem ? sem.innerHTML : (document.body ? document.body.innerHTML : '');
                    }"""

                    async def _extract_html():
                        if css_path == "body":
                            return await page.content()
                        res = await page.evaluate(eval_js, css_path)
                        return res if (res and len(res.strip()) >= 100) else await page.content()

                    try:
                        raw_html = await _extract_html()
                    except Exception:
                        await page.wait_for_timeout(1500)
                        final_url = page.url
                        raw_html = await _extract_html()

                    md_text = convert_html_to_markdown(raw_html, url=final_url, title=page_title)
                    worthy, reason = is_cpt_worthy_content(final_url, md_text, min_words=self.min_words)
                    status = "SUCCESS" if worthy else f"FILTERED: {reason}"

                    elapsed_ms = (time.time() - t0) * 1000
                    words = len(md_text.split()) if md_text else 0
                    tag = "[TIER 2 - PLAYWRIGHT]" if status == "SUCCESS" else "[QUALITY GATE FILTERED]"
                    print(f"[{idx}/{total}] {tag} ({elapsed_ms:.0f}ms | {words} kata) [{source}] {final_url[:70]}...")

                except Exception as e:
                    status = f"ERROR: {e}"
                    print(f"[{idx}/{total}] [CRAWL ERROR] {e} | {target_url[:70]}")
                finally:
                    if page:
                        try: await page.close()
                        except Exception: pass
                    if context:
                        try: await context.close()
                        except Exception: pass

                return {
                    "url": final_url, "raw_url": raw_url, "title": page_title or title, "source": source,
                    "pub_date": pub_date, "tier": "TIER2_PLAYWRIGHT", "content": md_text if status == "SUCCESS" else "",
                    "word_count": len(md_text.split()) if status == "SUCCESS" else 0, "status": status,
                }
            except Exception as outer_e:
                print(f"[{idx}/{total}] [WORKER ERROR] {outer_e} | {target_url[:70]}")
                return {
                    "url": target_url, "raw_url": raw_url, "title": title, "source": source,
                    "pub_date": pub_date, "tier": "ERROR", "content": "", "word_count": 0, "status": f"ERROR: {outer_e}",
                }

    async def crawl_articles(self, articles: List[Dict[str, str]]) -> List[Dict]:
        """Menjalankan crawling asinkron paralel untuk seluruh daftar artikel."""
        from playwright.async_api import async_playwright

        print(f"\n[*] Memulai Hybrid Async Pool (Concurrency: {self.concurrency}, Headless: {self.headless})...")
        limits = httpx.Limits(max_connections=max(self.concurrency * 2, 20), max_keepalive_connections=self.concurrency)

        async with httpx.AsyncClient(timeout=self.timeout, limits=limits, verify=False) as http_client:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
                tasks = [self._crawl_single_article(art, http_client, browser, idx, len(articles)) for idx, art in enumerate(articles, 1)]
                raw_results = await asyncio.gather(*tasks, return_exceptions=True)
                await browser.close()

        results = []
        for idx, res in enumerate(raw_results, 1):
            if isinstance(res, Exception):
                art = articles[idx - 1]
                results.append({
                    "url": art.get("decoded_url") or art.get("link", ""),
                    "raw_url": art.get("link", ""),
                    "title": art.get("title", ""),
                    "source": art.get("source", ""),
                    "pub_date": art.get("pub_date", ""),
                    "tier": "ERROR",
                    "content": "",
                    "word_count": 0,
                    "status": f"ERROR: {res}",
                })
            else:
                results.append(res)
        return results


# ==============================================================================
# 6. PIPELINE EXPORT & AUDIT REPORTING (Opsi 5)
# ==============================================================================

def export_dataset(
    results: List[Dict],
    deduplicator: SemanticDeduplicator,
    output_path: str,
    output_format: str = "all",
    output_mode: str = "each",
    topic: str = "",
    when: str = "",
    total_time_sec: float = 0.0,
):
    """Menyimpan hasil crawling bersih ke format Markdown (1 artikel 1 file .md atau merged), JSONL, dan Audit Log."""
    clean_path = output_path.rstrip("/\\")
    if clean_path.endswith((".md", ".jsonl", ".log", ".txt")):
        base = os.path.splitext(os.path.basename(clean_path))[0]
        parent_dir = os.path.dirname(os.path.abspath(clean_path)) or "."
    else:
        base = os.path.basename(clean_path)
        parent_dir = os.path.dirname(os.path.abspath(clean_path)) or "."

    # Jika mode 'each' atau 'both', simpan ke subfolder dataset khusus agar rapi
    if output_mode in ("each", "both"):
        dataset_dir = os.path.join(parent_dir, base)
    else:
        dataset_dir = parent_dir
    os.makedirs(dataset_dir, exist_ok=True)

    jsonl_file = os.path.join(dataset_dir, f"{base}.jsonl")
    log_file = os.path.join(dataset_dir, f"{base}.log")
    merged_md_file = os.path.join(dataset_dir if output_mode in ("each", "both") else parent_dir, f"{base}.md" if output_mode == "merge" else f"{base}_merged.md")

    valid_cpt = [r for r in results if r["status"] == "SUCCESS" and r["content"]]
    failed_or_filtered = [r for r in results if r["status"] != "SUCCESS" or not r["content"]]

    unique_items, duplicate_items = [], []
    for item in valid_cpt:
        is_dup, d_info = deduplicator.check_duplicate(item["url"], item["title"], item["source"], item["content"])
        if is_dup:
            item["status"] = f"FILTERED: DUPLICATE ({d_info['similarity_score']}% serupa dengan {d_info['matched_source']})"
            item["duplicate_info"] = d_info
            duplicate_items.append(item)
            print(f"[DUPLICATE DROPPED] Sim: {d_info['similarity_score']}% | [{item['source']}] -> [{d_info['matched_source']}] {item['url'][:70]}")
        else:
            unique_items.append(item)

    # 1. Export Markdown
    if output_format in ("md", "all"):
        # Mode EACH: 1 artikel = 1 file .md terpisah
        if output_mode in ("each", "both"):
            for idx, it in enumerate(unique_items, 1):
                domain = urlparse(it["url"]).netloc.replace("www.", "")
                domain_slug = re.sub(r"[^\w\-_\.]", "_", domain).strip("_") or "article"
                title_slug = re.sub(r"[^\w\s-]", "", it.get("title", "")).strip().lower()
                title_slug = re.sub(r"[-\s]+", "_", title_slug)[:45].strip("_")

                file_name = f"article_{idx:03d}_{domain_slug}_{title_slug}.md" if title_slug else f"article_{idx:03d}_{domain_slug}.md"
                file_path = os.path.join(dataset_dir, file_name)

                body = re.sub(r"^#\s+[^\n]+\n+", "", it["content"].strip()) if it["content"].strip().startswith("# ") else it["content"].strip()
                doc = (
                    f"# {it['title']}\n\n"
                    f"> **Sumber:** [{it['source']}]({it['url']})\n"
                    f"> **Tanggal Publikasi:** {it.get('pub_date', '-')}\n"
                    f"> **Jalur Ekstraksi:** `{it['tier']}` | **Jumlah Kata:** {it['word_count']} kata\n\n"
                    f"{body}\n"
                )
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(doc)
            print(f"[OK] {len(unique_items)} file artikel Markdown (1 artikel 1 file .md) disimpan di: {os.path.abspath(dataset_dir)}")

        # Mode MERGE: gabungkan semua artikel ke satu file .md
        if output_mode in ("merge", "both"):
            docs = []
            for it in unique_items:
                body = re.sub(r"^#\s+[^\n]+\n+", "", it["content"].strip()) if it["content"].strip().startswith("# ") else it["content"].strip()
                docs.append(f"# {it['title']}\n\n> **Sumber:** [{it['source']}]({it['url']})\n> **Tanggal Publikasi:** {it.get('pub_date', '-')}\n> **Jalur Ekstraksi:** `{it['tier']}` | **Jumlah Kata:** {it['word_count']} kata\n\n{body}")
            with open(merged_md_file, "w", encoding="utf-8") as f:
                f.write("\n\n---\n\n".join(docs) + "\n")
            print(f"[OK] Dataset Markdown gabungan disimpan ke: {os.path.abspath(merged_md_file)}")

    # 2. Export JSONL
    if output_format in ("jsonl", "all"):
        with open(jsonl_file, "w", encoding="utf-8") as f:
            for idx, it in enumerate(unique_items, 1):
                rec = {
                    "id": f"cpt_doc_{idx:05d}", "title": it["title"], "url": it["url"], "source": it["source"],
                    "published_at": it.get("pub_date", ""), "tier": it["tier"], "word_count": it["word_count"],
                    "content": it["content"], "crawled_at": datetime.now().isoformat(),
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[OK] Dataset JSONL disimpan ke: {jsonl_file}")

    # 3. Export Log
    tot_words = sum(it["word_count"] for it in unique_items)
    t1_cnt = sum(1 for it in unique_items if it["tier"] == "TIER1_FAST_PATH")
    t2_cnt = sum(1 for it in unique_items if it["tier"] == "TIER2_PLAYWRIGHT")

    with open(log_file, "w", encoding="utf-8") as f:
        f.write(
            f"=== PIPELINE AUDIT REPORT & QUALITY LOG ===\n"
            f"Waktu Eksekusi       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Topik Pencarian      : {topic or 'Direct URLs'}\n"
            f"Total URL Diproses   : {len(results)}\n"
            f"Total Lolos CPT Bersih: {len(unique_items)} artikel ({tot_words:,} kata)\n"
            f"  - Jalur Tier 1 (Fast-Path) : {t1_cnt} artikel\n"
            f"  - Jalur Tier 2 (Playwright): {t2_cnt} artikel\n"
            f"Total Duplikat Dieliminasi : {len(duplicate_items)} artikel\n"
            f"Total Ditolak Quality Gate : {len(failed_or_filtered)} artikel\n"
            f"Total Durasi Eksekusi: {total_time_sec:.2f} detik\n\n"
        )
        if duplicate_items:
            f.write("--- DAFTAR ARTIKEL DUPLIKAT (DIELIMINASI) ---\n")
            for dup in duplicate_items:
                inf = dup["duplicate_info"]
                f.write(f"• [{dup['source']}] {dup['url']} -> [{inf['matched_source']}] ({inf['similarity_score']}%)\n")
        if failed_or_filtered:
            f.write("\n--- DAFTAR ARTIKEL DITOLAK / GAGAL ---\n")
            for flt in failed_or_filtered:
                f.write(f"• {flt.get('url') or flt.get('raw_url')}: {flt['status']}\n")
    print(f"[OK] Audit Quality Log disimpan ke: {log_file}")

    print("\n" + "=" * 65)
    print("           RINGKASAN EKSEKUTIF PIPELINE CRAWLER")
    print("=" * 65)
    print(f"Topik Berita       : {topic or 'URLs'}")
    print(f"Total Diproses     : {len(results)} artikel | Bersih: {len(unique_items)} artikel ({tot_words:,} kata)")
    print(f"Rasio Jalur        : Fast-Path: {t1_cnt} | Playwright: {t2_cnt}")
    print(f"Duplikat Dieliminasi: {len(duplicate_items)} | Ditolak: {len(failed_or_filtered)}")
    if total_time_sec > 0:
        print(f"Kecepatan Pipeline : {total_time_sec:.2f} detik ({len(results)/total_time_sec:.2f} artikel/detik)")
    print("=" * 65 + "\n")


# ==============================================================================
# 7. MAIN ENTRYPOINT (CLI)
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Unified Pipeline Orchestrator (Ponytail Streamlined)")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("-t", "--topic", "-q", "--query", help="Topik berita Google News")
    src.add_argument("-u", "--urls", help="Path file teks berisi daftar URL kustom")
    src.add_argument("--url", help="Satu URL langsung yang ingin diuji/diekstrak")

    parser.add_argument("-w", "--when", default="7d", help="Filter waktu kebaruan (1d, 7d, 30d). Default: 7d")
    parser.add_argument("-l", "--limit", type=int, default=30, help="Batas artikel. Default: 30")
    parser.add_argument("-o", "--output", default="Scrapper/output/dataset_cpt", help="Path/nama output dataset. Default: Scrapper/output/dataset_cpt")
    parser.add_argument("-f", "--format", choices=["md", "jsonl", "all"], default="all", help="Format output. Default: all")
    parser.add_argument("--output-mode", choices=["each", "merge", "both"], default="each", help="Mode output Markdown: 'each' (1 file .md per artikel), 'merge', atau 'both'. Default: each")
    parser.add_argument("-c", "--concurrency", type=int, default=8, help="Batas paralel worker. Default: 8")
    parser.add_argument("-s", "--sim-threshold", type=float, default=0.80, help="Ambang batas kemiripan (0.0-1.0). Default: 0.80")
    parser.add_argument("--css-paths", default="Scrapper/sample_css_paths.csv", help="Path CSV mapping CSS selector")
    parser.add_argument("--default-css", default="body", help="Default CSS selector. Default: 'body'")
    parser.add_argument("--min-words", type=int, default=25, help="Minimal kata CPT Gatekeeper. Default: 25")
    parser.add_argument("--timeout", type=int, default=15, help="Timeout per artikel dalam detik. Default: 15")
    parser.add_argument("--headful", action="store_true", help="Jalankan browser terlihat (GUI)")

    args = parser.parse_args()
    start_time = time.time()
    css_map = load_css_paths(args.css_paths)
    print(f"[*] Memuat {len(css_map)} pemetaan CSS selector dari {args.css_paths}")

    articles: List[Dict[str, str]] = []
    if args.topic:
        raw_arts = fetch_google_news_rss(args.topic, when=args.when, limit=args.limit)
        articles = batch_decode_google_news_urls(raw_arts) if raw_arts else []
    elif args.url:
        u = args.url.strip()
        articles = [{"title": "", "link": u, "source": "Single Target URL", "pub_date": "", "decoded_url": u}]
        print(f"[*] Target uji coba 1 URL langsung: {u}")
    elif args.urls:
        if not os.path.isfile(args.urls):
            print(f"[Error] File '{args.urls}' tidak ditemukan.")
            return
        with open(args.urls, "r", encoding="utf-8") as f:
            articles = [{"title": "", "link": u, "source": "Custom URL", "pub_date": "", "decoded_url": u} for u in (line.strip() for line in f) if u and not u.startswith("#") and u.lower() != "url"][:args.limit]
        print(f"[*] Memuat {len(articles)} URL dari {args.urls}")

    if not articles:
        print("[!] Daftar artikel kosong.")
        return

    crawler = HybridAsyncCrawler(
        css_paths_map=css_map, default_css_path=args.default_css, concurrency=args.concurrency,
        timeout=args.timeout, min_words=args.min_words, headless=not args.headful,
    )
    results = asyncio.run(crawler.crawl_articles(articles))
    dedup = SemanticDeduplicator(threshold=args.sim_threshold)
    export_dataset(
        results, dedup, args.output, output_format=args.format, output_mode=args.output_mode,
        topic=args.topic or "", when=args.when, total_time_sec=time.time() - start_time
    )


if __name__ == "__main__":
    main()
