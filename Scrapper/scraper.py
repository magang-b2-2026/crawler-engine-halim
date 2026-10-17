#!/usr/bin/env python3
"""
Web Content Scraper CLI Script (Ponytail Streamlined)
Supporting Playwright & Selenium with innerHTML extraction, CPT Quality Gatekeeper,
and automated HTML-to-Markdown conversion.
"""

import argparse
import os
import re
import sys
import time
from urllib.parse import urlparse
from typing import Dict, List, Optional

# Windows UTF-8 console output guard (cegah charmap cp1252 crash pada karakter internasional)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Auto-switch to project .venv python if executed under an unactivated/incompatible python (e.g. Python 3.14)
venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "Scripts", "python.exe"))
if os.path.isfile(venv_py) and os.path.abspath(sys.executable).lower() != venv_py.lower() and not os.environ.get("_CRAWLER_VENV_ACTIVE"):
    os.environ["_CRAWLER_VENV_ACTIVE"] = "1"
    import subprocess
    sys.exit(subprocess.call([venv_py] + sys.argv))

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Scrapper.pipeline import (
    load_css_paths,
    get_css_selector_for_url,
    convert_html_to_markdown,
    is_cpt_worthy_content,
)


def _process_item(final_url: str, raw_url: str, raw_html: str, css_path: str, page_title: str, min_words: int) -> Dict[str, str]:
    """Helper terpadu untuk konversi markdown dan validasi Quality Gate CPT."""
    scrapped_markdown = convert_html_to_markdown(raw_html, url=final_url, title=page_title)
    is_worthy, reason = is_cpt_worthy_content(final_url, scrapped_markdown, min_words=min_words)
    status = "SUCCESS" if is_worthy else f"FILTERED: {reason}"
    word_cnt = len(scrapped_markdown.split()) if is_worthy else 0
    tag = f"[Quality Gate] DITERIMA: {word_cnt} kata" if is_worthy else f"[Quality Gate] DITOLAK: {reason}"
    print(f"    -> {tag}")
    return {
        "url": final_url, "raw_url": raw_url, "css_path": css_path,
        "content": scrapped_markdown.strip() if is_worthy else "", "status": status,
    }


