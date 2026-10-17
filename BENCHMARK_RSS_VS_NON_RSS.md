# LAPORAN KOMPARASI & BENCHMARKING: RSS FEED vs NON-RSS DIRECT CRAWLING
## Evaluasi Performa Ekstraksi Skala Besar (100 Artikel) pada Engine Crawler v3.1

**Tanggal Pengujian:** 17 Oktober 2026  
**Peneliti / Penguji:** Tim AI & Data Engineering (Naufal Halim)  
**Lingkungan:** Windows 11 x64, Python 3.11 (`.venv`), Concurrency: 8 Async Workers, Two-Tier Hybrid Engine  
**Repositori:** `magang-b2-2026/crawler-engine-halim`

---

## 1. Abstrak & Latar Belakang

Sistem *Crawler Engine v3.1* mendukung dua moda utama pengumpulan konten web untuk kebutuhan dataset *Continual Pre-Training* (CPT) Large Language Model (LLM):
1. **Moda RSS Feed Harvester (Google News):** Menggunakan Google News RSS sebagai agregator berbasis kata kunci (*keyword-driven discovery*) dengan dekoder token base64 otomatis.
2. **Moda Non-RSS Direct Crawling (Web Index / Archive Pagination):** Menggunakan daftar URL artikel langsung yang dikumpulkan dari indeks/arsip penerbit berita (*domain-targeted crawling*).

Pengujian saintifik ini membandingkan kinerja kedua metode tersebut secara *head-to-head* pada skala beban kerja **100 artikel riil**, mengukur latensi end-to-end, throughput artikel per detik, efisiensi jaringan, serta kualitas korpus teks yang dihasilkan.

---

## 2. Tabel Ringkasan Hasil Benchmarking (100 Artikel)

| Metrik Evaluasi | Moda 1: Google News RSS Feed | Moda 2: Non-RSS Direct Web Crawl | Selisih / Rasio Komparasi |
| :--- | :---: | :---: | :---: |
| **Sumber Data** | Google News RSS Feed (*"Kecerdasan Buatan"*) | Indeks Berita Langsung (Antara, Kompas, Detik, CNN) | Agregator Multi-Media vs Direct Editorial Archive |
| **Beban Uji Target** | 100 Artikel | 100 Artikel | Identik (100 Target) |
| **Artikel Lolos CPT Bersih** | **97 Artikel** | **99 Artikel** | +2 artikel pada Non-RSS |
| **Total Korpus Kata Bersih** | **50.342 kata** | **38.174 kata** | Bergantung pada panjang editorial berita |
| **Rata-rata Kata / Artikel** | 519 kata | 385 kata | - |
| **Duplikat Dieliminasi** | 1 Artikel (1%) | 1 Artikel (1%) | Filter Semantik 100% konsisten |
| **Artikel Gagal / Ditolak WAF** | 2 Artikel (Akamai HTTP 403) | 0 Artikel (0%) | Non-RSS 100% bebas blokir |
| **Rasio Jalur Ekstraksi** | 98 Fast-Path (Tier 1) | 99 Fast-Path (Tier 1) | ~99% Tier 1 Fast-Path pada kedua moda |
| **Total Waktu Eksekusi** | **68,85 detik** | **18,81 detik** | **Non-RSS 3,66x LEBIH CEPAT** ⚡ |
| **Throughput Kecepatan** | **1,41 artikel / detik** | **5,32 artikel / detik** | **Peningkatan +277% throughput** |
| **Hop Jaringan / Artikel** | 2 Hops (Google RSS Token $\to$ Publisher) | 1 Hop (Direct Publisher Endpoint) | 50% lebih hemat request jaringan |
| **Format Output** | 97 File `.md` + JSONL + Log | 99 File `.md` + JSONL + Log | 1 File per Artikel (`--output-mode each`) |

---

## 3. Diagram Alur & Arsitektur Eksekusi

```
========================================================================================
ALUR MODA 1: GOOGLE NEWS RSS FEED (Topic-Driven)
========================================================================================
[ Query Topik ]
      │
      ▼
[ Google News RSS ] ──> [ Obfuscated Token ] ──> [ Batch URL Decoder ] ──> [ Two-Tier Engine ]
  (1 request)            (news.google.com/...)     (100 sub-requests)      (100 async workers)
                                                                                  │
                                                                           Total: 68.85s (1.41 art/s)

========================================================================================
ALUR MODA 2: NON-RSS DIRECT CRAWLING (Targeted-Domain / URLs)
========================================================================================
[ Indeks Portal / URLs File ]
      │
      ▼
[ Direct Publisher URLs ] ───────────────────────────────────────────────> [ Two-Tier Engine ]
  (Langsung ke domain target)                                               (100 async workers)
                                                                                  │
                                                                           Total: 18.81s (5.32 art/s)
========================================================================================
```

---

## 4. Analisis Teknis & Penyebab Disparitas Performa

### A. Faktor Latensi Token Decoding (Overhead Hop Jaringan)
Pada Moda 1 (Google News RSS), Google tidak menyediakan URL penerbit dalam bentuk *plain-text*, melainkan token redirect terenkripsi base64 seperti:
`https://news.google.com/rss/articles/CBMiWmh0dHBzOi8vd3d3LmFudGFyYW5ld3MuY29t...`

