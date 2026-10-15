#!/usr/bin/env python3
"""
Google News RSS Harvester
Alternative lightweight, zero-browser URL discovery for credible news portals.
Fetches verified Indonesian news links without triggering Google Search bot detection.
"""

import argparse
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime


def fetch_google_news_rss(query: str, when: str = "7d", limit: int = 50) -> list:
    """
    Fetches news articles via Google News RSS search endpoint.
    Example: https://news.google.com/rss/search?q=Kecerdasan+Buatan+when:7d&hl=id&gl=ID&ceid=ID:id
    """
    clean_query = query.strip()
    if when:
        clean_query = f"{clean_query} when:{when}"

    encoded_query = urllib.parse.quote_plus(clean_query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=id&gl=ID&ceid=ID:id"

    print(f"[*] Fetching Google News RSS: {rss_url}")
    req = urllib.request.Request(
        rss_url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )

    articles = []
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        print(f"[*] Ditemukan {len(items)} artikel di feed RSS.")

        for item in items[:limit]:
            title = item.findtext("title", default="").strip()
            link = item.findtext("link", default="").strip()
            pub_date = item.findtext("pubDate", default="").strip()
            source = item.findtext("source", default="Unknown Media").strip()

            if link:
                articles.append({
                    "title": title,
                    "link": link,
                    "source": source,
                    "pub_date": pub_date
                })

    except Exception as e:
        print(f"[Error] Gagal mengambil Google News RSS: {e}")

    return articles


def save_urls(articles: list, output_file: str):
    """Save article URLs to txt file for scraper.py ingestion."""
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("url\n")
        for a in articles:
            f.write(f"{a['link']}\n")
    print(f"[OK] {len(articles)} URL Google News berhasil disimpan ke: {os.path.abspath(output_file)}")


def main():
    parser = argparse.ArgumentParser(description="Google News RSS Harvester")
    parser.add_argument("-q", "--query", required=True, help="Kata kunci pencarian berita (misal: 'Kecerdasan Buatan')")
    parser.add_argument("-w", "--when", default="7d", help="Filter waktu kebaruan berita (misal: 1d, 3d, 7d, 30d). Default: 7d")
    parser.add_argument("-l", "--limit", type=int, default=50, help="Batas maksimal artikel yang diambil. Default: 50")
    parser.add_argument("-o", "--output", default="google_news_urls.txt", help="Path file output URL. Default: google_news_urls.txt")

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
