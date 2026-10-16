#!/usr/bin/env python3
"""
Web Content Scraper CLI Script (Enhanced Edition v2.0)
Supporting Playwright & Selenium with:
- innerHTML extraction
- Automated HTML-to-Markdown conversion (trafilatura & markdownify)
- Dynamic redirect resolution for Google News / Google Search links
- Extensive news media CSS selectors
- CPT Dataset Quality Gatekeeper
"""

import argparse
import csv
import os
import re
import sys
import time
from urllib.parse import urlparse
from typing import Dict, List, Tuple, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Scrapper.pipeline import (
    normalize_url_key,
    load_css_paths,
    get_css_selector_for_url,
    convert_html_to_markdown,
    is_cpt_worthy_content,
)


def scrape_with_playwright(
    urls: List[str],
    css_paths_map: Optional[Dict[str, str]],
    default_css_path: str = "body",
    headless: bool = True,
    timeout: int = 30,
    min_words: int = 25
) -> List[Dict[str, str]]:
    """Scrape web pages using Playwright with innerHTML extraction and HTML-to-Markdown conversion."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[Error] Package 'playwright' belum terinstal. Install dengan: pip install playwright && playwright install")
        sys.exit(1)

    results = []
    print(f"[*] Starting Playwright (headless={headless}, default_selector='{default_css_path}')...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        page = context.new_page()

        for idx, raw_url in enumerate(urls, 1):
            url = raw_url if raw_url.startswith(('http://', 'https://')) else f"https://{raw_url}"
            is_redirect_link = "google.com/goto" in url or "google.com/url" in url or "news.google.com" in url
            
            css_path, is_defined = get_css_selector_for_url(raw_url, css_paths_map, default_css_path, silent=is_redirect_link)

            print(f"\n[{idx}/{len(urls)}] Mengakses: {url}...")
            raw_html = ""
            scrapped_markdown = ""
            status = "SUCCESS"
            final_url = url
            page_title = ""

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                page.wait_for_timeout(1000)
                final_url = page.url
                page_title = page.title()

                # Dynamic Redirect Resolution
                if final_url != url:
                    final_css, final_defined = get_css_selector_for_url(final_url, css_paths_map, default_css_path, silent=False)
                    if final_defined or not is_defined:
                        css_path = final_css
                        print(f"    -> [Redirect Terbuka] Mendarat di: {final_url} (Selektor: '{css_path}')")

                # Extract innerHTML from target element(s)
                raw_html = page.evaluate(
                    """(cssPath) => {
                        let el = document.querySelector(cssPath);
                        if (el) {
                            return el.innerHTML;
                        }
                        let nodes = document.querySelectorAll(cssPath);
                        if (nodes.length > 0) {
                            let res = '';
                            nodes.forEach(n => res += '\\n' + n.innerHTML);
                            return res;
                        }
                        return document.body ? document.body.innerHTML : '';
                    }""",
                    css_path
                )

                # Smart Semantic Fallback if selector returned empty or minimal HTML
                if not raw_html or len(raw_html) < 200:
                    fallback_html = page.evaluate("""() => {
                        let article = document.querySelector('article') || document.querySelector('main') || document.querySelector('.article-content') || document.querySelector('.articles-content');
                        return article ? article.innerHTML : '';
                    }""")
                    if fallback_html and len(fallback_html) > len(raw_html):
                        print("    -> [Smart Fallback] Ekstraksi dari tag semantik <article>/<main> aktif")
                        raw_html = fallback_html

                # Convert extracted HTML to clean Markdown
                scrapped_markdown = convert_html_to_markdown(raw_html, url=final_url, title=page_title)

                # Quality Gatekeeper Check
                is_worthy, reason = is_cpt_worthy_content(final_url, scrapped_markdown, min_words=min_words)
                if not is_worthy:
                    status = f"FILTERED: {reason}"
                    print(f"    -> [Quality Gate] DITOLAK: {reason}")
                else:
                    word_cnt = len(scrapped_markdown.split())
                    print(f"    -> [Quality Gate] DITERIMA: {word_cnt} kata Markdown terkonversi rapi")

            except Exception as e:
                status = f"ERROR: {str(e)}"
                print(f"    -> Gagal mengekstrak {url}: {e}")

            results.append({
                "url": final_url,
                "raw_url": raw_url,
                "css_path": css_path,
                "content": scrapped_markdown.strip() if status == "SUCCESS" else "",
                "status": status
            })

        browser.close()

    return results


def scrape_with_selenium(
    urls: List[str],
    css_paths_map: Optional[Dict[str, str]],
    default_css_path: str = "body",
    headless: bool = True,
    timeout: int = 30,
    min_words: int = 25
) -> List[Dict[str, str]]:
    """Scrape web pages using Selenium with innerHTML extraction and HTML-to-Markdown conversion."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        print("[Error] Package 'selenium' belum terinstal. Install dengan: pip install selenium")
        sys.exit(1)

    results = []
    print(f"[*] Starting Selenium (headless={headless}, default_selector='{default_css_path}')...")

    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(timeout)

    try:
        for idx, raw_url in enumerate(urls, 1):
            url = raw_url if raw_url.startswith(('http://', 'https://')) else f"https://{raw_url}"
            is_redirect_link = "google.com/goto" in url or "google.com/url" in url or "news.google.com" in url
            css_path, is_defined = get_css_selector_for_url(raw_url, css_paths_map, default_css_path, silent=is_redirect_link)

            print(f"\n[{idx}/{len(urls)}] Mengakses: {url}...")
            raw_html = ""
            scrapped_markdown = ""
            status = "SUCCESS"
            final_url = url
            page_title = ""

            try:
                driver.get(url)
                time.sleep(1)
                final_url = driver.current_url
                page_title = driver.title

                if final_url != url:
                    final_css, final_defined = get_css_selector_for_url(final_url, css_paths_map, default_css_path, silent=False)
                    if final_defined or not is_defined:
                        css_path = final_css
                        print(f"    -> [Redirect Terbuka] Mendarat di: {final_url} (Selektor: '{css_path}')")

                js_script = """
                let cssPath = arguments[0];
                let el = document.querySelector(cssPath);
                if (el) {
                    return el.innerHTML;
                }
                let nodes = document.querySelectorAll(cssPath);
                if (nodes.length > 0) {
                    let res = '';
                    nodes.forEach(n => res += '\\n' + n.innerHTML);
                    return res;
                }
                return document.body ? document.body.innerHTML : '';
                """
                raw_html = driver.execute_script(js_script, css_path)

                scrapped_markdown = convert_html_to_markdown(raw_html or "", url=final_url, title=page_title)

                is_worthy, reason = is_cpt_worthy_content(final_url, scrapped_markdown, min_words=min_words)
                if not is_worthy:
                    status = f"FILTERED: {reason}"
                    print(f"    -> [Quality Gate] DITOLAK: {reason}")
                else:
                    word_cnt = len(scrapped_markdown.split())
                    print(f"    -> [Quality Gate] DITERIMA: {word_cnt} kata Markdown terkonversi rapi")

            except Exception as e:
                status = f"ERROR: {str(e)}"
                print(f"    -> Gagal mengekstrak {url}: {e}")

            results.append({
                "url": final_url,
                "raw_url": raw_url,
                "css_path": css_path,
                "content": scrapped_markdown.strip() if status == "SUCCESS" else "",
                "status": status
            })
    finally:
        driver.quit()

    return results