Sebelum konten artikel dapat diunduh, modul `google_news_crawler.py` harus memecahkan token ini terlebih dahulu via *batch decoding* atau *HTTP HEAD/GET request*. Proses ini menambahkan **1 round-trip network hop ekstra** per artikel.

Sebaliknya, pada Moda 2 (Non-RSS), URL yang dimasukkan sudah merupakan *canonical target URL* (misal: `https://news.detik.com/berita/d-8711775/...`), sehingga worker pool langsung mengekstrak konten tanpa *pre-flight handshake*.

### B. Distribusi Domain & Toleransi WAF
* **Google News RSS:** Menghasilkan sebaran domain yang sangat heterogen (ratusan portal lokal hingga portal korporasi). Beberapa portal kecil menerapkan WAF agresif (seperti Akamai pada `megasyariah.co.id` yang menghasilkan HTTP 403), membutuhkan waktu tunggu hingga batas timeout sebelum dialihkan atau ditolak.
* **Non-RSS Direct Crawling:** Mengarah langsung ke domain media bereputasi tinggi dengan CDN berkapasitas besar (Detik, Kompas, Antara, CNN) yang melayani permintaan HTTP/2 dengan respons rata-rata di bawah 400ms.

### C. Konsistensi Sanitasi CPT Teks
Kedua metode menunjukkan kualitas sanitasi teks yang identik:
1. **Normalisasi ASCII Quotes:** 100% kutipan typographic (`“`, `”`, `«`, `»`) sukses dikonversi menjadi ASCII 34 (`"`).
2. **Dateline Removal:** Dateline media (seperti `JAKARTA, KOMPAS.com - `, `**Jakarta**-`, `(ANTARA) - `) berhasil dipotong bersih sehingga teks artikel langsung diawali inti informasi.
3. **Pembersihan Noise:** Tautan rekomendasi (*"Baca juga"*, inisial editor `(anl/ega)`) dibersihkan secara konsisten tanpa merusak struktur Markdown.

---

## 5. Matriks Kelebihan, Kekurangan, dan Rekomendasi Penggunaan

| Kriteria Evaluasi | Moda 1: RSS Feed (Google News) | Moda 2: Non-RSS Direct Crawling |
| :--- | :--- | :--- |
| **Kelebihan Utama** | • **Otomasi Penuh:** Cukup tentukan kata kunci, engine mencari berita secara mandiri.<br>• **Diversitas Sumber Luas:** Menjangkau puluhan portal berita berbeda dalam satu perintah.<br>• **Filter Kebaruan:** Mendukung filter waktu presisi (`--when 1d`, `7d`, `30d`). | • **Kecepatan Maksimal:** 3,6x lebih cepat (5,32 artikel/detik).<br>• **Determinisme Tinggi:** URL dapat dikurasi sebelumnya sesuai whitelist portal terpercaya.<br>• **Nir-Overhead:** Tanpa jeda decoding redirect Google.<br>• **Ketahanan WAF:** Minim terkena false-positive blokir bot. |
| **Kekurangan** | • Latensi lebih tinggi karena proses decode token redirect.<br>• Rentan bias domain institusi jika tanpa exclusion operator (`-site:`). | • Memerlukan tahap pengumpulan daftar URL awal (via file teks atau sitemap). |
| **Kapan Harus Digunakan?** | **Eksplorasi Topik Dinamis & Cepat:**<br>Cocok saat membutuhkan artikel terkini tentang topik tertentu (misal: *"Regulasi AI Indonesia"*, *"Subsidi Energi"*) tanpa repot mencari link satu per satu. | **Produksi Korpus Skala Besar (Massive CPT Corpus):**<br>Cocok untuk ekstraksi massal ribuan artikel dari daftar sitemap portal terpercaya, web arsip instansi/kementerian, atau basis data riset internal. |

---

## 6. Panduan Menjalankan Kedua Uji Komparasi

### A. Menjalankan Uji Coba Moda 1 (Google News RSS Feed 100 Artikel):
```powershell
python Scrapper/pipeline.py --topic "Kecerdasan Buatan" --when 7d --limit 100 --output Scrapper/output/dataset_cpt_100 --output-mode each --concurrency 8
```

### B. Menjalankan Uji Coba Moda 2 (Non-RSS Direct Crawling 100 Artikel):
1. Siapkan file teks berisi 100 URL langsung (misal: `Scrapper/output/test_non_rss_100_urls.txt`).
2. Jalankan perintah:
```powershell
python Scrapper/pipeline.py --urls Scrapper/output/test_non_rss_100_urls.txt --limit 100 --output Scrapper/output/dataset_non_rss_100 --output-mode each --concurrency 8
```

---

## 7. Kesimpulan Akhir

1. **Fleksibilitas Arsitektur:** Crawler Engine v3.1 terbukti mampu menangani input berbasis *agregator topik* maupun *daftar URL mentah* dengan standar kualitas output (CPT Sanitizer, Quality Gate, dan Format Markdown) yang setara 100%.
2. **Efisiensi:** Jika daftar URL sudah tersedia atau di-generate via sitemap/crawler pagination, **Moda Non-RSS Direct Crawling adalah opsi superior** dari segi kecepatan komputasi, mampu memproses **100 artikel hanya dalam 18,8 detik** (5,32 artikel/detik).
