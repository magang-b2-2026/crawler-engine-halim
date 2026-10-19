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


def clean_canonical_url(url: str) -> str:
    """Membersihkan URL dari parameter tracking (utm_*, ref, fbclid) dan menormalisasi skema untuk deduplikasi kanonikal."""
    if not url or not url.strip():
        return ""
    try:
        parsed = urlparse(url.strip())
        q_params = urllib.parse.parse_qsl(parsed.query)
        clean_params = [
            (k, v) for k, v in q_params
            if not k.lower().startswith("utm_")
            and k.lower() not in ("ref", "ref_src", "fbclid", "gclid", "amp", "preview", "_gl", "source")
        ]
        new_query = urllib.parse.urlencode(clean_params)
        clean_netloc = parsed.netloc.lower().removeprefix("www.")
        clean_path = parsed.path.rstrip("/")
        return urllib.parse.urlunparse(("https", clean_netloc, clean_path, "", new_query, ""))
    except Exception:
        return url.strip()


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

MEDIA_SUFFIX_REGEX = re.compile(
    r"\s+[-–—|•]\s+(?:"
    r"ANTARA\s+News(?:\s+[A-Za-z0-9]+){0,3}"
    r"|ANTARA"
    r"|detik[A-Za-z0-9]*"
    r"|detik\.com"
    r"|Kompas(?:\.com|\.id)?"
    r"|Tempo(?:\.co)?"
    r"|CNN\s+Indonesia"
    r"|CNBC\s+Indonesia"
    r"|Tribunnews(?:\.com)?"
    r"|Tribun\s+[A-Za-z0-9]+(?:\s+[A-Za-z0-9]+)?"
    r"|Liputan6(?:\.com)?"
    r"|RRI(?:\s+[A-Za-z0-9]+){0,3}(?:\.co\.id)?"
    r"|InfoPublik(?:\s+id)?"
    r"|Kumparan[A-Za-z0-9]*"
    r"|Bisnis(?:\.com)?"
    r"|JawaPos(?:\.com)?"
    r"|Media\s+Indonesia"
    r"|BeritaSatu(?:\.com)?"
    r"|Suara(?:\.com)?"
    r"|Merdeka(?:\.com)?"
    r"|Sindonews(?:\.com)?"
    r"|IDN\s+Times"
    r"|JPNN(?:\.com)?"
    r"|VIVA(?:\.co\.id)?"
    r"|Kementerian\s+[A-Za-z0-9\s]+"
    r"|Pemerintah\s+[A-Za-z0-9\s]+"
    r"|Pemprov\s+[A-Za-z0-9\s]+"
    r"|Pemkab\s+[A-Za-z0-9\s]+"
    r"|Disway"
    r"|Fajar"
    r"|Koran\s+Jakarta"
    r"|Tirto\.id"
    r"|Katadata(?:\.co\.id)?"
    r")\s*$",
    re.IGNORECASE,
)


def clean_headline_title(title: str, source: str = "") -> str:
    """Membersihkan judul dari akhiran/suffix portal media (e.g. ' - ANTARA News Jateng', ' - detikNews')."""
    if not title:
        return ""
    t = re.sub(r"\s+", " ", html.unescape(title)).strip()
    if source and len(source.strip()) >= 3:
        src_clean = source.strip()
        t = re.sub(r"\s+[-–—|•]\s+" + re.escape(src_clean) + r"\s*$", "", t, flags=re.I)
    t = MEDIA_SUFFIX_REGEX.sub("", t).strip()
    t = re.sub(r"\s+[-–—|•]\s*$", "", t).strip()
    return t


