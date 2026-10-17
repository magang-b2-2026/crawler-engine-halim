#!/usr/bin/env python3
"""
Google News RSS Harvester (Ponytail Streamlined)
Lightweight, zero-browser URL discovery for credible news portals.
"""

import argparse
import os
import sys

# Auto-switch to project .venv python if executed under an unactivated/incompatible python (e.g. Python 3.14)
venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "Scripts", "python.exe"))
if os.path.isfile(venv_py) and os.path.abspath(sys.executable).lower() != venv_py.lower() and not os.environ.get("_CRAWLER_VENV_ACTIVE"):
    os.environ["_CRAWLER_VENV_ACTIVE"] = "1"
    import subprocess
    sys.exit(subprocess.call([venv_py] + sys.argv))

# Ensure Scrapper module resolution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Scrapper.pipeline import fetch_google_news_rss, batch_decode_google_news_urls


def save_urls(articles: list, output_file: str):
    """Save article URLs to txt file for scraper ingestion."""
    os.makedirs(os.path.dirname(os.path.abspath(output_file)) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("url\n" + "\n".join((a.get("decoded_url") or a.get("link", "")) for a in articles if a.get("link")) + "\n")
    print(f"[OK] {len(articles)} URL artikel asli berhasil disimpan ke: {os.path.abspath(output_file)}")


def main():
    parser = argparse.ArgumentParser(description="Google News RSS Harvester & URL Discovery")
    parser.add_argument("-q", "--query", required=True, help="Kata kunci pencarian berita")
    parser.add_argument("-w", "--when", default="7d", help="Filter waktu kebaruan (1d, 7d, 30d). Default: 7d")
    parser.add_argument("-l", "--limit", type=int, default=50, help="Batas maksimal artikel. Default: 50")
    parser.add_argument("-o", "--output", default="Scrapper/output/google_news_urls.txt", help="Path file output. Default: Scrapper/output/google_news_urls.txt")
    parser.add_argument("--no-decode", action="store_true", help="Jangan decode URL asli (tetap pakai link redirect Google)")

    args = parser.parse_args()
    articles = fetch_google_news_rss(args.query, when=args.when, limit=args.limit)
    if not articles:
        print("[!] Tidak ada artikel yang ditemukan.")
        return

    if not args.no_decode:
        articles = batch_decode_google_news_urls(articles)

    print("\n=== DAFTAR LINK ARTIKEL YANG DITEMUKAN ===")
    for idx, a in enumerate(articles[:10], 1):
        target = a.get("decoded_url") or a.get("link", "")
        print(f"{idx:02d}. [{a.get('source', 'Media')}] {a.get('title', '')[:55]}...\n    -> {target}")

    save_urls(articles, args.output)


if __name__ == "__main__":
    main()
