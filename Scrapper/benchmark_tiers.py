#!/usr/bin/env python3
"""
Benchmarking Suite: Tier 1 (Fast-Path HTTPX) vs Tier 2 (Playwright Stealth)
Membandingkan performa secara ilmiah pada 3 kata kunci berbeda:
1. Kecerdasan Buatan Indonesia
2. Hilirisasi Nikel dan Tambang
3. Pemberantasan Judi Online Komdigi
"""

import asyncio
import os
import re
import sys
import time
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Scrapper.pipeline import (
    fetch_google_news_rss,
    batch_decode_google_news_urls,
    load_css_paths,
    get_css_selector_for_url,
    convert_html_to_markdown,
    is_cpt_worthy_content,
    normalize_url_key,
)
import httpx
from playwright.async_api import async_playwright


KEYWORDS = [
    "Kecerdasan Buatan Indonesia",
    "Hilirisasi Nikel dan Tambang",
    "Pemberantasan Judi Online Komdigi",
]


async def run_pure_tier1(articles: List[Dict], timeout: int = 15) -> Dict:
    """Menjalankan ekstraksi murni Tier 1 (HTTPX + Trafilatura) untuk seluruh artikel."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "id,en-US;q=0.9,en;q=0.8",
    }
    
    t0 = time.time()
    success_count = 0
    total_words = 0
    durations_ms = []

    limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
    async with httpx.AsyncClient(timeout=timeout, limits=limits, verify=False) as client:
        for a in articles:
            u = a.get("decoded_url") or a.get("link")
            art_t0 = time.time()
            try:
                resp = await client.get(u, headers=headers, follow_redirects=True, timeout=timeout)
                if resp.status_code == 200:
                    final_url = str(resp.url)
                    title_m = re.search(r"<title[^>]*>(.*?)</title>", resp.text, re.I | re.S)
                    title = title_m.group(1).strip() if title_m else ""
                    md_text = convert_html_to_markdown(resp.text, url=final_url, title=title)
                    worthy, _ = is_cpt_worthy_content(final_url, md_text, min_words=25)
                    if worthy:
                        success_count += 1
                        total_words += len(md_text.split())
            except Exception:
                pass
            durations_ms.append((time.time() - art_t0) * 1000)

    total_time = time.time() - t0
    return {
        "tier": "Tier 1 (Fast-Path HTTPX)",
        "total_time_sec": total_time,
        "success_count": success_count,
        "total_articles": len(articles),
        "total_words": total_words,
        "avg_duration_ms": sum(durations_ms) / len(durations_ms) if durations_ms else 0,
    }


async def run_pure_tier2(articles: List[Dict], css_map: Dict[str, str], timeout: int = 15) -> Dict:
    """Menjalankan ekstraksi murni Tier 2 (Playwright Stealth Chromium) untuk seluruh artikel."""
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    t0 = time.time()
    success_count = 0
    total_words = 0
    durations_ms = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )

        for a in articles:
            u = a.get("decoded_url") or a.get("link")
            art_t0 = time.time()
            context = None
            page = None
            try:
                context = await browser.new_context(user_agent=ua, viewport={"width": 1920, "height": 1080}, ignore_https_errors=True)
                await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
                page = await context.new_page()

                await page.goto(u, wait_until="domcontentloaded", timeout=timeout * 1000)
                if "google.com" in u:
                    try:
                        await page.wait_for_url(lambda url: "google.com" not in url, timeout=4000)
                    except Exception:
                        pass
                await page.wait_for_timeout(1000)

                final_url = page.url
                raw_t = await page.title()
                css_path, _ = get_css_selector_for_url(final_url, css_map, default_css_path="body", silent=True)

                eval_js = """(css) => {
                    let el = document.querySelector(css);
                    if (el) return el.innerHTML;
                    let nodes = document.querySelectorAll(css);
                    if (nodes.length > 0) return Array.from(nodes).map(n => n.innerHTML).join('\\n');
                    let sem = document.querySelector('article, main, .article-content');
                    return sem ? sem.innerHTML : (document.body ? document.body.innerHTML : '');
                }"""
                raw_html = await page.evaluate(eval_js, css_path)
                md_text = convert_html_to_markdown(raw_html, url=final_url, title=raw_t or "")
                worthy, _ = is_cpt_worthy_content(final_url, md_text, min_words=25)
                if worthy:
                    success_count += 1
                    total_words += len(md_text.split())
            except Exception:
                pass
            finally:
                if page:
                    try: await page.close()
                    except Exception: pass
                if context:
                    try: await context.close()
                    except Exception: pass
            durations_ms.append((time.time() - art_t0) * 1000)

        await browser.close()

    total_time = time.time() - t0
    return {
        "tier": "Tier 2 (Playwright Stealth)",
        "total_time_sec": total_time,
        "success_count": success_count,
        "total_articles": len(articles),
        "total_words": total_words,
        "avg_duration_ms": sum(durations_ms) / len(durations_ms) if durations_ms else 0,
    }


async def main():
    css_map = load_css_paths("Scrapper/sample_css_paths.csv")
    print(f"[*] Memulai Benchmark Tier 1 vs Tier 2 pada 3 Kata Kunci...")
    print(f"[*] CSS Map dimuat: {len(css_map)} domain\n")

    benchmark_results = []

    for idx, kw in enumerate(KEYWORDS, 1):
        print(f"\n=======================================================")
        print(f"KATA KUNCI {idx}: \"{kw}\"")
        print(f"=======================================================")
        raw_arts = fetch_google_news_rss(kw, when="7d", limit=5)
        arts = batch_decode_google_news_urls(raw_arts)

        if not arts:
            print(f"[!] Gagal mendapatkan artikel untuk '{kw}'")
            continue

        print(f"\n-> Menjalankan Uji TIER 1 (Fast-Path HTTPX)...")
        res_t1 = await run_pure_tier1(arts)
        print(f"   [Tier 1] Total Waktu: {res_t1['total_time_sec']:.2f}s | Sukses: {res_t1['success_count']}/{res_t1['total_articles']} | Total Kata: {res_t1['total_words']} | Rata-rata: {res_t1['avg_duration_ms']:.0f}ms/artikel")

        print(f"\n-> Menjalankan Uji TIER 2 (Playwright Stealth)...")
        res_t2 = await run_pure_tier2(arts, css_map)
        print(f"   [Tier 2] Total Waktu: {res_t2['total_time_sec']:.2f}s | Sukses: {res_t2['success_count']}/{res_t2['total_articles']} | Total Kata: {res_t2['total_words']} | Rata-rata: {res_t2['avg_duration_ms']:.0f}ms/artikel")

        speedup = res_t2["total_time_sec"] / res_t1["total_time_sec"] if res_t1["total_time_sec"] > 0 else 1.0

        benchmark_results.append({
            "keyword": kw,
            "t1": res_t1,
            "t2": res_t2,
            "speedup": speedup,
        })

    # Cetak Tabel Perbandingan Final
    print("\n\n" + "=" * 90)
    print("                    TABEL HASIL BENCHMARK TIER 1 VS TIER 2")
    print("=" * 90)
    print(f"{'Kata Kunci':<32} | {'Tier 1 Waktu':<13} | {'Tier 2 Waktu':<13} | {'Speedup':<8} | {'Kata (T1 vs T2)':<16}")
    print("-" * 90)
    for b in benchmark_results:
        kw_short = b["keyword"][:30]
        t1_str = f"{b['t1']['total_time_sec']:.2f}s ({b['t1']['avg_duration_ms']:.0f}ms)"
        t2_str = f"{b['t2']['total_time_sec']:.2f}s ({b['t2']['avg_duration_ms']:.0f}ms)"
        spd_str = f"{b['speedup']:.1f}x"
        w_str = f"{b['t1']['total_words']} vs {b['t2']['total_words']}"
        print(f"{kw_short:<32} | {t1_str:<13} | {t2_str:<13} | {spd_str:<8} | {w_str:<16}")
    print("=" * 90 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