def extract_clean_headline(html_content: str, fallback_title: str = "", source: str = "") -> str:
    """Mengekstrak judul/headline artikel paling presisi dari dokumen HTML.
    Memprioritaskan <meta property='og:title'>, <meta name='twitter:title'>, dan <h1>
    di atas tag <title> generik portal, serta membersihkan akhiran media."""
    if not html_content:
        return clean_headline_title(fallback_title, source=source)

    candidates = []

    # 1. Cek meta og:title dan twitter:title
    og_m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html_content, re.I)
    if not og_m:
        og_m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']', html_content, re.I)
    if og_m:
        candidates.append(og_m.group(1))

    tw_m = re.search(r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']', html_content, re.I)
    if not tw_m:
        tw_m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:title["\']', html_content, re.I)
    if tw_m:
        candidates.append(tw_m.group(1))

    # 2. Cek tag <h1>
    for h1_m in re.finditer(r'<h1[^>]*>(.*?)</h1>', html_content, re.I | re.S):
        h1_text = re.sub(r'<[^>]+>', '', h1_m.group(1))
        h1_text = re.sub(r'\s+', ' ', h1_text).strip()
        if len(h1_text) >= 15:
            candidates.append(h1_text)
            break

    # 3. Cek tag <title> (ambil semua <title>, saring nama situs pendek jika ada yang lebih panjang)
    titles = []
    for t_m in re.finditer(r'<title[^>]*>(.*?)</title>', html_content, re.I | re.S):
        t_text = re.sub(r'<[^>]+>', '', t_m.group(1))
        t_text = re.sub(r'\s+', ' ', t_text).strip()
        if t_text:
            titles.append(t_text)

    titles.sort(key=lambda s: len(s), reverse=True)
    candidates.extend(titles)

    # 4. Fallback title
    if fallback_title:
        candidates.append(fallback_title)

    GENERIC_NAMES = {
        "berita", "home", "index", "indeks", "kementerian pekerjaan umum", "pu.go.id",
        "detikcom", "detiknews", "kompas.com", "antara news", "portal berita", "artikel"
    }

    for cand in candidates:
        cleaned = clean_headline_title(cand, source=source)
        if not cleaned or len(cleaned) < 10:
            continue
        c_low = cleaned.lower().strip()
        if c_low in GENERIC_NAMES:
            continue
        if any(w in c_low for w in ("just a moment", "attention required", "security check", "403 forbidden", "access denied", "page not found")):
            continue
        return cleaned

    return clean_headline_title(fallback_title, source=source)


def clean_html_embedded_noise(html_content: str) -> str:
    """Membersihkan kontainer video/multimedia embed, banner paywall, dan menormalisasi drop-cap dari struktur DOM."""
    if not html_content or "<" not in html_content:
        return html_content
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")
        found = False

        # 1. Normalisasi drop-cap (misal: Tempo drop-cap <span class="tempo-dropcap"><strong>D</strong></span>UGAAN)
        for dc in soup.select(".tempo-dropcap, span[style*='font-size: 4rem'], span[style*='font-size:4rem']"):
            dc_text = dc.get_text(strip=True)
            dc.replace_with(dc_text)
            found = True

        # 2. Pembersihan banner paywall / promosi langganan (misal: Tempo+, Kompas.id)
        paywall_selectors = [
            "div[class*='bg-black']", "div:has(> img[src*='paywall'])", ".paywall-content",
            "div[class*='paywall']", "div[class*='premium-box']"
        ]
        for el in soup.select(", ".join(paywall_selectors)):
            txt_low = el.get_text().lower()
            if any(w in txt_low for w in ("tempo+", "berlangganan", "benefit", "baca cerita lengkapnya", "kompas.id")):
                el.decompose()
                found = True

        # 3. Pembersihan kontainer video/multimedia embed dan teaser caption sebelumnya
        video_selectors = [
            "div.noncontent", "div.video20detik", "a.video20detik", ".embed_video",
            ".video-embed", ".embed-video", "iframe[src*='20.detik.com']",
            "iframe[src*='youtube']", "div[class*='video-box']", "div[class*='detail__video']"
        ]
        for el in soup.select(", ".join(video_selectors)):
            found = True
            prev = el.find_previous_sibling()
            while prev and prev.name and prev.get_text(strip=True) == "":
                prev = prev.find_previous_sibling()
            if prev and prev.name == "p":
                prev_text = prev.get_text(strip=True)
                if (prev.find(["strong", "b"]) or len(prev_text) < 120) and not prev_text.endswith((".", "!", "?")):
                    prev.decompose()
            el.decompose()

        # 4. Pembersihan header, footer, navigasi, sidebar, dan widget rekomendasi/komentar
        structural_noise = [
            "body > header", "header#header", "header.site-header", "header.main-header", "div.main-header",
            "ul.main-header__top-details-list", "div.top-bar", "div.information__content",
            "footer", "nav", "aside", ".sidebar", "div.sidebar", "div.sidebar__single", "div.sidebar__comments",
            "div[class*='sidebar-right']", "div[class*='sidebar-left']", "div.widget", "div.widget-area",
            "div.baca-juga", "div.berita-terkait", "div.berita-terbaru", "div.related-articles", "div.related-news",
            "div.popular-posts", "div.trending-news", "div.comments-area", "div.comment-respond", "#comments",
            "div.discussion-section", "section.comments", "div.social-share", "div.share-box", "div.post-share",
            "div.social-links", "ul.social-media", "div.contact-info", "div.info-pemprov", "div.footer-contact",
            "div.share-links", "div.kontak-kami"
        ]
        for el in soup.select(", ".join(structural_noise)):
            el.decompose()
            found = True

        return str(soup) if found else html_content
    except Exception:
        return html_content


def is_standalone_emoji(line: str) -> bool:
    """Mendeteksi apakah sebuah baris teks hanya berisi emoji, ikon multimedia, atau simbol grafis."""
    stripped_no_md = re.sub(r"[\s\*\_\-\#\>\:\(\)\[\]\.\,\;]+", "", line)
    if not stripped_no_md:
        return False
    emoji_cleaned = re.sub(
        r"[\U00010000-\U0010ffff\u200d\ufe0f\u2600-\u27bf\u2300-\u23ff\u2b50\u2b55\u2934\u2935\u25aa\u25ab\u25b6\u25c0\u25fb-\u25fe]",
        "",
        stripped_no_md,
    )
    return len(emoji_cleaned) == 0


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

    # 4B. Normalisasi drop-cap terfragmentasi (misal: "**D**UGAAN" -> "DUGAAN")
    text = re.sub(r"(?:\*\*|__)([A-Za-z])(?:\*\*|__)([A-Za-z]+)", r"\1\2", text)

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

        # A. Eliminasi garis pemisah terisolasi atau baris titik-titik (misal: "....................................", "-------------------")
        if re.match(r"^[.\-_*=~]{3,}$", line_str):
            continue

        # Deteksi pemisah bagian penutup (Berita Terkait, Berita Terbaru, Rekomendasi, Diskusi, Komentar, Kontak Medsos, Kredit Editor)
        # Ketika bagian ini muncul, sisa teks ke bawah adalah widget/kontak/kredit dan harus dipotong (truncate).
        if re.match(
            r"^(?:#+\s*)?(?:berita\s+terbaru|berita\s+terkait|artikel\s+terkait|baca\s+juga\s*:?$|baca\s+artikel\s+lainnya|rekomendasi\s+berita|berita\s+populer|terpopuler|trending\s+topic|pilihan\s+editor|related\s+news|latest\s+news|discussion(?:\s+about\s+this\s+post)?|komentar(?:\s+pembaca)?|\d+\s+komentar|tulis\s+komentar|kirim\s+komentar|informasi\s+(?:seputar|terkait|lebih\s+lanjut)\s+.*?\s+(?:bisa|dapat)\s+diakses(?:\s+melalui)?|dapat\s+diakses\s+melalui|informasi\s+selengkapnya\s+dapat\s+diakses|ikuti\s+media\s+sosial\s+kami|kontak\s+dan\s+media\s+sosial|hubungi\s+kami\s+melalui|saluran\s+resmi\s+kami)\s*:?$",
            line_str,
            re.I,
        ):
            break

        # Baris penutup kredit redaksi mandiri (misal: "Editor:", "Pewarta:", "Fotografer:") di bagian akhir artikel
        if len(clean_lines) >= 2 and re.match(r"^(?:#+\s*)?(?:\*\*|__|\*|_|\\\*)?\s*(?:editor|pewarta|reporter|penulis|kontributor|redaktur|fotografer|sumber)\s*:?\s*$", line_str, re.I):
            break

        # Eliminasi heading/baris identitas instansi, balai kota, kantor bupati, gedung pemerintahan, atau navigasi portal
        if re.match(
            r"^(?:#+\s*)?(?:balai\s+kota|kantor\s+bupati|sekretariat\s+daerah|komplek\s+perkantoran|gedung\s+[A-Za-z0-9\s]+lantai|informasi|ikuti\s+kami|bimas|kontak\s+kami)\s*[A-Za-z0-9\s]*$",
            line_str,
            re.I,
        ) and len(line_str) < 80:
            continue

        # Eliminasi baris alamat jalan & nomor kantor di header/footer
        if re.match(r"^(?:jl\.|jalan)\s+[A-Za-z0-9\s\.\,\-]+(?:no\.\s*\d+|nomor\s*\d+|rt\s*\d+|rw\s*\d+|\d{5})", line_str, re.I) and len(line_str) < 120:
            continue

        # Eliminasi nomor telepon/fax/email kantor terisolasi
        if re.match(r"^(?:telepon|telp|fax|e-?mail)\s*:\s*.*$", line_str, re.I):
            continue

        if line_str.startswith("#"):
            clean_lines.append(line_str)
            continue

        # B. Eliminasi view/hit counter (misal: "Dibaca : 373 Kali", "Views: 1200")
        if re.match(r"^(?:\*\*|__)?\s*(?:dibaca|dilihat|view(?:s|ed)?|reads?|tayang)\s*:\s*\d+.*$", line_str, re.I):
            continue
        if re.match(r"^\d+\s+(?:kali\s+dibaca|views?|reads?)$", line_str, re.I):
            continue

        # Eliminasi inline Sumber atau catatan rilis di akhir baris (misal: "para Kepala OPD beserta jajarannya.\* Sumber: Diskominfosta Bangka Tengah")
        line_str = re.sub(r"\s*(?:[\.\*\\\_]|\b)+\s*sumber\s*:\s*[^\n]+$", ".", line_str, flags=re.I).strip()

        # C. Eliminasi metadata author/uploader CMS (misal: "Diposting Oleh : Newsroom Diskominfosantik -", "Pewarta: ...", "Fotografer: ...", "Editor:")
        if re.match(r"^(?:\*\*|__|\*|_|\\\*)?\s*(?:diposting(?:\s+oleh)?|diterbitkan(?:\s+oleh)?|dipublikasikan(?:\s+pada)?|posted(?:\s+by)?|penulis|pewarta|reporter|editor|kontributor|redaktur|alih\s+bahasa|rilis|tanggal(?:\s+rilis)?|update|fotografer|sumber(?:\s+foto)?)\s*:\s*[^\n]*$", line_str, re.I):
            continue

        # D. Eliminasi rubrik/kategori terisolasi (misal: "PENDIDIKAN", "EKONOMI")
        if (line_str.upper() in RUBRIC_KEYWORDS) or (re.match(r"^[A-Z\s]{3,20}$", line_str) and len(line_str.split()) <= 2):
            continue

        # E. Eliminasi timestamp/tanggal mentah (misal: "Oct 17, 2026 -", "14 Okt 2026 10:18 WIB")
        if re.match(r"^(?:(?:senin|selasa|rabu|kamis|jumat|sabtu|minggu|monday|tuesday|wednesday|thursday|friday|saturday|sunday)[,\s]+)?(?:(?:jan|feb|mar|apr|mei|may|jun|jul|agu|aug|sep|okt|oct|nov|des|dec)[a-z]*|\d{1,2})\s+\d{1,2}[,\s\-]+(?:\d{4})?(?:\s+[-–—|•]\s*)?(?:\s*\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:wib|wita|wit|gmt|utc))?)?\s*[-–—]?$", line_str, re.I):
            continue

        # F. Eliminasi baris dateline terisolasi (misal: "**Jakarta**-", "JAKARTA -")
        if re.match(r"^(?:\*\*|__)?\s*[A-Za-z\s,\.\-/\(\)]{2,30}?(?:\*\*|__)?\s*[-–—]{1,2}\s*(?:\*\*|__)?$", line_str):
            continue

        # G. Eliminasi derau navigasi & CTA sosial media
        if re.match(r"^(?:\*\*|__)?\s*(?:baca\s+juga|simak\s+juga|simak\s+video|pilihan\s+editor|artikel\s+ini\s+telah\s+tayang|tonton\s+video|lihat\s+juga|lire\s+l'article\s+complet|read\s+more|baca\s+selengkapnya)\s*:?", line_str, re.I):
            continue
        if re.match(r"^(?:\*\*|__)?\s*(?:dapatkan\s+update\s+berita|ikuti\s+saluran\s+whatsapp|simak\s+berita\s+terbaru\s+di|(?:install|unduh|download)\s+aplikasi|klik\s+di\s+sini\s+untuk\s+berlangganan|bergabunglah\s+dengan\s+saluran|bagikan\s+pemikiran|kirim\s+komentar)", line_str, re.I):
            continue

        # H. Eliminasi caption gambar & kredit foto
        if re.search(r"(?:foto|photo|dok(?:umen)?|ilustrasi|sumber\s+foto|fotografer)\s*:\s*[A-Za-z0-9/\.\s\-\*\_]+$", line_str, re.I) and len(line_str) < 300:
            continue
        if re.match(r"^\(?(?:foto|photo|dok(?:umen)?|ilustrasi|fotografer)\s*[:/]\s*[^\n\)]+\)?$", line_str, re.I):
            continue

        # I. Eliminasi copyright, disclaimer anti-crawler, arsip paywall, sindikasi, dan CTA donasi
        if re.search(r"(?:dilarang keras mengambil|copyright\s*(?:©|\(c\)|&copy;)|hak cipta dilindungi|all rights reserved|artikel ini telah masuk arsip|(?:berita|artikel|konten)\s+ini\s+telah\s+(?:tayang|terbit|dimuat)\s+di|crawling atau pengindeksan otomatis untuk ai|simak breaking news|donasi lewat tautan|ekspedisi kata ke nyata|mari bantu sesama|rekening donasi|berlangganan tempo|akses edisi mingguan dari tahun|akses penuh seluruh artikel tempo\+|anda mendukung independensi jurnalisme tempo|lihat benefit lainnya|fitur baca cepat di edisi mingguan|baca cerita lengkapnya|(?:install|unduh|download)\s+aplikasi|bagikan\s+pemikiran|kirim\s+komentar)", line_str, re.I):
            continue

        # J. Eliminasi hashtag kampanye / slogan / media sosial (misal: "**#SigapMembangunNegeriUntukRakyat**", "#KemenPU")
        if re.match(r"^(?:\*\*|__)?\s*#[A-Za-z0-9_]{3,}(?:\s+#[A-Za-z0-9_]{3,})*\s*(?:\*\*|__)?$", line_str):
            continue

        # K. Eliminasi daftar kontak media sosial resmi dengan/tanpa emoji (misal: "🌐 Website: pu.go.id", "📘 Facebook: ...", "X @banten_pemprov", "🎵 TikTok: @...")
        if re.match(r"^(?:[^\w\s]\s*)?(?:\*\*|__)?\s*(?:website|situs|facebook|fb|instagram|ig|x|twitter|tiktok|youtube|yt|threads|telegram|linkedin|email|e-mail)\s*[:@\s]\s*[^\n]+$", line_str, re.I):
            continue

        # L. Eliminasi baris emoji terisolasi (misal: "💡", "▶️", "👉")
        if is_standalone_emoji(line_str):
            continue

        # M. Eliminasi baris teaser video / multimedia (misal: "💡 **...**", "▶️ **...**", "**Simak Video...**", "**Tonton Video...**")
        if re.match(r"^(?:\*\*|__)?\s*(?:💡|▶️|video\s*:|simak\s+video|tonton\s+video|saksikan\s+video)", line_str, re.I):
            continue

        # Eliminasi kalimat ajakan tonton YouTube/video di akhir narasi
        line_str = re.sub(r"(?:saksikan|tonton|simak)\s+(?:selengkapnya|video)\s+(?:hanya\s+)?di\s+(?:youtube|yt|saluran)\s+[^\n]+", "", line_str, flags=re.I).strip()
        if not line_str:
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

    # 9. Pembersihan inisial redaksi di akhir teks (misal: (kcm/ard), **(anl/ega)**, (dna/dna), (ant/red), (Hil))
    text = re.sub(r"(?:\s+|^)(?:\*\*|__)?\s*\(\s*[a-zA-Z0-9]{2,5}\s*/\s*[a-zA-Z0-9]{2,5}\s*\)\s*(?:\*\*|__)?\s*$", "", text.strip(), flags=re.I)
    text = re.sub(r"(?:\s+|^)(?:\*\*|__)?\s*\(\s*(?:ant|red|tim|[a-zA-Z]{3,4})\s*\)\s*(?:\*\*|__)?\s*$", "", text.strip(), flags=re.I)

    # 9B. Pembersihan metadata jurnalistik, inisial institusi, dan teaser promosi di akhir artikel
    temp_lines = text.strip().splitlines()
    changed = True
    while changed and temp_lines:
        changed = False
        last_line = temp_lines[-1].strip()
        if not last_line:
            temp_lines.pop()
            changed = True
            continue
        # Inisial redaksi tersisa di baris terakhir (misal: (kcm/ard), (ant/red), (id 28), (Hil))
        if re.search(r"^(?:\*\*|__)?\s*\(\s*(?:[a-zA-Z0-9]{2,5}\s*/\s*[a-zA-Z0-9]{2,5}|ant|red|tim|[a-zA-Z]{1,4}(?:\s+\d+)?)\s*\)\s*(?:\*\*|__)?$", last_line, re.I):
            temp_lines.pop()
            changed = True
            continue
        # Inisial/kredit institusi media di baris terakhir (misal: Diskominfo/D, Kominfo/Fikri, Setda/A, Humas/B)
        if re.search(r"^(?:\*\*|__|\*|_)?\s*(?:Diskominfo|Kominfo|Humas|Prokopim|Setda|Media\s+Center)\s*(?:[/\\-]\s*[A-Za-z0-9\s]+|\([A-Za-z0-9\s]+\))\s*(?:\*\*|__|\*|_)?$", last_line, re.I):
            temp_lines.pop()
            changed = True
            continue
        # Metadata editor/pewarta/fotografer/sumber di baris terakhir
        if re.match(r"^(?:\*\*|__|\*|_|\\\*)?\s*(?:editor|pewarta|reporter|penulis|kontributor|redaktur|fotografer|foto|photo|sumber|alih\s+bahasa)\s*:\s*.*$", last_line, re.I):
            temp_lines.pop()
            changed = True
            continue
        # Baris label metadata tanpa isi (misal: "Editor:", "Pewarta:")
        if re.match(r"^(?:\*\*|__|\*|_|\\\*)?\s*(?:editor|pewarta|reporter|penulis|kontributor|redaktur|fotografer|sumber)\s*:?\s*$", last_line, re.I):
            temp_lines.pop()
            changed = True
            continue
        # Nama jurnalis/editor mandiri di baris terakhir jika didahului label Editor/Pewarta (misal: "Editor:\n\nZabur Karuru")
        if len(temp_lines) >= 2:
            prev_line = temp_lines[-2].strip()
            if re.match(r"^(?:\*\*|__|\*|_|\\\*)?\s*(?:editor|pewarta|reporter|penulis|kontributor|redaktur|fotografer)\s*:?\s*$", prev_line, re.I):
                temp_lines.pop()  # pop nama editor
                temp_lines.pop()  # pop label editor
                changed = True
                continue
        # Trailing bold teaser tanpa tanda baca penutup kalimat (. ! ? :" .")
        if re.match(r"^(?:\*\*|__)[^\*\_\n]{5,150}(?:\*\*|__)$", last_line) and not re.search(r"[\.!\?\"'](?:\*\*|__)$", last_line):
            temp_lines.pop()
            changed = True
            continue
    text = "\n".join(temp_lines)

    # 10. Normalisasi spasi dan pemisahan antar paragraf Markdown
    # Setiap paragraf naratif terpisah oleh baris kosong (\n\n) sesuai kaidah Markdown/CommonMark untuk CPT LLM
    # Sementara item list berturut-turut (- , * , 1. ), blockquote (> ), dan tabel (| ) tetap rapat
    def is_bullet(s: str) -> bool:
        return bool(re.match(r"^\s*[-*+]\s+", s))

    def is_numbered(s: str) -> bool:
        return bool(re.match(r"^\s*\d+[\.\)]\s+", s))

    def is_quote(s: str) -> bool:
        return s.lstrip().startswith(">")

    def is_table(s: str) -> bool:
        st = s.strip()
        return st.startswith("|") and st.endswith("|")

    non_empty = [l.rstrip() for l in text.splitlines() if l.strip()]
    formatted = []
    in_code = False

    for idx, s in enumerate(non_empty):
        stripped = s.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            formatted.append(s)
            if not in_code and idx < len(non_empty) - 1:
                formatted.append("")
            continue

        formatted.append(s)
        if in_code:
            continue

        if idx < len(non_empty) - 1:
            next_s = non_empty[idx + 1]
            next_stripped = next_s.strip()
            if next_stripped.startswith("```"):
                formatted.append("")
                continue
            if is_bullet(s) and is_bullet(next_s):
                continue
            if is_numbered(s) and is_numbered(next_s):
                continue
            if is_quote(s) and is_quote(next_s):
                continue
            if is_table(s) and is_table(next_s):
                continue
            formatted.append("")

    clean_paras = []
    for line in formatted:
        if not line:
            clean_paras.append("")
            continue
        indent = len(line) - len(line.lstrip(" "))
        indent_str = " " * indent
        collapsed = re.sub(r"[ \t]{2,}", " ", line.lstrip(" "))
        clean_paras.append(indent_str + collapsed)

    text = "\n".join(clean_paras)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def convert_html_to_markdown(html_content: str, url: str = "", title: str = "") -> str:
    """Konversi HTML ke Markdown bersih untuk dataset CPT via Trafilatura / Markdownify, disanitasi untuk training LLM."""
    if not html_content or not html_content.strip():
        return ""

    html_cleaned = clean_html_embedded_noise(html_content)
    raw = html_cleaned if ("<html" in html_cleaned[:300].lower() or "<body" in html_cleaned[:300].lower()) else f"<!DOCTYPE html><html><body>{html_cleaned}</body></html>"
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
            sanitized = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", "", html_cleaned, flags=re.I | re.S)
            res = md(sanitized, heading_style="ATX", strip=["nav", "footer", "aside", "iframe", "form"])
            res = re.sub(r"\n{3,}", "\n\n", res).strip()
            if res and len(res.split()) >= 15:
                raw_md = res
        except Exception:
            pass

    if not raw_md:
        clean_strip = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", "", html_cleaned, flags=re.I | re.S)
        raw_md = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", clean_strip)).strip()

    return sanitize_cpt_text(raw_md, title=title)


BLOCK_PHRASES = (
    "attention required! | cloudflare", "just a moment...", "access denied", "403 forbidden",
    "enable javascript and cookies", "security check to access", "sorry, you have been blocked",
    "error 400 (bad request)", "page not found", "halaman tidak ditemukan", "request rejected",
    "the requested url was rejected", "support id:",
    "performing security verification", "uses a security service to protect against",
    "verifies you are not a bot", "verify you are human", "checking your browser",
    "cloudflare ray id", "ray id:", "laman tidak bisa ditampilkan", "tidak dibolehkan diakses",
    "attack id:", "laman tidak diizinkan",
    "baca selengkapnya dengan berlangganan", "konten ini eksklusif untuk pelanggan",
    "silakan login untuk membaca", "berlangganan kompas.id", "anda telah mencapai batas gratis",
    "berlangganan tempo+", "berlangganan tempo", "akses penuh seluruh artikel tempo+",
    "berita tempo plus", "baca cerita lengkapnya", "anda mendukung independensi jurnalisme tempo",
    "fitur baca cepat di edisi mingguan", "lihat benefit lainnya", "akses edisi mingguan dari tahun",
)
BAD_DOMAINS = ("play.google.com", "apps.apple.com", "accounts.google.com", "facebook.com/login")

PAYWALL_MARKERS = (
    "berlangganan tempo+", "berita tempo plus", "akses edisi mingguan dari tahun",
    "akses penuh seluruh artikel tempo+", "berlangganan kompas.id", "konten ini eksklusif untuk pelanggan",
    "baca selengkapnya dengan berlangganan", "silakan login untuk membaca", "anda telah mencapai batas gratis",
    "lihat benefit lainnya", "anda mendukung independensi jurnalisme tempo", "baca cerita lengkapnya",
)


def is_cpt_worthy_content(url: str, text: str, min_words: int = 25, title: str = "", raw_html: str = "") -> Tuple[bool, str]:
    """Mengevaluasi apakah teks hasil ekstraksi memenuhi standar CPT."""
    domain = urlparse(url).netloc.lower()
    if any(bd in domain for bd in BAD_DOMAINS):
        return False, f"Bukan artikel/dokumen web ({domain})"

    if title:
        t_low = title.lower()
        if any(bp in t_low for bp in ("just a moment...", "attention required", "security check", "403 forbidden", "access denied", "laman tidak")):
            return False, f"Deteksi judul halaman proteksi WAF/Bot ('{title}')"

    cleaned = text.strip()
    if not cleaned:
        return False, "Konten teks kosong"

    words = cleaned.split()
    if len(words) < min_words:
        return False, f"Teks terlalu pendek ({len(words)} kata < batas minimal {min_words} kata)"

    # Hitung kata narasi murni tanpa sintaks gambar markdown (![alt](url)) dan heading
    prose_text = re.sub(r"!\[[^\]]*\]\([^\)]+\)", " ", cleaned)
    prose_text = re.sub(r"^#+[^\n]+", " ", prose_text, flags=re.M)
    prose_words = prose_text.split()
    if len(prose_words) < min_words:
        return False, f"Teks narasi terlalu pendek ({len(prose_words)} kata narasi < batas minimal {min_words} kata)"

    if all(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", line.strip()) for line in cleaned.splitlines() if line.strip()):
        return False, "Deteksi dump alamat IP mentah (bukan artikel informatif)"

    full_low = cleaned.lower()
    for pm in PAYWALL_MARKERS:
        if pm in full_low:
            return False, f"Deteksi stub paywall / konten berbayar terpotong ('{pm}')"

    first_800 = cleaned[:800].lower()
    for phrase in BLOCK_PHRASES:
        if phrase in first_800:
            return False, f"Deteksi halaman blokir WAF / Error screen ('{phrase}')"

    if raw_html:
        h_low = raw_html.lower()
        if ('"isaccessibleforfree": false' in h_low or '"isaccessibleforfree":false' in h_low) and len(words) < 200:
            return False, "Deteksi stub paywall / konten berbayar (Schema.org isAccessibleForFree: false)"
        if any(w in h_low for w in ('class="bg-black', 'class="paywall', 'id="paywall')) and any(w in h_low for w in ('tempo+', 'berlangganan kompas.id')) and len(words) < 200:
            return False, "Deteksi stub paywall terpotong dari kontainer berlangganan"

    # Deteksi dump menu navigasi / daftar hyperlink (bukan artikel narasi)
    lines_non_empty = [l.strip() for l in cleaned.splitlines() if l.strip()]
    if lines_non_empty:
        bullet_lines = [l for l in lines_non_empty if l.startswith(("* ", "+ ", "- ", "• "))]
        avg_words = len(words) / len(lines_non_empty)
        if len(lines_non_empty) >= 6 and (len(bullet_lines) / len(lines_non_empty) > 0.40) and avg_words < 12:
            return False, f"Deteksi dump menu navigasi/daftar link ({len(bullet_lines)}/{len(lines_non_empty)} baris poin)"

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
    """Mengambil daftar artikel berita terverifikasi dari endpoint RSS Google News.
    Mendukung multi-query koma (misal: 'query1, query2') atau auto-ekspansi jika limit > 100."""
    queries = [q.strip() for q in query.split(",") if q.strip()]
    if limit > 100 and len(queries) == 1:
        base = queries[0]
        queries = [
            base,
            f"{base} terintegrasi",
            f"{base} kemiskinan",
            f"{base} dinsos",
            f"{base} pemkab",
            f"{base} indonesia",
        ]

    raw_articles: List[Dict[str, str]] = []
    seen_raw_links: Set[str] = set()

    for q in queries:
        if len(raw_articles) >= limit:
            break
        clean_q = f"{q} when:{when}" if when else q
        rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote_plus(clean_q)}&hl=id&gl=ID&ceid=ID:id"
        print(f"[*] Menghubungi Google News RSS ('{q}'): {rss_url}")
        try:
            resp = httpx.get(rss_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            items = ET.fromstring(resp.content).findall(".//item")
            print(f"[*] Ditemukan {len(items)} artikel di feed Google News untuk '{q}'.")
            for it in items:
                link = (it.findtext("link") or "").strip()
                if link and link not in seen_raw_links:
                    seen_raw_links.add(link)
                    raw_articles.append({
                        "title": (it.findtext("title") or "").strip(),
                        "link": link,
                        "source": (it.findtext("source") or "Media Nasional").strip(),
                        "pub_date": (it.findtext("pubDate") or "").strip(),
                        "decoded_url": "",
                    })
                    if len(raw_articles) >= limit:
                        break
        except Exception as e:
            print(f"[!] Gagal mengambil Google News RSS '{q}': {e}")

    return raw_articles[:limit]


def batch_decode_google_news_urls(articles: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Mendekode token URL Google News RSS ke URL asli penerbit dan membuang URL kanonikal duplikat sebelum crawl."""
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

    # Pre-crawl Canonical URL Deduplication
    unique_articles = []
    seen_canonical: Set[str] = set()
    for a in articles:
        target = a.get("decoded_url") or a.get("link", "")
        can = clean_canonical_url(target)
        if can and can not in seen_canonical:
            seen_canonical.add(can)
            a["canonical_url"] = can
            unique_articles.append(a)

    dups_count = len(articles) - len(unique_articles)
    if dups_count > 0:
        print(f"[DEDUP] {dups_count} URL duplikat/tracking berhasil dieliminasi sebelum proses crawling.")

    return unique_articles


# ==============================================================================
# 5. HYBRID TWO-TIER ASYNC CRAWLER (Opsi 1 & Opsi 2)
# ==============================================================================

async def solve_captcha_via_bot(url: str, solver_url: str, timeout: float = 45.0) -> Optional[str]:
    """Helper microservice delegator untuk memanggil komdigi-bot guna bypass CAPTCHA/Turnstile."""
    if not solver_url or not solver_url.strip():
        return None
    endpoint = solver_url.strip().rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{endpoint}/solve", json={"url": url})
            if r.status_code not in (200, 202):
                return None
            job_id = r.json().get("job_id")
            if not job_id:
                return None

            t_start = time.time()
            while time.time() - t_start < timeout:
                await asyncio.sleep(1.5)
                poll_r = await client.get(f"{endpoint}/job/{job_id}")
                if poll_r.status_code == 200:
                    j_data = poll_r.json()
                    st = j_data.get("status")
                    if st == "done":
                        res = j_data.get("result") or {}
                        if res.get("status") == "pass":
                            return res.get("html") or None
                    elif st == "failed":
                        break
    except Exception:
        pass
    return None


class HybridAsyncCrawler:
    """Crawler Asinkron Tiga Tingkat: Tier 1 (Fast-Path HTTPX) + Tier 2 (Playwright Stealth) + Tier 3 (komdigi-bot Solver)."""

    def __init__(
        self,
        css_paths_map: Dict[str, str],
        default_css_path: str = "body",
        concurrency: int = 8,
        timeout: int = 15,
        min_words: int = 25,
        headless: bool = True,
        bot_solver_url: str = "",
    ):
        self.css_paths_map = css_paths_map
        self.default_css_path = default_css_path
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)
        self.timeout = timeout
        self.min_words = min_words
        self.headless = headless
        self.bot_solver_url = bot_solver_url.strip().rstrip("/")

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
        self, client: httpx.AsyncClient, url: str, fallback_title: str = "", source: str = ""
    ) -> Optional[Tuple[str, str, str, str]]:
        if "google.com" in url:
            return None
        try:
            resp = await client.get(url, headers=self.http_headers, follow_redirects=True, timeout=self.timeout)
            if resp.status_code == 200:
                final_url = str(resp.url)
                title = extract_clean_headline(resp.text, fallback_title=fallback_title, source=source)
                md_content = convert_html_to_markdown(resp.text, url=final_url, title=title)
                worthy, reason = is_cpt_worthy_content(final_url, md_content, min_words=self.min_words, title=title, raw_html=resp.text)

                # Deteksi konten terpotong / Unhydrated SPA Mismatch (Auto-fallback ke Tier 2)
                words = len(md_content.split())
                spa_markers = ("__NEXT_DATA__", "window.__INITIAL_STATE__", "__NUXT__", "window.__remixContext", "__next_f", 'id="__next"')
                has_spa = any(m in resp.text for m in spa_markers) and words < 120

                tail = md_content[-250:].lower()
                trunc_markers = ("baca selengkapnya", "halaman selanjutnya", "halaman berikutnya", "baca kelanjutannya", "bersambung ke", "berlangganan tempo", "tempo+", "baca cerita lengkapnya")
                has_trunc = any(tm in tail for tm in trunc_markers)

                if has_spa or has_trunc:
                    return None

                if worthy:
                    return final_url, md_content, title, "SUCCESS"
                else:
                    return final_url, "", title, f"FILTERED: {reason}"
        except Exception:
            pass
        return None

    async def _crawl_single_article_worker(
        self, article: Dict[str, str], client: httpx.AsyncClient, playwright_browser, idx: int, total: int
    ) -> Dict:
        target_url = article.get("decoded_url") or article.get("link", "")
        raw_url = article.get("link", "")
        source = article.get("source", "Media")
        raw_title = article.get("title", "")
        title = clean_headline_title(raw_title, source=source)
        pub_date = article.get("pub_date", "")

        # ---------------- TIER 1: FAST-PATH ----------------
        t0 = time.time()
        tier1_res = await self._fetch_tier1_fastpath(client, target_url, fallback_title=title, source=source)
        if tier1_res:
            final_url, md_text, p_title, t1_status = tier1_res
            clean_res_title = clean_headline_title(p_title or title, source=source)
            elapsed_ms = (time.time() - t0) * 1000
            words = len(md_text.split()) if md_text else 0
            if t1_status == "SUCCESS":
                print(f"[{idx}/{total}] [TIER 1 - FAST PATH] ({elapsed_ms:.0f}ms | {words} kata) [{source}] {target_url[:75]}...")
                return {
                    "url": final_url, "raw_url": raw_url, "title": clean_res_title, "source": source,
                    "pub_date": pub_date, "tier": "TIER1_FAST_PATH", "content": md_text, "word_count": words, "status": "SUCCESS",
                }
            else:
                print(f"[{idx}/{total}] [QUALITY GATE FILTERED] ({elapsed_ms:.0f}ms | {words} kata) [{source}] {target_url[:75]}...")
                return {
                    "url": final_url, "raw_url": raw_url, "title": clean_res_title, "source": source,
                    "pub_date": pub_date, "tier": "TIER1_FAST_PATH", "content": "", "word_count": 0, "status": t1_status,
                }

        # ---------------- TIER 2: PLAYWRIGHT FALLBACK ----------------
        t0 = time.time()
        final_url = target_url
        md_text = ""
        status = "SUCCESS"
        tier_label = "TIER2_PLAYWRIGHT"
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
            full_page_html = await page.content()
            page_title = extract_clean_headline(full_page_html, fallback_title=raw_t or title, source=source)

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
            worthy, reason = is_cpt_worthy_content(final_url, md_text, min_words=self.min_words, title=page_title, raw_html=full_page_html)
            status = "SUCCESS" if worthy else f"FILTERED: {reason}"
            tier_label = "TIER2_PLAYWRIGHT"

            # ---------------- TIER 3: KOMDIGI-BOT DELEGATOR (ON-DEMAND) ----------------
            if not worthy and any(w in reason for w in ("WAF", "Bot", "CAPTCHA", "Just a moment")) and self.bot_solver_url:
                print(f"[{idx}/{total}] [TIER 3 - BOT SOLVER] Mengirimkan target ke komdigi-bot ({self.bot_solver_url})...")
                solved_html = await solve_captcha_via_bot(final_url, self.bot_solver_url, timeout=float(self.timeout * 2))
                if solved_html:
                    solved_md = convert_html_to_markdown(solved_html, url=final_url, title=page_title)
                    s_worthy, s_reason = is_cpt_worthy_content(final_url, solved_md, min_words=self.min_words, title=page_title)
                    if s_worthy:
                        md_text = solved_md
                        status = "SUCCESS"
                        tier_label = "TIER3_KOMDIGI_BOT"
                        print(f"[{idx}/{total}] [TIER 3 SUCCESS] Berhasil bypass proteksi via komdigi-bot ({len(md_text.split())} kata)")

            elapsed_ms = (time.time() - t0) * 1000
            words = len(md_text.split()) if md_text else 0
            tag = f"[{tier_label.replace('_', ' ')}]" if status == "SUCCESS" else "[QUALITY GATE FILTERED]"
            print(f"[{idx}/{total}] {tag} ({elapsed_ms:.0f}ms | {words} kata) [{source}] {final_url[:70]}...")

        except Exception as e:
            status = f"ERROR: {e}"
            print(f"[{idx}/{total}] [CRAWL ERROR] {e} | {target_url[:70]}")
        finally:
            if page:
                try:
                    await asyncio.wait_for(page.close(), timeout=2.0)
                except Exception:
                    pass
            if context:
                try:
                    await asyncio.wait_for(context.close(), timeout=2.0)
                except Exception:
                    pass

        return {
            "url": final_url, "raw_url": raw_url, "title": clean_headline_title(page_title or title, source=source), "source": source,
            "pub_date": pub_date, "tier": tier_label, "content": md_text if status == "SUCCESS" else "",
            "word_count": len(md_text.split()) if status == "SUCCESS" else 0, "status": status,
        }

    async def _crawl_single_article(
        self, article: Dict[str, str], client: httpx.AsyncClient, playwright_browser, idx: int, total: int
    ) -> Dict:
        target_url = article.get("decoded_url") or article.get("link", "")
        raw_url = article.get("link", "")
        source = article.get("source", "Media")
        raw_title = article.get("title", "")
        title = clean_headline_title(raw_title, source=source)
        pub_date = article.get("pub_date", "")

        async with self.semaphore:
            try:
                return await asyncio.wait_for(
                    self._crawl_single_article_worker(article, client, playwright_browser, idx, total),
                    timeout=float(self.timeout * 2 + 5),
                )
            except asyncio.TimeoutError:
                print(f"[{idx}/{total}] [TIMEOUT] Worker melebihi batas waktu ({self.timeout * 2 + 5}s) | {target_url[:70]}")
                return {
                    "url": target_url, "raw_url": raw_url, "title": title, "source": source,
                    "pub_date": pub_date, "tier": "TIMEOUT", "content": "", "word_count": 0, "status": "ERROR: Worker Timeout",
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
                clean_it_title = clean_headline_title(it.get("title", ""), source=it.get("source", ""))
                domain = urlparse(it["url"]).netloc.replace("www.", "")
                domain_slug = re.sub(r"[^\w\-_\.]", "_", domain).strip("_") or "article"
                title_slug = re.sub(r"[^\w\s-]", "", clean_it_title).strip().lower()
                title_slug = re.sub(r"[-\s]+", "_", title_slug)[:45].strip("_")

                file_name = f"article_{idx:03d}_{domain_slug}_{title_slug}.md" if title_slug else f"article_{idx:03d}_{domain_slug}.md"
                file_path = os.path.join(dataset_dir, file_name)

                body = re.sub(r"^#\s+[^\n]+\n+", "", it["content"].strip()) if it["content"].strip().startswith("# ") else it["content"].strip()
                doc = f"# {clean_it_title}\n\n{body}\n"
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(doc)
            print(f"[OK] {len(unique_items)} file artikel Markdown (1 artikel 1 file .md) disimpan di: {os.path.abspath(dataset_dir)}")

        # Mode MERGE: gabungkan semua artikel ke satu file .md
        if output_mode in ("merge", "both"):
            docs = []
            for it in unique_items:
                clean_it_title = clean_headline_title(it.get("title", ""), source=it.get("source", ""))
                body = re.sub(r"^#\s+[^\n]+\n+", "", it["content"].strip()) if it["content"].strip().startswith("# ") else it["content"].strip()
                docs.append(f"# {clean_it_title}\n\n{body}")
            with open(merged_md_file, "w", encoding="utf-8") as f:
                f.write("\n\n---\n\n".join(docs) + "\n")
            print(f"[OK] Dataset Markdown gabungan disimpan ke: {os.path.abspath(merged_md_file)}")

    # 2. Export JSONL
    if output_format in ("jsonl", "all"):
        with open(jsonl_file, "w", encoding="utf-8") as f:
            for idx, it in enumerate(unique_items, 1):
                clean_it_title = clean_headline_title(it.get("title", ""), source=it.get("source", ""))
                rec = {
                    "id": f"cpt_doc_{idx:05d}", "title": clean_it_title, "url": it["url"], "source": it["source"],
                    "published_at": it.get("pub_date", ""), "tier": it["tier"], "word_count": it["word_count"],
                    "content": it["content"], "crawled_at": datetime.now().isoformat(),
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[OK] Dataset JSONL disimpan ke: {jsonl_file}")

    # 3. Export Log
    tot_words = sum(it["word_count"] for it in unique_items)
    t1_cnt = sum(1 for it in unique_items if it["tier"] == "TIER1_FAST_PATH")
    t2_cnt = sum(1 for it in unique_items if it["tier"] == "TIER2_PLAYWRIGHT")
    t3_cnt = sum(1 for it in unique_items if it["tier"] == "TIER3_KOMDIGI_BOT")

    with open(log_file, "w", encoding="utf-8") as f:
        f.write(
            f"=== PIPELINE AUDIT REPORT & QUALITY LOG ===\n"
            f"Waktu Eksekusi       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Topik Pencarian      : {topic or 'Direct URLs'}\n"
            f"Total URL Diproses   : {len(results)}\n"
            f"Total Lolos CPT Bersih: {len(unique_items)} artikel ({tot_words:,} kata)\n"
            f"  - Jalur Tier 1 (Fast-Path) : {t1_cnt} artikel\n"
            f"  - Jalur Tier 2 (Playwright): {t2_cnt} artikel\n"
            f"  - Jalur Tier 3 (komdigi-bot): {t3_cnt} artikel\n"
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
    print(f"Rasio Jalur        : Fast-Path: {t1_cnt} | Playwright: {t2_cnt} | Bot-Solver: {t3_cnt}")
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
    parser.add_argument("--bot-solver-url", default="", help="URL endpoint service komdigi-bot (misal: http://localhost:8080)")

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
        bot_solver_url=args.bot_solver_url,
    )
    results = asyncio.run(crawler.crawl_articles(articles))
    dedup = SemanticDeduplicator(threshold=args.sim_threshold)
    export_dataset(
        results, dedup, args.output, output_format=args.format, output_mode=args.output_mode,
        topic=args.topic or "", when=args.when, total_time_sec=time.time() - start_time
    )


if __name__ == "__main__":
    main()
