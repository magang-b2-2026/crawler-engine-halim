# Web Content Scraper & Pipeline Orchestrator (Edisi Produksi v3.0)

Ecosystem crawler canggih untuk pembuatan dataset **Continual Pre-Training (CPT) LLM** berkualitas tinggi dengan arsitektur **Hybrid Asinkron Dua Tingkat**, **Deduplikasi Semantik N-gram**, dan integrasi **Google News RSS**.

---

## 🚀 Fitur Utama & Peningkatan Arsitektur

### 1. Opsi 1: Async Concurrency Pool
- Menggunakan `asyncio.Semaphore` dan Playwright Async API.
- Menjalankan scraping secara paralel multi-tab/context, meningkatkan throughput hingga **10x lipat** tanpa pemborosan memori.
- Manajemen siklus hidup peramban terproteksi dengan pembersihan resource otomatis (`finally` blocks) untuk mencegah *zombie Chromium processes*.

### 2. Opsi 2: Hybrid Fast-Path (Dua Tingkat Ekstraksi)
- **Tier 1 (Fast-Path HTTPX + Trafilatura):** Mengambil konten langsung via request HTTP asinkron berkecepatan tinggi (< 400ms per artikel). Tanpa overhead Chromium browser untuk halaman statis / SSR.
- **Tier 2 (Async Playwright Stealth Fallback):** Diaktifkan secara otomatis hanya jika halaman membutuhkan eksekusi JavaScript (Next.js/React), melewati Cloudflare/WAF, atau resolusi tautan redirect dinamis.
- **Toleransi SSL Daerah:** Dilengkapi dengan toleransi sertifikat tidak valid (`verify=False` & `ignore_https_errors=True`) agar portal berita daerah dan instansi pemerintah tetap dapat diindeks tanpa terhalang SSL hostname mismatch.

### 3. Opsi 3: Semantic Deduplication (N-gram Shingling)
- Mendeteksi dan membuang artikel kembar/sindikasi rilis pers (misal kawat Antara yang diterbitkan ulang oleh puluhan portal media) dengan ambang batas kemiripan $\ge 80\%$.
- Menggabungkan metrik **Jaccard Similarity** dan **Containment Overlap** dengan mitigasi *short-stub false positive guard*.
- Seluruh artikel yang tereliminasi dicatat transparan di berkas audit `.log` beserta skor kemiripan dan URL sumber aslinya.

### 4. Opsi 5: One-Click Pipeline Orchestrator (`pipeline.py`)
Satu perintah langsung menjalankan seluruh rantai proses:
$$\text{Topik/Kueri} \longrightarrow \text{Google News RSS} \longrightarrow \text{URL Decoding} \longrightarrow \text{Hybrid Async} \longrightarrow \text{Quality Gate} \longrightarrow \text{Deduplikasi} \longrightarrow \text{Dataset MD \& JSONL}$$

---

## 📦 Instalasi & Persiapan Lingkungan

1. Pasang dependensi Python:
   ```bash
   pip install -r Scrapper/requirements.txt
   pip install trafilatura markdownify html2text httpx selectolax googlenewsdecoder
   ```

2. Pasang binary browser Playwright:
   ```bash
   python -m playwright install chromium
   ```

---

## ⚡ Panduan Penggunaan CLI

### 1. Jalur Utama: One-Click Pipeline Orchestrator (`pipeline.py`)

#### Mengambil Berita dari Topik Google News:
```bash
python Scrapper/pipeline.py --topic "Kecerdasan Buatan Indonesia" --when 7d --limit 20 --output Scrapper/output/dataset_cpt.md --format all
```

#### Menggunakan Berkas Daftar URL Kustom:
```bash
python Scrapper/pipeline.py --urls Scrapper/sample_urls.txt --output Scrapper/output/dataset_cpt.md --format all
```

#### Argumen CLI Lengkap:
| Parameter | Alias | Deskripsi | Default |
|---|---|---|---|
| `--topic` | `-t`, `-q` | Kata kunci pencarian Google News | *Opsional jika pakai `--urls`* |
| `--urls` | `-u` | Berkas daftar URL kustom (1 per baris) | *Opsional jika pakai `--topic`* |
| `--when` | `-w` | Filter kebaruan Google News (`1d`, `3d`, `7d`, `30d`) | `7d` |
| `--limit` | `-l` | Batas jumlah artikel yang diambil | `30` |
| `--output` | `-o` | Lokasi berkas dataset hasil | `Scrapper/output/dataset_cpt.md` |
| `--format` | `-f` | Format luaran: `md`, `jsonl`, atau `all` | `all` |
| `--concurrency` | `-c` | Batas worker paralel asinkron | `8` |
| `--sim-threshold` | `-s` | Ambang batas deduplikasi semantik (0.0 - 1.0) | `0.80` (80%) |
| `--css-paths` | - | Lokasi CSV pemetaan CSS selector | `Scrapper/sample_css_paths.csv` |
| `--default-css` | - | Selector default jika domain belum terdaftar | `body` |
| `--min-words` | - | Batas minimal kata CPT Quality Gate | `25` |
| `--headful` | - | Tampilkan antarmuka browser Playwright | `False` (Headless) |

---

### 2. Jalur Klasik: Scraper CLI Mandiri (`scraper.py`)
Untuk kebutuhan penarikan statis/serial dari file daftar URL:
```bash
python Scrapper/scraper.py --urls=Windows/output/crawler_url.txt --output=Scrapper/output/dataset_cpt.md --output-mode=merge --css-path="body" --css-paths=Scrapper/sample_css_paths.csv
```

---

## 🧪 Pengujian Kualitas & Regresi (QA Test Suite)

Sistem dilengkapi dengan test suite otomatis (`test_qa_suite.py`) yang menguji 17 skenario:
```bash
python Scrapper/test_qa_suite.py
```

Item yang diuji mencakup:
* ✅ Pencegahan False-Positive pada deduplikasi ringkasan pendek.
* ✅ Deteksi berita sindikasi rilis pers kembar (>80%).
* ✅ Preservasi liputan berita independen (<80%).
* ✅ Penyaringan halaman tantangan Cloudflare/WAF dan IP dump mentah.
* ✅ Penyaringan halaman stub berbayar (paywall subscription).
* ✅ Resolusi CSS path per subdomain, domain tanpa www, dan default selector `body`.
* ✅ Pembersihan entitas HTML judul (`&#8211;`, `&amp;`).
* ✅ Integritas skema data JSONL dan pemisah dokumen Markdown (`---`).

---

## 📂 Struktur Berkas Luaran Dataset

Setiap eksekusi pipeline menghasilkan 3 berkas terstandarisasi:
1. **`.md`**: Dataset Markdown bersih terstandarisasi CPT (dengan metadata sumber, tanggal, dan jalur ekstraksi).
2. **`.jsonl`**: Format dataset per-baris JSON yang siap diumpankan ke HuggingFace Datasets / PyTorch DataLoader:
   ```json
   {"id": "cpt_doc_00001", "title": "...", "url": "...", "source": "...", "published_at": "...", "tier": "TIER1_FAST_PATH", "word_count": 553, "content": "...", "crawled_at": "..."}
   ```
3. **`.log`**: Berkas audit kualitas yang mencatat durasi, rasio Fast-Path vs Playwright, daftar artikel ditolak (beserta alasannya), dan daftar artikel duplikat yang dieliminasi.
