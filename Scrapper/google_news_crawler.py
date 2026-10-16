#!/usr/bin/env python3
"""
Google News RSS Harvester (Ponytail Streamlined)
Lightweight, zero-browser URL discovery for credible news portals.
"""

import argparse
import os
import sys

# Ensure Scrapper module resolution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Scrapper.pipeline import fetch_google_news_rss


def save_urls(articles: list, output_file: str):
    """Save article URLs to txt file for scraper ingestion."""
    os.makedirs(os.path.dirname(os.path.abspath(output_file)) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("url\n" + "\n".join(a["link"] for a in articles if a.get("link")) + "\n")
    print(f"[OK] {len(articles)} URL Google News berhasil disimpan ke: {os.path.abspath(output_file)}")


def main():
    parser = argparse.ArgumentParser(description="Google News RSS Harvester")
    parser.add_argument("-q", "--query", required=True, help="Kata kunci pencarian berita")
    parser.add_argument("-w", "--when", default="7d", help="Filter waktu kebaruan (1d, 7d, 30d). Default: 7d")
    parser.add_argument("-l", "--limit", type=int, default=50, help="Batas maksimal artikel. Default: 50")
    parser.add_argument("-o", "--output", default="google_news_urls.txt", help="Path file output. Default: google_news_urls.txt")

    args = parser.parse_args()
    articles = fetch_google_news_rss(args.query, when=args.when, limit=args.limit)
    if not articles:
        print("[!] Tidak ada artikel yang ditemukan.")
        return

    print("\n=== CONTOH ARTIKEL KREDIBEL YANG DITEMUKAN ===")
    for a in articles[:5]:
        print(f"• [{a['source']}] {a['title'][:65]}...")

    save_urls(articles, args.output)


if __name__ == "__main__":
    main()
