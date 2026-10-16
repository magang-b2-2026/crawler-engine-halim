# LOG PERUBAHAN & PENYEMPURNAAN SISTEM CRAWLER (CHANGELOG)

**Tanggal:** 16 Oktober 2026  
**Arsitek Sistem:** Naufal Halim  
**Repositori:** `Crawler Mas Anjas (AITF Engine & Web Content Scraper)`  
**Status QA:** ✅ 100% Passed (17 Unit & Regression Tests + Real-World Scenario Stress Tests)

---

## 1. Ringkasan Pembaruan Arsitektur Utama (v3.0)

| No | Opsi Peningkatan | Modul / Berkas | Deskripsi Implementasi | Status |
| :---: | :--- | :--- | :--- | :---: |
| 1 | **Opsi 1: Async Concurrency Pool** | `Scrapper/pipeline.py` | Worker pool asinkron berbasis `asyncio.Semaphore` dan Playwright async API untuk eksekusi scraping paralel berkecepatan tinggi. | ✅ Selesai |
| 2 | **Opsi 2: Hybrid Fast-Path (Two-Tier)** | `Scrapper/pipeline.py` | Ekstraksi dua tingkat: **Tier 1 (Fast-Path HTTPX + Trafilatura)** untuk portal statis (< 400ms) dan **Tier 2 (Async Playwright Stealth)** untuk WAF/JS-rendering. | ✅ Selesai |
| 3 | **Opsi 3: Semantic Deduplication** | `Scrapper/pipeline.py` | Filter duplikasi semantik menggunakan N-gram Shingling (Jaccard & Containment Overlap) guna mendeteksi dan membuang berita sindikasi/rilis pers kembar (> 80%). | ✅ Selesai |
| 4 | **Opsi 5: One-Click Pipeline CLI** | `Scrapper/pipeline.py` | Orkestrator terpadu satu perintah: Topik $\to$ Google News RSS Discovery $\to$ Batch URL Decoding $\to$ Hybrid Async Extraction $\to$ Quality Gate $\to$ Deduplikasi $\to$ Export Dataset (Markdown & JSONL). | ✅ Selesai |
| 5 | **Regresi & Testing QA Suite** | `Scrapper/test_qa_suite.py` | 17 pengujian otomatis menyeluruh untuk menguji logika filter CPT, routing CSS, de-entitizing HTML, deduplikasi, dan ekspor berkas. | ✅ Selesai |

---

## 2. Temuan Audit Logika & Bug Hunting (Cacat Sistem yang Berhasil Dibenahi)

Selama pengujian QA dan uji skenario, ditemukan 5 cacat logika kritis yang telah diidentifikasi dan dituntaskan:

1. **Cacat #1: Kebocoran Memori / Zombie Context pada Playwright**
   * *Masalah:* Blok `try` pada navigasi halaman menutup browser context di akhir alur normal. Jika terjadi timeout navigasi atau network drop, penutupan `context.close()` dan `page.close()` terlewati, meninggalkan proses Chromium zombie di background.
   * *Solusi:* Memindahkan seluruh pembersihan resource Playwright ke dalam blok `finally`, menjamin context dan page selalu ditutup tanpa peduli status error yang terjadi.

2. **Cacat #2: Kebocoran Entitas HTML pada Judul Artikel**
   * *Masalah:* Judul dari RSS atau metadata `<title>` kerap memuat kode entitas HTML seperti `&#8211;`, `&amp;`, `&quot;`, `&#039;`, dan spasi berlebih.
   * *Solusi:* Mengintegrasikan pustaka `html.unescape()` dan normalisasi spasi regex sebelum judul diformat ke Markdown maupun JSONL.

3. **Cacat #3: False Positive Deduplikasi pada Ringkasan Pendek (Containment Flaw)**
   * *Masalah:* Pada formula awal Containment Overlap ($\frac{|A \cap B|}{\min(|A|, |B|)}$), ringkasan pendek berisi 10 kata yang kebetulan memiliki 8 kata yang sama dengan artikel panjang 2000 kata akan menghasilkan containment 80% (false positive duplicate), menyebabkan artikel valid terbuang.
   * *Solusi:* Menambahkan guard: Containment hanya aktif jika kedua dokumen memiliki minimal 25 shingles dan rasio panjang kedua dokumen sebanding ($\frac{\min}{\max} \ge 0.35$).