def read_url_list(urls_file: str) -> List[str]:
    """Read list of URLs from file."""
    if not os.path.isfile(urls_file):
        print(f"[Error] File daftar URL '{urls_file}' tidak ditemukan.")
        sys.exit(1)

    urls = []
    with open(urls_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.lower() in ['url', 'urls', 'link', 'links']:
                continue
            urls.append(line)

    if not urls:
        print(f"[Warning] Tidak ada URL yang ditemukan pada file '{urls_file}'.")

    return urls


def sanitize_filename(name: str) -> str:
    """Sanitize string for filename use."""
    sub = re.sub(r'[^\w\-_\. ]', '_', name)
    return re.sub(r'_+', '_', sub).strip('_')


def save_output(results: List[Dict[str, str]], output_target: str, output_mode: str):
    """Save clean scraped content to Markdown file(s) for training dataset."""
    valid_items = [item for item in results if item.get('status') == 'SUCCESS' and item.get('content')]
    filtered_or_failed = [item for item in results if item.get('status') != 'SUCCESS' or not item.get('content')]

    if output_mode == 'merge':
        out_dir = os.path.dirname(output_target)
        if not out_dir:
            out_dir = '.'
        base_name = os.path.splitext(os.path.basename(output_target))[0]
        log_file = os.path.join(out_dir, f"{base_name}.log")
    else:
        out_dir = output_target
        if output_target.endswith('.md') or output_target.endswith('.txt'):
            out_dir = os.path.splitext(output_target)[0]
        log_file = os.path.join(out_dir, "scraper.log")

    os.makedirs(out_dir, exist_ok=True)

    if filtered_or_failed:
        with open(log_file, 'w', encoding='utf-8') as log_f:
            log_f.write(f"=== SCRAPING QUALITY LOG & REJECTION REPORT ({time.strftime('%Y-%m-%d %H:%M:%S')}) ===\n")
            log_f.write(f"Total URL Diproses : {len(results)}\n")
            log_f.write(f"Total Lolos CPT    : {len(valid_items)}\n")
            log_f.write(f"Total Ditolak/Gagal: {len(filtered_or_failed)}\n\n")
            for item in filtered_or_failed:
                log_f.write(f"- URL Target: {item['url']}\n")
                log_f.write(f"  URL Input : {item['raw_url']}\n")
                log_f.write(f"  Alasan    : {item['status']}\n\n")

        print(f"\n[INFO] {len(filtered_or_failed)} URL ditolak/gagal. Detail tercatat di: {os.path.abspath(log_file)}")

    if output_mode == 'merge':
        clean_contents = [item['content'].strip() for item in valid_items]
        merged_text = "\n\n---\n\n".join(clean_contents)
        if merged_text:
            merged_text += "\n"

        with open(output_target, 'w', encoding='utf-8') as f:
            f.write(merged_text)

        print(f"[OK] {len(valid_items)} artikel bersih berkualitas tinggi disimpan ke: {os.path.abspath(output_target)}")

    elif output_mode == 'each':
        for idx, item in enumerate(valid_items, 1):
            parsed = urlparse(item['url'])
            domain_slug = sanitize_filename(parsed.netloc or "url")
            filename = f"scraped_{idx:03d}_{domain_slug}.md"
            filepath = os.path.join(out_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(item['content'].strip() + "\n")

        print(f"[OK] {len(valid_items)} file dataset CPT tersimpan pada folder: {os.path.abspath(out_dir)}")


def main():
    parser = argparse.ArgumentParser(
        description="Web Content Scraper - Ekstraksi isi konten URL ke file Markdown."
    )
    parser.add_argument(
        "--urls", "-u",
        required=True,
        help="Path ke file yang berisi daftar URL (misal: --urls=Windows/output/crawler_url.txt)"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Path lokasi output file/folder hasil scrapping"
    )
    parser.add_argument(
        "--output-mode",
        choices=["each", "merge"],
        default="merge",
        help="Mode simpan output: 'each' (1 file per URL) atau 'merge' (gabung semua ke 1 file). Default: merge"
    )
    parser.add_argument(
        "--css-path",
        default="body",
        help="Default CSS Path selector ekstraksi elemen. Default: 'body'"
    )
    parser.add_argument(
        "--css-paths",
        default=None,
        help="Path ke file CSV pemetaan URL ke CSS Path (contoh header: url;css_path)"
    )
    parser.add_argument(
        "--engine",
        choices=["playwright", "selenium"],
        default="playwright",
        help="Engine scraping yang digunakan: 'playwright' atau 'selenium'. Default: playwright"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Jalankan browser dengan UI visual (non-headless mode)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout waktu tunggu loading halaman dalam detik. Default: 30"
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=25,
        help="Batas minimum jumlah kata agar konten dinyatakan layak CPT (default: 25 kata)"
    )

    args = parser.parse_args()

    urls = read_url_list(args.urls)
    if not urls:
        print("[!] Tidak ada URL yang valid untuk diproses.")
        sys.exit(0)

    css_paths_map = None
    if args.css_paths:
        css_paths_map = load_css_paths(args.css_paths)

    headless_mode = not args.no_headless
    if args.engine == "playwright":
        results = scrape_with_playwright(
            urls=urls,
            css_paths_map=css_paths_map,
            default_css_path=args.css_path,
            headless=headless_mode,
            timeout=args.timeout,
            min_words=args.min_words
        )
    else:
        results = scrape_with_selenium(
            urls=urls,
            css_paths_map=css_paths_map,
            default_css_path=args.css_path,
            headless=headless_mode,
            timeout=args.timeout,
            min_words=args.min_words
        )

    save_output(results, args.output, args.output_mode)


if __name__ == "__main__":
    main()