def scrape_with_playwright(
    urls: List[str],
    css_paths_map: Optional[Dict[str, str]],
    default_css_path: str = "body",
    headless: bool = True,
    timeout: int = 30,
    min_words: int = 25,
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
            viewport={"width": 1920, "height": 1080},
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        page = context.new_page()

        for idx, raw_url in enumerate(urls, 1):
            url = raw_url if raw_url.startswith(("http://", "https://")) else f"https://{raw_url}"
            is_redirect = any(x in url for x in ("google.com/goto", "google.com/url", "news.google.com"))
            css_path, is_def = get_css_selector_for_url(raw_url, css_paths_map, default_css_path, silent=is_redirect)
            print(f"\n[{idx}/{len(urls)}] Mengakses: {url}...")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                page.wait_for_timeout(1000)
                final_url = page.url
                page_title = page.title()

                if final_url != url:
                    final_css, f_def = get_css_selector_for_url(final_url, css_paths_map, default_css_path, silent=False)
                    if f_def or not is_def:
                        css_path = final_css
                        print(f"    -> [Redirect Terbuka] Mendarat di: {final_url} (Selektor: '{css_path}')")

                if css_path == "body":
                    raw_html = page.content()
                else:
                    raw_html = page.evaluate(
                        """(css) => {
                            let el = document.querySelector(css);
                            if (el) return el.innerHTML;
                            let nodes = document.querySelectorAll(css);
                            return nodes.length > 0 ? Array.from(nodes).map(n => n.innerHTML).join('\\n') : '';
                        }""",
                        css_path,
                    )
                    if not raw_html or len(raw_html) < 200:
                        fb = page.evaluate("() => { let el = document.querySelector('article, main, .article-content'); return el ? el.innerHTML : ''; }")
                        raw_html = fb if fb and len(fb) > len(raw_html) else page.content()

                results.append(_process_item(final_url, raw_url, raw_html, css_path, page_title, min_words))
            except Exception as e:
                print(f"    -> Gagal mengekstrak {url}: {e}")
                results.append({"url": url, "raw_url": raw_url, "css_path": css_path, "content": "", "status": f"ERROR: {e}"})

        browser.close()
    return results


def scrape_with_selenium(
    urls: List[str],
    css_paths_map: Optional[Dict[str, str]],
    default_css_path: str = "body",
    headless: bool = True,
    timeout: int = 30,
    min_words: int = 25,
) -> List[Dict[str, str]]:
    """Scrape web pages using Selenium with innerHTML extraction and HTML-to-Markdown conversion."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        import subprocess
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

    service = Service()
    if sys.platform == "win32":
        service.creation_flags = subprocess.CREATE_NO_WINDOW

    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(timeout)

    try:
        for idx, raw_url in enumerate(urls, 1):
            url = raw_url if raw_url.startswith(("http://", "https://")) else f"https://{raw_url}"
            is_redirect = any(x in url for x in ("google.com/goto", "google.com/url", "news.google.com"))
            css_path, is_def = get_css_selector_for_url(raw_url, css_paths_map, default_css_path, silent=is_redirect)
            print(f"\n[{idx}/{len(urls)}] Mengakses: {url}...")

            try:
                driver.get(url)
                time.sleep(1)
                final_url = driver.current_url
                page_title = driver.title

                if final_url != url:
                    final_css, f_def = get_css_selector_for_url(final_url, css_paths_map, default_css_path, silent=False)
                    if f_def or not is_def:
                        css_path = final_css
                        print(f"    -> [Redirect Terbuka] Mendarat di: {final_url} (Selektor: '{css_path}')")

                if css_path == "body":
                    raw_html = driver.page_source
                else:
                    raw_html = driver.execute_script(
                        """let css = arguments[0];
                        let el = document.querySelector(css);
                        if (el) return el.innerHTML;
                        let nodes = document.querySelectorAll(css);
                        return nodes.length > 0 ? Array.from(nodes).map(n => n.innerHTML).join('\\n') : '';""",
                        css_path,
                    )
                    if not raw_html or len(raw_html) < 200:
                        fb = driver.execute_script("let el = document.querySelector('article, main, .article-content'); return el ? el.innerHTML : '';")
                        raw_html = fb if fb and len(fb) > len(raw_html) else driver.page_source

                results.append(_process_item(final_url, raw_url, raw_html, css_path, page_title, min_words))
            except Exception as e:
                print(f"    -> Gagal mengekstrak {url}: {e}")
                results.append({"url": url, "raw_url": raw_url, "css_path": css_path, "content": "", "status": f"ERROR: {e}"})
    finally:
        driver.quit()

    return results


def read_url_list(urls_file: str) -> List[str]:
    """Membaca daftar URL dari file teks."""
    if not os.path.isfile(urls_file):
        return []
    with open(urls_file, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#") and line.strip().lower() not in ("url", "urls", "link", "links")]


def save_output(results: List[Dict[str, str]], output_target: str, output_mode: str):
    """Menyimpan hasil scraping ke format Markdown dan Quality Log."""
    valid_items = [it for it in results if it.get("status") == "SUCCESS" and it.get("content")]
    filtered = [it for it in results if it.get("status") != "SUCCESS" or not it.get("content")]

    out_dir = os.path.dirname(output_target) or "." if output_mode == "merge" else output_target
    if output_mode != "merge" and (output_target.endswith(".md") or output_target.endswith(".txt")):
        out_dir = os.path.splitext(output_target)[0]

    os.makedirs(out_dir, exist_ok=True)
    log_file = os.path.join(out_dir, f"{os.path.splitext(os.path.basename(output_target))[0]}.log" if output_mode == "merge" else "scraper.log")

    if filtered:
        with open(log_file, "w", encoding="utf-8") as log_f:
            log_f.write(
                f"=== SCRAPING QUALITY LOG ({time.strftime('%Y-%m-%d %H:%M:%S')}) ===\n"
                f"Total URL Diproses : {len(results)}\nTotal Lolos CPT    : {len(valid_items)}\nTotal Ditolak/Gagal: {len(filtered)}\n\n"
            )
            for it in filtered:
                log_f.write(f"- URL: {it['url']} (Input: {it['raw_url']})\n  Status: {it['status']}\n\n")
        print(f"\n[INFO] {len(filtered)} URL ditolak/gagal. Detail tercatat di: {os.path.abspath(log_file)}")

    if output_mode == "merge":
        merged = "\n\n---\n\n".join(it["content"].strip() for it in valid_items)
        with open(output_target, "w", encoding="utf-8") as f:
            f.write(f"{merged}\n" if merged else "")
        print(f"[OK] {len(valid_items)} artikel bersih disimpan ke: {os.path.abspath(output_target)}")
    elif output_mode == "each":
        for idx, it in enumerate(valid_items, 1):
            domain_slug = re.sub(r"[^\w\-_\.]", "_", urlparse(it["url"]).netloc.replace("www.", "") or "url").strip("_")
            title_slug = re.sub(r"[^\w\s-]", "", it.get("title", "")).strip().lower()
            title_slug = re.sub(r"[-\s]+", "_", title_slug)[:45].strip("_")
            file_name = f"article_{idx:03d}_{domain_slug}_{title_slug}.md" if title_slug else f"article_{idx:03d}_{domain_slug}.md"
            filepath = os.path.join(out_dir, file_name)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"{it['content'].strip()}\n")
        print(f"[OK] {len(valid_items)} file dataset CPT tersimpan di: {os.path.abspath(out_dir)}")


def main():
    parser = argparse.ArgumentParser(description="Web Content Scraper (Ponytail Streamlined)")
    parser.add_argument("--urls", "-u", required=True, help="Path ke file daftar URL")
    parser.add_argument("--output", "-o", required=True, help="Path output file/folder hasil scrapping")
    parser.add_argument("--output-mode", choices=["each", "merge"], default="each", help="Mode output ('each' atau 'merge'). Default: each")
    parser.add_argument("--css-path", default="body", help="Default CSS selector. Default: 'body'")
    parser.add_argument("--css-paths", default=None, help="Path ke file CSV pemetaan CSS selector")
    parser.add_argument("--engine", choices=["playwright", "selenium"], default="playwright", help="Engine scraping. Default: playwright")
    parser.add_argument("--no-headless", action="store_true", help="Jalankan browser dengan UI visual")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per URL dalam detik. Default: 30")
    parser.add_argument("--min-words", type=int, default=25, help="Batas minimum kata CPT. Default: 25")

    args = parser.parse_args()
    urls = read_url_list(args.urls)
    if not urls:
        print("[!] Tidak ada URL yang valid untuk diproses.")
        sys.exit(0)

    css_map = load_css_paths(args.css_paths) if args.css_paths else None
    runner = scrape_with_playwright if args.engine == "playwright" else scrape_with_selenium
    results = runner(urls=urls, css_paths_map=css_map, default_css_path=args.css_path, headless=not args.no_headless, timeout=args.timeout, min_words=args.min_words)
    save_output(results, args.output, args.output_mode)


if __name__ == "__main__":
    main()
