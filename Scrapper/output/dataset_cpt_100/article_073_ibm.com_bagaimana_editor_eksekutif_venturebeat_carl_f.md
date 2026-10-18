# Bagaimana Editor Eksekutif VentureBeat Carl Franzen menggunakan AI untuk melaporkan, menulis, dan membangun | IBM®

> **Sumber:** [IBM](https://www.ibm.com/id-id/think/news/how-venturebeat-executive-editor-carl-franzen-uses-ai-report-write-build)
> **Tanggal Publikasi:** Mon, 12 Oct 2026 07:00:00 GMT
> **Jalur Ekstraksi:** `TIER1_FAST_PATH` | **Jumlah Kata:** 2021 kata

Carl Franzen, Editor Eksekutif *VentureBeat*, sebuah publikasi teknologi yang berfokus pada AI untuk pengambil keputusan perusahaan, telah menjadikan AI bagian sentral dari bagaimana ia melaporkan, menulis, dan bereksperimen dengan berbagai bentuk penerbitan baru.

Franzen menggunakan berbagai alat, termasuk ChatGPT, Claude, dan Firecrawl, untuk melakukan riset dan menyusun draf. Ia juga mengembangkan proyek independen, seperti publikasi berita otomatis One Big Story. Kepada *IBM® Think* ia mengatakan bahwa AI telah memperluas secara signifikan apa yang dapat ia kerjakan sendiri. Meski demikian, ia tetap memeriksa setiap baris teks, tautan, dan klaim faktual secara langsung sebelum menerbitkannya

Wawancara berikut dengan Franzen telah diedit untuk panjang dan kejelasan.

ChatGPT pada berlangganan Plus (terutama GPT-6 Astra dan GPT-6 Sol); Claude Opus 5.5 dari Anthropic (dan 4.8, favorit lama saya!) melalui berlangganan Claude Pro, Claude Code di terminal; ChatGPT Images 2.5 melalui ChatGPT; fal.ai; Midjourney; dan Firecrawl.

Agregator berita AI eksperimental saya One Big Story, menelusuri ribuan media berita dan menggunakan prompt yang telah ditetapkan untuk menemukan berita yang paling berdampak bagi seluruh penduduk Bumi pada hari itu, berita tersebut kemudian dirangkum dan dikembangkan dengan informasi tambahan menjadi berbagai format, seperti video, audio, artikel panjang, sesi tanya jawab melalui chatbot, atau kreasi acak seperti soneta dan naskah teater. Layanan ini berjalan di atas tumpukan teknologi berbasis berbagai model AI yang saya bangun sendiri dengan pendekatan vibe coding, termasuk Perplexity Sonar dan FLUX (yang terakhir melalui fal.ai), serta banyak model lainnya. Saya telah mengunggah daftar lengkapnya secara online bagi siapa pun yang tertarik.

**Email dan penyusunan**: Saya menghubungkan ChatGPT ke email pekerjaan saya dan Claude terhubung ke email pribadi saya. Dalam kedua kasus tersebut, AI bertindak sebagai penyaring, draf tanggapan, dan draf email dan artikel.

**Riset:** ChatGPT dan Claude adalah asisten riset utama saya, dan Firecrawl membantu saya memberi mereka salinan bersih dari materi sumber saya (lebih lanjut tentang itu di bawah).

**Seni:** *Saya menggunakan ChatGPT Images 2.5 atau Midvoyage untuk membuat seni kustom asli untuk setiap cerita saya yang diterbitkan di VentureBeat.* Saya bangga dengan gambar-gambar ini. Menurut pendapat saya, gambar-gambar ini jauh lebih menarik bagi pembaca daripada citra stok generik yang merupakan default pra-AI kami.

**Bangunan:** Claude Code adalah pembangun saya. Di *VentureBeat*, saya membuat Slackbot yang menggunakan API Claude untuk memantau saluran editorial kami, mengurutkan tautan yang dibagikan tim kami ke dalam kategori buletin, dan menulis ringkasan ke dalam Google Doc bersama, sehingga sebagian besar isi buletin sudah tersusun sebelum siapa pun mulai menulis. Slackbot ini berjalan di Google Cloud dan merupakan jenis alat internal yang sebelumnya harus saya ajukan permintaannya kepada tim teknik untuk dibuatkan.

Saya bertanya kepada ChatGPT dan Claude apakah ada email menarik yang saya terima, lalu keduanya menampilkan beberapa email pilihan. Setelah itu, saya meminta mereka menyusun draf balasan untuk email yang paling menarik atau memerlukan tindak lanjut. Jika sebuah email berisi materi yang berpotensi menjadi artikel, saya meminta AI membuat draf awal untuk saya tinjau dan kembangkan. Selama proses tersebut, saya memberikan dokumen sumber dan halaman web yang relevan sebagai referensi.Setelah draf artikel selesai disusun dan diedit, atau terkadang saat proses penulisan masih berlangsung, saya menggunakan ChatGPT Images 2.5 untuk menghasilkan gambar orisinal.

Di mana saya masih lebih suka bekerja tanpanya: bacaan terakhir. Saya memeriksa setiap baris dan kata sendiri, memeriksa setiap tautan dan sering menulis ulang bagian atas cerita sehingga informasi yang paling penting mendarat di beberapa paragraf pertama.

Ada begitu banyak model AI yang sangat terspesialisasi, bersifat sumber terbuka, atau tersedia dengan biaya rendah melalui antarmuka pemrograman aplikasi (API) atau Protokol Konteks Model (MCP). Model-model tersebut memungkinkan pengembangan produk berbasis AI native dengan biaya yang sangat terjangkau. Mintalah model garis depan AI seperti Claude atau ChatGPT untuk membantu Anda menemukan model-model tersebut dan memanfaatkannya. Biaya operasional otomatis One Big Story hanya sekitar 5 hingga 10 USD per bulan.

Banyak pengguna AI intensif yang saya kenal kini beralih menggunakan prompt yang lebih sederhana dengan model yang lebih canggih. Pengalaman saya justru sebaliknya. Semakin terperinci prompt yang saya berikan, dalam batas yang wajar, semakin sering saya mendapatkan output yang langsung dapat digunakan sejak "one-shot" (percobaan pertama).

Teman sekaligus mantan rekan kerja saya, Michael Nuñez, menyarankan agar saya lebih sering mendiktekan instruksi kepada model AI, meskipun model tersebut tidak selalu menangkap kata-kata yang saya ucapkan dengan tepat. Saya mulai lebih sering melakukannya, tetapi sejauh ini belum merasakan peningkatan produktivitas atau perubahan besar seperti yang dialaminya. Mungkin penyebabnya adalah cara bicara saya yang terlalu cepat atau pelafalan saya yang kurang jelas.

Ini adalah alat percakapan berbasis giliran. Jika Anda mengharapkan output "one-shot" yang sempurna dari prompt pertama Anda, Anda mungkin akan kecewa. Setidaknya, begitulah yang pernah saya alami.

Dengan menggunakan model AI secara rutin, tingkat keberhasilan saya mendapatkan hasil yang tepat dalam sekali percobaan (one-shot) meningkat. Namun, hasil terbaik yang saya capai dengan AI tetap berasal dari interaksi multi-putaran. Saya berdiskusi bolak-balik dengan model, terus menyempurnakan ide, memintanya melakukan riset web lebih lanjut (dengan menyertakan sitasi), membandingkan temuan, dan mengidentifikasi hal-hal yang membedakan satu temuan dari yang lain. Sepanjang proses tersebut, saya terus mengarahkan model pada bidang yang paling menarik bagi saya atau yang menurut saya paling relevan bagi audiens.

Tentu saja. Saya sekarang memulai hampir semua pekerjaan saya dengan AI. Saya menggunakannya untuk menyaring ide-ide yang ingin saya ajukan dan menata gagasan, serta sebagai alat utama untuk melakukan riset di web: AI ini menelusuri informasi sumber yang saya butuhkan, lalu merangkumnya untuk saya, lengkap dengan sitasi dan tautan sumber agar saya dapat memverifikasi sendiri angka-angka yang disajikan.

Untuk pelaporan dan riset, AI adalah antarmuka utama saya ke web. Saya masih menggunakan Google, tetapi terutama untuk mencari jawaban cepat atas pertanyaan sehari-hari di rumah, misalnya berapa lama tortilla yang disimpan di lemari es masih aman dikonsumsi setelah melewati tanggal batas penjualan. Menurut saya, fitur AI Overviews umumnya cukup membantu untuk kebutuhan tersebut maupun untuk beberapa topik riset yang lebih luas, meskipun saya menyadari bahwa fitur ini juga mengurangi jumlah kunjungan ke situs web seperti tempat saya bekerja, *VentureBeat*.

Saya tidak pernah mempublikasikan draf AI langsung ke situs. Saya selalu membaca setiap baris dan kata dan memeriksa setiap tautan dan informasi yang bersumber di dalamnya untuk memastikannya direpresentasikan secara akurat. Saya sering mendapati diri saya menulis ulang, atau mendorong ulang AI, untuk menarik "daging" cerita ke dalam beberapa paragraf pertama bagi pembaca kami.

Saya sependapat dengan mereka yang mengatakan bahwa penggunaan AI sebaiknya diizinkan secara luas, termasuk untuk menulis dan menyusun draf yang diterbitkan atas nama penulis manusia yang sebenarnya. Namun, penulis yang namanya tercantum sebagai penulis harus selalu bertanggung jawab atas seluruh konten yang dihasilkan AI dan kemudian diunggah ke internet atau diterbitkan di media mana pun. Menurut saya, merancang atau menggunakan karakter yang sepenuhnya dihasilkan AI untuk berperan sebagai "jurnalis", seperti yang kabarnya dilakukan oleh beberapa situs, bukanlah praktik yang baik.

Untuk menulis karya fiksi pribadi dan jurnal, saya masih sepenuhnya melakukannya secara manual. Saya menikmati proses mengembangkan ide-ide kreatif dan merangkai kata-kata dengan gaya saya sendiri, sehingga saya tidak ingin menyerahkan proses penulisan tersebut kepada AI. Namun, ketika menulis untuk menyelesaikan tugas khusus, bukan sekadar menyalurkan imajinasi, saya banyak memanfaatkan AI.

Menurut saya, sebagian besar ruang redaksi yang pernah saya dengar masih terlalu lambat dan terlalu berhati-hati dalam mengadopsi AI. Seperti yang kita lihat pada Google Search, AI dapat menjadi alat yang sangat bermanfaat dan transformatif bagi jurnalisme jika dimanfaatkan secara intensif, dengan tetap menggunakannya secara bijak dan terarah.

Ada kemungkinan untuk berlebihan dan mempercayainya terlalu mutlak. Tetapi sebagian besar publikasi arus utama yang saya sadari tampaknya mengambil pendekatan yang berlawanan: mereka tidak cukup mempercayainya atau potensinya.

Saya selalu memeriksa tautan sumber yang mendasarinya untuk klaim faktual yang dibuat AI, dan saya akan menyarankan siapa pun yang bekerja di bidang yang bergantung pada informasi yang jujur dan akurat untuk melakukan hal yang sama.

Model-model terbaru telah menjadi jauh lebih baik tentang halusinasi, tetapi mereka kadang-kadang masih mengubah informasi dari satu sumber ke sumber lain, melewatkan informasi yang paling penting atau salah menghubungkannya. Berada secara online dan banyak membaca membantu saya menangkap kesalahan semacam ini.

Pekerjaan back-office, integrasi chatbot untuk berinteraksi dengan pelanggan (termasuk model suara untuk menangani panggilan pelanggan), serta berbagai jenis pengelolaan dan transformasi informasi. Contohnya meliputi mengatalogkan dan memproses faktur, mengubah informasi dari satu format ke format lain (misalnya, dari dasbor data menjadi presentasi slide), melacak persediaan dan pesanan, serta memantau berbagai sumber data yang sangat besar dan beragam.

Dari apa yang saya lihat dalam pelaporan saya, AI telah membuat semua tugas dan proses ini jauh lebih efisien.

Saya pikir banyak perusahaan terlalu bergantung pada mendapatkan AI hanya dari merek perusahaan lama yang tepercaya... ketika ada banyak startup baru dan model sumber terbuka yang menarik untuk dipilih.

Hal terburuk yang dapat dilakukan organisasi yang ingin memanfaatkan AI adalah melarang karyawannya, terutama para pemimpin, karyawan berkinerja tinggi, serta mereka yang bekerja di bidang kreatif dan kaya informasi menggunakan berbagai alat baru yang menarik minat mereka. Biarkan orang-orang yang paling paham AI dan lapar di organisasi Anda bereksperimen dengan AI apa pun yang mereka inginkan untuk bekerja (sesuai alasan), dan pelajari dari mereka pelajaran mana yang harus dibawa kembali ke tim yang lebih luas.

Apa pun yang ingin Anda lakukan, cobalah menggunakan AI terlebih dahulu dan lihat sejauh mana AI dapat membantu. Ada satu catatan penting: gunakan model garis depan AI yang paling mutakhir dan paling canggih yang dapat Anda akses, meskipun Anda harus membayar 20 USD per bulan untuk berlangganan Claude Pro atau ChatGPT Plus. Berdasarkan pengalaman saya, versi gratis ChatGPT, Claude, bahkan Google Gemini memiliki banyak keterbatasan dan kinerjanya kurang mengesankan jika dibandingkan dengan versi berbayar tersebut.

Maka ingatlah bahwa pekerjaan itu masih milik Anda. Periksa setiap klaim terhadap sumbernya, tulis ulang apa pun yang perlu ditulis ulang dan bertanggung jawab penuh atas semua yang keluar di bawah nama Anda.

Firecrawl. Ketika Anda memberikan URL mentah kepada chatbot AI dan asisten AI, aksesnya sering kali diblokir atau informasi yang diperoleh tidak lengkap. Sebagai gantinya, tempelkan URL halaman yang tersedia untuk publik ke alat "Scrape" milik Firecrawl, unduh hasilnya sebagai file Markdown (format yang secara alami dipahami oleh LLM), lalu unggah file tersebut ke chatbot bersama halaman lain sebanyak yang Anda perlukan. Dengan cara ini, AI dapat memahami dengan lebih jelas konten yang sedang Anda lihat dan sumber informasi yang Anda gunakan.

Jika Anda membutuhkan AI untuk memahami cara kerja interaktivitas dan elemen visual sebuah situs, cobalah memasang Playwright, perangkat otomatisasi browser sumber terbuka dari Microsoft, untuk digunakan dengan Claude Code atau agen AI berbasis terminal lainnya. Bagi saya, alat gratis ini sangat membantu ketika saya perlu membuat asisten AI memahami tampilan suatu halaman, termasuk elemen interaktif yang ingin saya sertakan dalam analisis dan output.

Sejujurnya, semuanya sekaligus. Dalam seminggu biasa, saya menerbitkan antara lima dan 12 cerita yang dilaporkan dan riset secara mendalam di *VentureBeat*, yang didukung oleh peliputan dan riset menyeluruh, banyak di antaranya dilengkapi analisis komparatif. Pada saat yang sama, saya juga mengelola dua publikasi independen.

One Big Story adalah produk berita harian yang berjalan secara otomatis. Layanan ini memindai ribuan media berita, memilih satu berita yang paling penting bagi seluruh penduduk Bumi, lalu mengolahnya menjadi berbagai format, seperti video, audio, artikel panjang, sesi tanya jawab melalui chatbot, bahkan soneta.

Prompt Scene adalah buletin gratis saya yang membahas subkultur seni AI. Setiap edisi menampilkan seorang kreator AI yang sedang berkembang dan berbagi cerita dengan kata-katanya sendiri tentang siapa dan apa yang menginspirasinya, alat yang digunakannya, serta alasan di balik karya-karyanya. Semua ini saya lakukan sambil menjalankan peran utama sebagai orang tua yang bekerja dari rumah, mengurus rumah tangga, dua anjing kami, dan berbagai kegiatan putri-putri saya.

Beberapa tahun lalu, kombinasi pekerjaan seperti ini membutuhkan sebuah tim, anggaran yang memadai, atau pengorbanan waktu tidur yang jauh lebih besar. AI tidak mengerjakan semuanya untuk saya. Penentuan arah, peliputan, pertimbangan profesional, dan penyuntingan akhir tetap menjadi tanggung jawab saya. Namun, AI menangani sebagian besar pekerjaan riset, pengumpulan informasi, penyortiran, penyusunan draf, pengorganisasian, dan pengembangan materi - jauh lebih banyak daripada yang secara realistis dapat dikerjakan satu orang dalam rentang waktu yang sama tanpa bantuan AI.

Bangun, terapkan, dan kelola asisten dan agen AI yang kuat yang mengotomatiskan alur kerja dan proses dengan AI generatif.

Bangun masa depan bisnis Anda dengan solusi AI yang dapat Anda percaya.

Layanan IBM Consulting AI membantu merancang ulang cara kerja bisnis dengan AI untuk transformasi.