4. **Cacat #4: Pemblokiran SSL pada Portal Berita Daerah / Instansi**
   * *Masalah:* Banyak media lokal dan portal daerah Indonesia (misal: `beritanasionalupdate.com`, situs pemkab) memiliki sertifikat SSL expired atau hostname mismatch (`ERR_CERT_COMMON_NAME_INVALID`).
   * *Solusi:* Mengonfigurasi `verify=False` pada HTTPX AsyncClient dan `ignore_https_errors=True` pada Playwright context, sehingga crawler dapat mengekstrak konten daerah secara andal.

5. **Cacat #5: Rusaknya Execution Context akibat Redirect Susulan Playwright**
   * *Masalah:* URL Google News redirect (`news.google.com/rss/articles/...`) melakukan navigasi dua tahap. Memanggil `page.evaluate()` saat navigasi kedua masih berjalan menyebabkan exception: `Execution context was destroyed, most likely because of a navigation`.
   * *Solusi:* Menambahkan stabilisasi URL (`wait_for_url` hingga keluar dari domain Google) dan wrapper retry pada `page.evaluate()` jika terdeteksi context destruction.

---

## 3. Hasil Benchmark Kecepatan & Uji Skenario

### Skenario 1: Topik "Kecerdasan Buatan Indonesia" (10 Artikel)
* **Waktu Total:** 10.01 detik (1.00 artikel / detik).
* **Throughput:** 10/10 artikel lolos CPT Bersih (8,322 kata).
* **Rasio Jalur:** 100% Tier 1 Fast-Path (rata-rata kecepatan 90ms - 635ms per artikel).

### Skenario 2: Topik "Komdigi Berantas Judi Online" (8 Artikel Media Nasional & Daerah)
* **Waktu Total:** 7.98 detik.
* **Throughput:** 8/8 artikel sukses (2,390 kata).
* **Uji Toleransi SSL:** Berhasil mengekstrak `beritanasionalupdate.com` yang memiliki certificate mismatch dalam 482ms tanpa error.

### Skenario 3: Uji Fallback Playwright Tier 2 (Link Dinamis Google News)
* **Waktu Ekstraksi:** 7.8 detik.
* **Hasil:** Mendarat di `detik.com`, CSS selector teresolusi dinamis ke `.detail__body-text`, ekstraksi 551 kata Markdown bersih dengan format ATX.

---

## 4. Cara Menjalankan Pipeline Produksi (Panduan Perintah)

### A. Eksekusi Satu Perintah (One-Click Pipeline):
```bash
python Scrapper/pipeline.py --topic "Kecerdasan Buatan Indonesia" --when 7d --limit 20 --output Scrapper/output/dataset_cpt.md --format all
```

### B. Opsi Argumen Lengkap:
* `--topic`, `-t`: Kata kunci topik berita Google News.
* `--urls`, `-u`: Menggunakan berkas daftar URL kustom (alternatif dari topik).
* `--when`, `-w`: Filter waktu kebaruan berita (`1d`, `3d`, `7d`, `30d`). Default: `7d`.
* `--limit`, `-l`: Batas maksimal artikel yang diambil. Default: `30`.
* `--output`, `-o`: Lokasi berkas dataset hasil. Default: `Scrapper/output/dataset_cpt.md`.
* `--format`, `-f`: Format luaran dataset (`md`, `jsonl`, atau `all`). Default: `all`.
* `--concurrency`, `-c`: Batas paralel worker asinkron. Default: `8`.
* `--sim-threshold`, `-s`: Ambang batas kemiripan deduplikasi semantik (0.0 - 1.0). Default: `0.80`.

### C. Menjalankan Regression Test Suite:
```bash
python Scrapper/test_qa_suite.py
```
*(Menjalankan 17 unit test otomatis untuk verifikasi kualitas dan keandalan sistem)*.
