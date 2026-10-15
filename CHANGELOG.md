# LOG PERUBAHAN & PENYEMPURNAAN SISTEM CRAWLER (CHANGELOG)

**Tanggal:** 15 Oktober 2026  
**Arsitek Sistem:** Naufal Halim  
**Repositori:** `Crawler Mas Anjas (AITF Engine & Web Content Scraper)`  
**Status QA:** ✅ Passed (100% Verified)

---

## 1. Ringkasan Pembaruan Utama

| No | Modul / Komponen | Perubahan yang Diterapkan | Status |
| :--- | :--- | :--- | :---: |
| 1 | `Scrapper/scraper.py` | Mengubah nilai default `--css-path` dari `"body p"` menjadi `"body"`. | ✅ Selesai |
| 2 | `Scrapper/sample_css_paths.csv` | Menambahkan pemetaan CSS Selector 30+ media berita kredibel (Google News & Inilah.com). | ✅ Selesai |
| 3 | `Scrapper/scraper.py` | Mengubah mekanisme ekstraksi JavaScript dari `innerText` ke `innerHTML`. | ✅ Selesai |
| 4 | `Scrapper/scraper.py` | Integrasi library Python `trafilatura` dan `markdownify` untuk konversi otomatis HTML ke Markdown. | ✅ Selesai |
| 5 | `Scrapper/google_news_crawler.py` | Membuat engine discovery baru berbasis Google News RSS (`news.google.com/rss/search`) + sintaks `when:Nd`. | ✅ Selesai |
| 6 | Infrastruktur Proyek | Inisialisasi **CodeGraph** (`.codegraph`) dan pelacakan commit **Git lokal**. | ✅ Selesai |

---

## 2. Rincian Teknis Implementasi

### A. Default Selector `"body"` & Ekstraksi `innerHTML`
* **Sebelum:** Scraper menggunakan `body p` dan `.innerText`. Akibatnya, subjudul (`<h2>`, `<h3>`), tabel, daftar (`<ul>`, `<ol>`), serta teks di luar tag `<p>` hilang atau menggumpal tidak beraturan.
* **Sesudah:** Scraper menargetkan kontainer artikel atau `"body"` secara default, lalu mengekstrak `innerHTML` lengkap sehingga seluruh elemen semantik (heading, list, paragraf) tertangkap utuh.

### B. Konverter Otomatis HTML ke Markdown (`trafilatura` & `markdownify`)
* Menggabungkan dua teknologi pemrosesan teks standar AI:
  1. **`trafilatura`**: Secara cerdas menyaring elemen boilerplate (iklan Google AdSense, banner sponsor, navigasi, dan tombol medsos) langsung ke Markdown bersih.
  2. **`markdownify`**: Mengubah tag HTML spesifik menjadi sintaks Markdown ATX (`# Judul`, `## Subjudul`, `- Bullet`, `1. Nomor`, `| Tabel |`).
* Menambahkan blok header Markdown otomatis:
  ```markdown
  # [Judul Halaman / Berita]
  > Sumber: https://...
  ```

### C. Pemetaan 30+ Portal Berita Kredibel (`sample_css_paths.csv`)
Telah didefinisikan selektor CSS presisi untuk media berita yang sering diagregasi oleh Google News Indonesia:
* `inilah.com` $\rightarrow$ `"h1, div.MuiContainer-root p, div[class*='MuiBox'] p, article"` (Next.js / Material-UI)
* `merdeka.com` $\rightarrow$ `"div.articles-content, div.articles-content__body"`
* `kompas.com` $\rightarrow$ `"div.read__article, div.read__content, article"`
* `detik.com` $\rightarrow$ `"div.detail__body-text, article.detail"`
* `tempo.co` $\rightarrow$ `"div.detail-konten, article.detail-artikel, div#isi"`
* `cnnindonesia.com` $\rightarrow$ `"div.detail-text, div#detikdetailtext"`
* `cnbcindonesia.com` $\rightarrow$ `"div.detail_text, div.detail-box"`
* `antaranews.com`, `kumparan.com`, `tirto.id`, `bisnis.com`, `kontan.co.id`, `katadata.co.id`, `republika.co.id`, `suara.com`, `sindonews.com`, `mediaindonesia.com`, `jawapos.com`, `viva.co.id`, `idntimes.com`, dll.

### D. Google News RSS Discovery Engine (`google_news_crawler.py`)
* Memanfaatkan endpoint pencarian resmi Google News:
  `https://news.google.com/rss/search?q={query}+when:{when}&hl=id&gl=ID&ceid=ID:id`
* **Keunggulan:**
  * Zero-browser (tidak memerlukan Chrome/Selenium pada tahap penemuan).
  * Kecepatan tinggi (< 2 detik untuk mengambil 100 URL).
  * Bebas dari ancaman pemblokiran CAPTCHA Google Search.
  * Mendukung filter kebaruan waktu (`when:1d`, `when:7d`, `when:30d`).

---

## 3. Hasil Pengujian QA (Quality Assurance)

### Uji 1: Ekstraksi Halaman Resep & Berita (Merdeka.com)
* **Target:** `https://www.merdeka.com/trending/read/7967897/...`
* **Hasil:**
  * Berhasil mengekstrak 748 kata Markdown.
  * 4 Subjudul (`##`) terformat sempurna.
  * Iklan `<div id="div-gpt-ad...">` otomatis dilenyapkan.
  * Lolos CPT Quality Gatekeeper.

### Uji 2: Ekstraksi Google News RSS
* **Kueri:** `"Kecerdasan Buatan" when:3d`
* **Hasil:** Menemukan 100 artikel kredibel (Kontan, Kompas, Canva/Kemenag, IDNFinancials, dll.) dalam waktu 1.8 detik dan disimpan ke `output/google_news_sample.txt`.

---

## 4. Pelacakan Repositori & CodeGraph
* **CodeGraph:** Diinisialisasi (`codegraph init`), menghasilkan indeks 7 berkas kode dengan 28 node dan 44 edge relasi.
* **Git:** Status perubahan disimpan secara lokal tanpa remote push ke GitHub sesuai batasan proyek.
