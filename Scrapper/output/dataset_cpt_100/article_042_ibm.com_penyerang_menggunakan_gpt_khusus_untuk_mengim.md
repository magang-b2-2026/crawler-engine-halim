# Penyerang menggunakan GPT khusus untuk mengimplementasikan serangan ClickFix dalam kampanye RAT baru | IBM®

> **Sumber:** [IBM](https://www.ibm.com/id-id/think/news/custom-gpt-clickfix-attacks)
> **Tanggal Publikasi:** Mon, 12 Oct 2026 07:00:00 GMT
> **Jalur Ekstraksi:** `TIER1_FAST_PATH` | **Jumlah Kata:** 793 kata

Insiden itu mengekspos kesenjangan yang dapat dieksploitasi dalam perilaku manusia, kata pakar, menunjukkan bahwa kepercayaan bisa sama rentannya dengan Teknologi.

Aktor ancaman menyalahgunakan GPT khusus untuk mengirimkan malware trojan akses jarak jauh (RAT) melalui serangan ClickFix, menyoroti bagaimana platform AI tepercaya menjadi kendaraan baru untuk teknik rekayasa sosial yang mapan.

Serangan siber yang paling efektif tidak selalu yang paling canggih. Seringkali, kesuksesan datang dari harapan bahwa pengguna akan mengambil tindakan yang sama yang mereka lakukan setiap hari.

Para peneliti di perusahaan keamanan siber Huntress baru-baru ini mengidentifikasi aktor ancaman yang menyalahgunakan GPT khusus untuk mengirimkan malware melalui serangan gaya Clickfix. Pertama kali diamati lebih dari dua tahun yang lalu, ClickFix adalah teknik rekayasa sosial yang menipu pengguna untuk menyalin dan menjalankan perintah jahat sendiri, sering disamarkan sebagai CAPTCHA atau langkah verifikasi rutin. Sejak itu telah berkembang menjadi metode pengiriman malware yang banyak digunakan.

Kampanye terbaru menunjukkan penyerang sekarang mengadaptasi taktik yang sudah mapan ke lingkungan digital baru. Lebih penting lagi, mereka menggunakan kepercayaan yang semakin meningkat yang diberikan pengguna pada alat yang didukung AI sebagai mekanisme untuk pengiriman malware.

Sementara penggunaan GPT khusus mungkin tampak baru, rantai serangan yang mendasarinya sama sekali tidak. "Ada kampanye ClickFix yang telah dipublikasikan setidaknya selama dua tahun sekarang," kata Michelle Alvarez, Manajer IBM® X-Force Threat Intelligence, pada episode baru-baru ini dari podcast *Security Intelligence*. Menurut Alvarez, fokus industri keamanan siber pada kecerdasan buatan terkadang dapat menutupi evolusi lanjutan dari ancaman yang sudah mapan. "Saya pikir mungkin semua pembicaraan tentang AI dan kerentanan AI garis depan ini agak menutupi ancaman penting ini yang tampaknya terus Lanjutkan berkembang," katanya.

Kampanye ini mencerminkan tren yang lebih luas dalam keamanan siber: penyerang semakin menggunakan kembali teknologi dan platform tepercaya untuk meningkatkan efektivitas teknik yang ada daripada mengembangkan yang sama sekali baru.

Menurut Huntress, penyerang menciptakan pengalaman khusus berbahaya yang pada akhirnya mengarahkan pengguna ke alur kerja yang mampu menerapkan malware akses jarak jauh. Selain itu, laporan dari *BleepingComputer* mencatat bahwa kampanye tersebut sebagian bergantung pada kredibilitas yang terkait dengan ekosistem ChatGPT, menciptakan lingkungan di mana pengguna mungkin lebih cenderung mempercayai instruksi yang mereka terima.

Bergabunglah dengan para pemimpin keamanan yang mengandalkan Buletin Think untuk berita yang dikurasi tentang AI, keamanan siber, data, dan otomatisasi. Pelajari dengan cepat dari tutorial pakar dan penjelas - dikirimkan langsung ke kotak masuk Anda. Lihat Pernyataan Privasi IBM®.

Kepercayaan itu penting karena serangan ClickFix ini hampir seluruhnya bergantung pada interaksi pengguna.

"Rantaian pembunuhan umum masih merupakan langkah yang sama, tetapi sangat kuat," kata Norman Dorsch, Manajer Produk IBM® X-Force. "Pengguna adalah orang yang benar-benar menginstal payload selama serangan ClickFix itu."

Tidak seperti mengeksploitasi yang menargetkan kerentanan perangkat lunak, ClickFix menyerang pengambilan keputusan. Korban biasanya disajikan dengan prompt yang menyerupai CAPTCHA, pemeriksaan verifikasi browser, atau instruksi pemecahan masalah. Peneliti Microsoft telah mengamati aktor ancaman yang menggunakan teknik ini untuk meyakinkan pengguna untuk menjalankan perintah yang pada akhirnya mengirimkan malware, sementara peneliti Proofpoint telah mendokumentasikan adopsi ClickFix yang berkembang di beberapa kampanye ancaman.

Pendekatan ini tetap menarik bagi penyerang karena menggeser semua "angkat berat" kampanye ke korban. Dengan membujuk pengguna untuk menjalankan perintah sendiri, penyerang dapat melewati banyak kontrol keamanan yang dirancang untuk mencegah instalasi perangkat lunak yang tidak sah.

Seperti yang dijelaskan Dorsch, penyerang sering menyajikan interaksi sebagai langkah verifikasi rutin.

"Buktikan bahwa Anda manusia, tempel perintah ini ke terminal Anda dan kemudian mengeksekusi payload," katanya. "Ini sebenarnya menerapkan muatan (payload) ke sistem pengguna, dan Anda mendapatkan C2 \[perintah dan kendali\]."

Penggunaan GPT khusus juga menimbulkan pertanyaan tentang bagaimana pasar AI dan ekosistem agen akan diatur saat mereka terus berkembang. Organisasi telah menghadapi tantangan serupa di toko aplikasi, repositori ekstensi browser, dan pasar perangkat lunak. Ini semua adalah tempat di mana konten berbahaya dapat hidup berdampingan bersama alat yang sah.

"Setiap kali sebuah perusahaan memiliki semacam pasar, diharapkan pada titik tertentu akan memiliki tingkat tanggung jawab dalam hal memangkas apa yang terbukti berbahaya," kata Giacomo Casoni, Senior X-Force Incident Response Consultant di IBM®.

Ketika perusahaan terus Lanjutkan mengadopsi asisten AI dan sistem agen, kepercayaan akan semakin menjadi Boundary keamanan, pakar sepakat. Pengguna tidak boleh mengevaluasi instruksi dari antarmuka yang didukung AI dengan skeptisisme yang sama yang akan mereka terapkan pada lampiran email atau situs web yang tidak dikenal. Coba pikirkan, seberapa sering Anda langsung memercayai notifikasi dari aplikasi pesan atau aplikasi kantor yang biasa Anda gunakan tanpa mengecek kebenarannya terlebih dahulu. Aktor ancaman memahami dinamika ini dan mulai mengintegrasikannya ke dalam playbook yang sudah ada.

Temuan Huntress menunjukkan bahwa organisasi harus memikirkan keamanan AI secara lebih luas daripada hanya kerentanan model. Melindungi pengguna dari pengalaman AI berbahaya mungkin menjadi sama pentingnya dengan mengamankan model yang mendasarinya.

Kesimpulan bagi para pembela adalah bahwa penyerang tidak perlu mengkompromikan sistem AI untuk mendapatkan manfaat darinya. Mereka hanya perlu meyakinkan pengguna bahwa instruksi yang berasal dari sistem itu selalu dapat dipercaya.
