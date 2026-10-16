# AITF Crawler Engine & CPT Dataset Pipeline Ecosystem

Repositori ini berisi ekosistem lengkap untuk crawling dan ekstraksi data berbasis web yang dirancang khusus untuk menghasilkan dataset berkualitas tinggi bagi kebutuhan **Continual Pre-Training (CPT) Large Language Models (LLM)**.

Sistem ini menggabungkan dua engine utama:
1. **Python Hybrid Pipeline (Scrapper v3.0):** Pipeline ekstraksi modern dengan arsitektur asinkron dua tingkat (*Fast-Path HTTPX + Playwright Stealth*), deduplikasi semantik N-gram, dan integrasi Google News RSS.
2. **AITF Binary Engine:** Binary executable multi-platform (Windows, Linux, macOS) untuk crawling Google Search dan Google Images volume besar.

---

## 📑 Daftar Isi

- [Arsitektur Sistem](#-arsitektur-sistem)
- [Struktur Direktori](#-struktur-direktori)
- [Fitur Utama & Keunggulan](#-fitur-utama--keunggulan)
- [Keamanan & Konfigurasi Lingkungan (.env)](#-keamanan--konfigurasi-lingkungan-env)
- [Instalasi & Persiapan](#-instalasi--persiapan)
- [Panduan Penggunaan CLI](#-panduan-penggunaan-cli)
  - [1. One-Click Pipeline Orchestrator (Rekomendasi Utama)](#1-one-click-pipeline-orchestrator-rekomendasi-utama)
  - [2. Scraper CLI Mandiri (Playwright / Selenium)](#2-scraper-cli-mandiri-playwright--selenium)
  - [3. Google News RSS Harvester (Zero-Browser Discovery)](#3-google-news-rss-harvester-zero-browser-discovery)
  - [4. AITF Binary Engine (Google Search & Image)](#4-aitf-binary-engine-google-search--image)
- [Format Luaran Dataset](#-format-luaran-dataset)
- [Pengujian QA & Regresi](#-pengujian-qa--regresi)
- [Kontributor & Lisensi](#-kontributor--lisensi)

---

## 🏛 Arsitektur Sistem

```mermaid
flowchart TD
    User["Operator / Engineer"] -->|"Input Topik & Parameter"| Pipeline["Scrapper/pipeline.py (Orchestrator)"]
    
    subgraph Discovery ["1. Tahap Penemuan (Zero-Browser Discovery)"]
        Pipeline -->|"Kueri + when:Nd"| GNews["Google News RSS Harvester"]
        GNews -->|"Token Protobuf /rss/articles"| Decoder["Google Decoder / URL Resolver"]
    end

    subgraph Extraction ["2. Tahap Ekstraksi Asinkron Dua Tingkat"]
        Decoder -->|"Direct Publisher URL"| HybridPool["Hybrid Async Worker Pool (asyncio.Semaphore)"]
        HybridPool -->|"Coba Pertama (< 350ms)"| Tier1["Tier 1: Fast-Path (HTTPX + Trafilatura)"]
        Tier1 -- "Gagal / WAF / JS Render" --> Tier2["Tier 2: Fallback (Playwright Stealth Chromium)"]
        Tier1 -- "Sukses" --> QGate["CPT Quality Gatekeeper"]
        Tier2 --> QGate
    end

    subgraph Curation ["3. Tahap Kurasi & Deduplikasi"]
        QGate -->|"Lolos Validasi Panjang, WAF, & Paywall"| Dedup["Semantic Deduplicator (Word Shingling Jaccard & Overlap)"]
        Dedup -->|"Kemiripan >= 80%"| Drop["Dieliminasi (Tercatat di .log)"]
        Dedup -->|"Artikel Unik & Kaya"| Exporter["Multi-Format Exporter"]
    end

    subgraph Output ["4. Luaran Dataset"]
        Exporter --> MD["Dataset Markdown (.md)"]
        Exporter --> JSONL["Dataset JSONL (PyTorch / HuggingFace)"]
        Exporter --> LOG["Audit Quality Log (.log)"]
    end
```

---

## 📁 Struktur Direktori

```text
.
├── .env.example             # Template konfigurasi environment (bebas dari kredensial)
├── .gitignore               # Aturan pengabaian Git (mencegah kebocoran .env dan cache)
├── CHANGELOG.md             # Log pembaruan arsitektur, bug hunting, dan hasil benchmark
├── readme.md                # Dokumentasi komprehensif repositori (dokumen ini)
├── Linux/                   # Binary AITF Engine dan skrip instalasi untuk OS Linux
├── MacOS/                   # Binary AITF Engine dan skrip instalasi untuk OS macOS
├── Windows/                 # Binary AITF Engine dan skrip instalasi untuk OS Windows
└── Scrapper/                # Modul Python CPT Scraper & Pipeline Orchestrator
    ├── pipeline.py          # One-Click Pipeline Orchestrator (Opsi 1, 2, 3, 5)
    ├── scraper.py           # Standalone Web Content Scraper (Playwright & Selenium)
    ├── google_news_crawler.py # Google News RSS Harvester (Zero-browser URL discovery)
    ├── sample_css_paths.csv # Pemetaan CSS Selector presisi 30+ media berita nasional
    ├── sample_urls.txt      # Berkas contoh daftar URL
    ├── test_qa_suite.py     # Test suite otomatis (17 pengujian unit & regresi)
    ├── requirements.txt     # Daftar dependensi dasar Python
    └── output/              # Folder penyimpanan hasil dataset (.md, .jsonl, .log)
```

---

## 🌟 Fitur Utama & Keunggulan

1. **Async Concurrency Pool (Opsi 1):** Manajemen konkurensi asinkron berbasis `asyncio.Semaphore` yang mengeksekusi multi-halaman secara simultan dengan proteksi penutupan resource (`try...finally`) agar tidak meninggalkan proses Chromium zombie.
2. **Hybrid Fast-Path Two-Tier (Opsi 2):**
   - **Tier 1 (Fast-Path):** HTTPX asynchronous direct fetch + Trafilatura untuk halaman berita statis/SSR. Memproses artikel hanya dalam waktu **90ms – 400ms** tanpa beban memori browser.
   - **Tier 2 (Browser Fallback):** Playwright Chromium dengan skrip stealth (`navigator.webdriver = undefined`), toleransi SSL daerah (`ignore_https_errors=True`), dan stabilisasi redirect Google News untuk halaman kompleks dengan proteksi WAF atau hidrasi React/Next.js.
3. **Semantic Deduplication (Opsi 3):** Deteksi berita sindikasi rilis pers kembar (kawat berita yang diterbitkan ulang oleh banyak portal) menggunakan N-gram Word Shingling ($k=2$). Menggabungkan metrik **Jaccard Similarity** dan **Containment Overlap** dengan *short-stub false-positive guard* untuk mengeliminasi duplikasi di atas ambang batas (default $80\%$).
4. **One-Click Orchestrator CLI (Opsi 5):** Perintah tunggal `pipeline.py` yang mengorkestrasi pencarian Google News RSS, decoding tautan, crawling hybrid, quality gate, deduplikasi, hingga ekspor multi-format.
5. **CPT Quality Gatekeeper:** Memfilter halaman non-artikel, teks galat/dump IP, halaman tantangan Cloudflare/WAF, serta potongan artikel terpotong langganan (*paywall stubs*).

---

## 🔒 Keamanan & Konfigurasi Lingkungan (.env)

> [!CAUTION]
> **KEBIJAKAN KEAMANAN KREDENSIAL:**
> Seluruh token otentikasi, API keys, dan kredensial proxy **HANYA** boleh disimpan di dalam berkas lokal `.env` dan **TIDAK PERNAH** ditulis ke dalam repositori, berkas dokumentasi, maupun skrip publik.
> Berkas `.env` telah didaftarkan ke dalam `.gitignore` untuk mencegah kebocoran secara tidak sengaja.

### Menyiapkan Berkas `.env`:

1. Salin berkas template `.env.example` menjadi `.env`:
   ```bash
   # Di Windows (PowerShell)
   Copy-Item .env.example .env

   # Di Linux / macOS
   cp .env.example .env
   ```

2. Buka berkas `.env` dan masukkan konfigurasi lokal Anda:
   ```env
   # Token autentikasi untuk binary ./aitf-engine (jika menggunakan AITF binary)
   CRAWLER_ENGINE_TOKEN=masukkan_token_pribadi_anda_disini

   # Pengaturan Proxy (Opsional jika diperlukan)
   # HTTP_PROXY=http://user:password@proxy-host:port
   # HTTPS_PROXY=http://user:password@proxy-host:port

   # Konfigurasi default pipeline Python (Opsional)
   # PIPELINE_CONCURRENCY=8
   # PIPELINE_SIM_THRESHOLD=0.80
   # PIPELINE_MIN_WORDS=25
   ```

Jika Anda menggunakan binary AITF Engine, variabel lingkungan `CRAWLER_ENGINE_TOKEN` akan otomatis dibaca oleh sistem tanpa perlu menuliskan token pada perintah terminal.

---

## 📦 Instalasi & Persiapan

### 1. Lingkungan Python (Untuk Modul Scrapper & Pipeline)

Disarankan menggunakan Python versi 3.10, 3.11, atau 3.12:

```bash
# 1. Buat dan aktifkan virtual environment (opsional namun disarankan)
python -m venv .venv

# Di Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Di Linux / macOS:
source .venv/bin/activate

# 2. Pasang paket dependensi utama
pip install -r Scrapper/requirements.txt
pip install trafilatura markdownify html2text httpx selectolax googlenewsdecoder

# 3. Unduh runtime browser Chromium untuk Playwright
python -m playwright install chromium
```

### 2. Lingkungan Binary AITF Engine (Sesuai OS)

* **Windows:** Jalankan PowerShell as Administrator di folder `Windows/` lalu eksekusi `.\windows-installer.ps1`.
* **Linux:** Masuk ke folder `Linux/`, berikan izin eksekusi `chmod +x linux-installer.sh`, lalu jalankan `./linux-installer.sh`.
* **macOS:** Masuk ke folder `MacOS/`, berikan izin eksekusi `chmod +x macos-installer.sh`, lalu jalankan `./macos-installer.sh`.

---

## 🚀 Panduan Penggunaan CLI

### 1. One-Click Pipeline Orchestrator (Rekomendasi Utama)

Berkas [`Scrapper/pipeline.py`](file:///e:/Coding/Coding/KOMDIGI/Crawler%20Mas%20Anjas/Scrapper/pipeline.py) adalah antarmuka terlengkap untuk membangun dataset CPT siap latih.

#### A. Crawling Topik Berita Terbaru (Google News RSS):
```bash
python Scrapper/pipeline.py --topic "Kecerdasan Buatan Indonesia" --when 7d --limit 30 --output Scrapper/output/dataset_cpt.md --format all --concurrency 8
```

#### B. Crawling Berdasarkan Berkas Daftar URL Kustom:
```bash
python Scrapper/pipeline.py --urls Scrapper/sample_urls.txt --output Scrapper/output/dataset_cpt.md --format all
```

#### Daftar Argumen CLI `pipeline.py`:
| Argumen | Alias | Tipe | Default | Penjelasan |
|---|---|---|---|---|
| `--topic` | `-t`, `-q` | `str` | `None` | Kata kunci topik berita yang dicari di Google News RSS. |
| `--urls` | `-u` | `str` | `None` | Path berkas teks daftar URL lokal (satu baris satu URL). |
| `--when` | `-w` | `str` | `7d` | Filter batas waktu kebaruan berita (`1d`, `3d`, `7d`, `30d`). |
| `--limit` | `-l` | `int` | `30` | Jumlah maksimal artikel yang diproses. |
| `--output` | `-o` | `str` | `Scrapper/output/dataset_cpt.md` | Path berkas target dataset luaran. |
| `--format` | `-f` | `str` | `all` | Format luaran yang dihasilkan: `md`, `jsonl`, atau `all`. |
| `--concurrency` | `-c` | `int` | `8` | Batas jumlah *worker* paralel asinkron. |
| `--sim-threshold` | `-s` | `float` | `0.80` | Ambang batas kemiripan deduplikasi semantik (0.0 – 1.0). |
| `--css-paths` | - | `str` | `Scrapper/sample_css_paths.csv` | File CSV pemetaan selector CSS per domain portal media. |
| `--default-css` | - | `str` | `body` | Selector CSS cadangan jika domain tidak ada di CSV. |
| `--min-words` | - | `int` | `25` | Batas minimal kata artikel agar lolos CPT Quality Gate. |
| `--headful` | - | `flag` | `False` | Tampilkan jendela grafis browser Playwright (mode inspeksi). |

---

### 2. Scraper CLI Mandiri (Playwright / Selenium)

Untuk kebutuhan scraping serial atau evaluasi CSS selector tertentu pada berkas URL:

```bash
# Mode gabung (merge) seluruh teks bersih ke 1 berkas Markdown
python Scrapper/scraper.py --urls Windows/output/crawler_url.txt --output Scrapper/output/hasil_merge.md --output-mode merge --css-path "body" --css-paths Scrapper/sample_css_paths.csv

# Mode simpan terpisah (each) menjadi satu berkas .md per URL
python Scrapper/scraper.py --urls Windows/output/crawler_url.txt --output Scrapper/output/artikel_terpisah/ --output-mode each
```

---

### 3. Google News RSS Harvester (Zero-Browser Discovery)

Untuk mengumpulkan URL berita kredibel tanpa membuka browser dan bebas risiko CAPTCHA:

```bash
python Scrapper/google_news_crawler.py --query "Transformasi Digital" --when 3d --limit 50 --output Scrapper/output/urls_google_news.txt
```

---

### 4. AITF Binary Engine (Google Search & Image)

Untuk menjalankan binary crawler Google Search menggunakan token yang telah dikonfigurasi di file `.env`:

```bash
# 1. Pastikan token sudah terdefinisi di variabel lingkungan shell atau .env
# Contoh di Windows (PowerShell):
$env:CRAWLER_ENGINE_TOKEN = (Get-Content .env | Select-String "CRAWLER_ENGINE_TOKEN=").ToString().Split("=")[1].Trim()

# Contoh di Linux / macOS:
export CRAWLER_ENGINE_TOKEN=$(grep -E '^CRAWLER_ENGINE_TOKEN=' .env | cut -d '=' -f2)

# 2. Eksekusi binary crawler (contoh di folder Windows)
cd Windows
.\aitf-engine.exe crawl -k "Kecerdasan Buatan" --keyword-type=keywords

# Mode Crawling Gambar
.\aitf-engine.exe crawl --search-image-mode=True -k "Infrastruktur Digital"

# Ekstraksi Teks Hasil Crawling
.\aitf-engine.exe extract-text -f output/crawler_url.txt
```

---

## 📊 Format Luaran Dataset

Pipeline ini menghasilkan 3 berkas output komplementer:

### 1. Berkas Markdown (`.md`)
Format dokumen ramah bacaan manusia dan LLM dengan pemisah `\n\n---\n\n`:
```markdown
# Judul Berita Utama Terverifikasi

> **Sumber:** [Media Nasional](https://www.portalmedia.com/berita/12345)
> **Tanggal Publikasi:** Wed, 14 Oct 2026 09:46:47 GMT
> **Jalur Ekstraksi:** `TIER1_FAST_PATH` | **Jumlah Kata:** 850 kata

Paragraf pertama isi berita yang sudah dibersihkan dari iklan dan widget...

Paragraf kedua dan kutipan narasumber yang terstruktur...
```

### 2. Berkas JSONL (`.jsonl`)
Format *line-delimited JSON* standar industri untuk *DataLoader* PyTorch / HuggingFace `datasets`:
```json
{"id": "cpt_doc_00001", "title": "Judul Berita", "url": "https://...", "source": "Media", "published_at": "...", "tier": "TIER1_FAST_PATH", "word_count": 850, "content": "Teks lengkap...", "crawled_at": "2026-10-16T10:00:00"}
```

### 3. Berkas Audit Quality Log (`.log`)
Laporan audit transparan yang mencatat metrik performa dan alasan penyaringan:
```text
=== PIPELINE AUDIT REPORT & QUALITY LOG ===
Waktu Eksekusi       : 2026-10-16 10:10:00
Topik Pencarian      : Kecerdasan Buatan Indonesia
Total URL Diproses   : 20
Total Lolos CPT Bersih: 18 artikel (14,250 kata)
  - Jalur Tier 1 (Fast-Path) : 17 artikel (94.4%)
  - Jalur Tier 2 (Playwright): 1 artikel (5.6%)
Total Duplikat Dieliminasi : 1 artikel (Ambang batas: 80%)
Total Ditolak Quality Gate : 1 artikel
Total Durasi Eksekusi: 12.45 detik (1.61 artikel/detik)
```

---

## 🧪 Pengujian QA & Regresi

Untuk memastikan integritas seluruh fungsi dan mencegah terjadinya regresi logika di masa depan, jalankan suite pengujian otomatis:

```bash
python Scrapper/test_qa_suite.py
```

Suite pengujian ini mencakup 17 skenario:
- [x] Deteksi duplikat URL persis ($O(1)$ lookup).
- [x] Eliminasi duplikasi rilis pers / sindikasi kawat berita ($\ge 80\%$).
- [x] Preservasi liputan berita independen pada topik yang sama ($< 80\%$).
- [x] Pencegahan *false-positive* deduplikasi pada ringkasan pendek (*stub-guard*).
- [x] Penyaringan layar tantangan Cloudflare WAF dan dump IP mentah.
- [x] Penyaringan potongan artikel berlangganan (*paywall stubs*).
- [x] Resolusi hierarki CSS selector (exact URL, subdomain, domain tanpa www, dan default fallback).
- [x] Pembersihan entitas HTML judul (`&#8211;`, `&amp;`, `&quot;`).
- [x] Verifikasi integritas format ekspor JSONL dan Markdown.

---

## 👥 Kontributor & Catatan Rilis

- **Arsitek & Pengembang:** Naufal Halim
- **Lingkungan Uji:** Windows 10/11, Python 3.10+, Playwright Chromium Engine, HTTPX Async.
- **Rilis Saat Ini:** Version 3.0 (Oktober 2026) – *Lihat detail teknis lengkap pada [CHANGELOG.md](file:///e:/Coding/Coding/KOMDIGI/Crawler%20Mas%20Anjas/CHANGELOG.md)*.