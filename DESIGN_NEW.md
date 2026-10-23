# DESIGN.md — Finance Mac App (Tauri shell)

Status: **DRAF rev.2 untuk direview.** Belum ada kode ditulis.
Pemilik keputusan: Deny. Orkestrasi: steve.
Dokumen ini dimaksudkan untuk diajukan ke agent lain guna revisi, lalu dikembalikan sebagai spesifikasi
final untuk dibangun.

> **Tentang revisi ini (rev.2).** Fungsi dasar tidak berubah: sidecar Python, Rust tidak menyentuh DB,
> aturan PID di §4, keputusan D1–D10, dan urutan kerja di §16 **semuanya tetap**. Yang ditambahkan:
> detail pengalaman pemakaian (UX), anggaran performa, dua celah kebenaran pada mekanisme sesi (§8), dan
> beberapa pertanyaan verifikasi baru (Q8–Q11). Penomoran lama dipertahankan supaya referensi silang
> tidak patah; bagian baru memakai akhiran huruf (§9A, §9B, §9C, §10A). Setiap tambahan diberi tag:
> **[UX]** pengalaman pemakaian · **[PERF]** performa · **[SEC]** keamanan · **[RISIKO]** celah yang
> ditemukan. Butir yang butuh keputusan Deny dikumpulkan di §17.

## 1. Tujuan

Aplikasi macOS yang dibuka dari Dock, satu klik, tanpa terminal.
Isinya tetap aplikasi finance yang sudah ada — **tidak ada logika uang yang ditulis ulang**.

## 2. Non-tujuan (tegas)

- BUKAN port ulang backend ke Rust. Python tetap backend-nya.
- BUKAN UI baru. `web/` yang sekarang dipakai apa adanya.
- BUKAN aplikasi untuk dibagikan ke orang lain. Satu mesin, satu pengguna.
- BUKAN pengganti server manual `:8791`. Keduanya harus bisa jalan bersamaan.

"UI" di sini berarti `web/`. Layar milik shell (splash, layar error, pemilih folder, menu) memang ada
dan didesain di §9, §9A, §9B — itu bukan UI baru untuk aplikasi finance, hanya penanganan keadaan
yang tidak dimiliki `web/`.

## 3. Bentuk

Tauri v2, mode **sidecar**:

- Rust menyalakan proses Python saat app dibuka.
- Rust mematikan proses itu saat app ditutup.
- WebView menunjuk ke server yang baru dinyalakan itu.

Ditolak: mode "titik ke `:8791`". Itu hanya membungkus tab browser dan tetap butuh server yang sudah
jalan — tidak menyelesaikan masalah yang mendasari.

## 4. Arsitektur proses

```
Finance.app (Rust)
  ├─ spawn → python3 src/server.py --port <P>   (sidecar, child process)
  └─ WebView → http://127.0.0.1:<P>/
```

Aturan keras:

1. Rust mencatat PID yang **ia nyalakan sendiri**. Hanya PID itu yang boleh ia matikan.
2. Rust **TIDAK PERNAH** menyentuh proses Python yang bukan ia nyalakan.
3. Rust **TIDAK PERNAH** membuka `finance.db` langsung. Semua baca/tulis lewat HTTP API.
   Alasan: satu sumber kebenaran untuk matematika uang. Dua implementasi saldo = dua angka berbeda,
   dan tidak ada cara menentukan mana yang benar.
4. Rust **TIDAK PERNAH** menjalankan `kill`, `pkill`, `killall` berdasarkan nama proses atau port.
   Hanya PID yang dicatat di langkah 1.

**[RISIKO] Catatan PID (melengkapi aturan 1).** Sidecar harus dinyalakan **langsung** sebagai
`python3 src/server.py` seperti di diagram, supaya PID yang dicatat adalah PID Python itu sendiri.
Kalau yang dinyalakan adalah `scripts/start-server.sh` yang lalu memanggil Python sebagai anak, PID yang
dicatat adalah PID shell: SIGTERM ke shell tidak otomatis sampai ke Python dan Python bisa **yatim**
(tetap hidup setelah app ditutup). Jika skrip harus dipakai, baris terakhirnya harus `exec python3 …`.
Ini langsung terkait Q1 dan Q5.

## 5. Keputusan yang sudah dikunci

| # | Keputusan | Alasan |
|---|---|---|
| D1 | Sidecar, bukan titik-ke-port | Tanpa sidecar, app kosong kalau server belum jalan |
| D2 | Port ephemeral, bukan `8791` | App punya instance sendiri; `8791` bisa dipakai server manual |
| D3 | Nol akses DB dari Rust | Satu sumber kebenaran untuk matematika uang |
| D4 | `web/` tetap disajikan Python | Ubah UI tidak perlu rebuild `.app`, cukup reload |
| D5 | Single instance | Klik kedua fokus ke jendela yang ada, bukan menyalakan server kedua |
| D6 | Ad-hoc sign, bukan Developer ID | Pemakaian sendiri; $99/tahun tidak perlu |
| D7 | Bind loopback `127.0.0.1` | Tidak bisa diakses dari jaringan |
| D8 | Sesi login bertahan sampai laptop restart | Diminta Deny — lihat §8 |
| D9 | Splash `"Make it ready..."` | Diminta Deny — lihat §9 |
| D10 | Lokasi repo dari config + auto-detect | Lihat §10 — `.app` tidak boleh mati karena folder dipindah |

## 6. Pertanyaan yang WAJIB dijawab dengan bukti sebelum build

Ini bukan daftar "nanti dicek". Ini yang menentukan bentuk kode.

| # | Pertanyaan | Kenapa penting |
|---|---|---|
| Q1 | `scripts/start-server.sh` menerima override port? | D2 butuh port dinamis. Kalau tidak bisa, D2 batal |
| Q2 | Ada endpoint health yang bisa dipoll? | Rust perlu tahu kapan server siap, tanpa `sleep` sembarang |
| Q3 | Server sekarang bind `127.0.0.1` atau `0.0.0.0`? | D7 |
| Q4 | Sesi login sekarang disimpan di mana — memori proses, berkas, atau cookie saja? **Dan: cookie sesi punya `Max-Age`/`Expires`, atau cookie sesi murni? Ada flag `Secure`?** | Menentukan cara D8 diwujudkan (§8). Dua tambahan di sini **[RISIKO]**, lihat §8 |
| Q5 | `start-server.sh` men-daemonize (PPID 1) atau jalan di foreground? | Sidecar butuh foreground supaya bisa dimatikan |
| Q6 | Path absolut di-hardcode di mana saja? | §10 — inventaris sudah menyebut `scripts/backup-db.sh:10-11` |
| Q7 | Berapa lama cold start Python + SQLite? | Menentukan timeout & apakah splash perlu |
| **Q8** | **[RISIKO]** Apakah `web/` memakai `localStorage`, `sessionStorage`, atau IndexedDB (tema, filter terakhir, preferensi tampilan)? | Penyimpanan itu terikat ke *origin*, dan origin memuat nomor port. Dengan D2 (port berubah) data itu bisa hilang tiap buka app. Lihat §7 langkah 3 dan D2a |
| **Q9** | **[RISIKO]** Python mana yang dipakai server selama ini: sistem, Homebrew, atau venv di repo? | App yang dibuka dari Dock **tidak mewarisi `PATH` terminal**. `python3` di Homebrew (`/opt/homebrew/bin`) tidak terlihat; `/usr/bin/python3` tanpa Command Line Tools memunculkan dialog pemasangan. Lihat §10A |
| **Q10** | Ada fitur unduh/ekspor (CSV, PDF), cetak, atau tautan keluar di `web/`? | WebView Tauri tidak menangani unduhan dan `window.print()` seperti Chrome. Lihat §9B |
| **Q11** | Layout `web/` masih layak di lebar 800 px? | Menentukan ukuran minimum jendela (§9B) |

## 7. Perilaku

### Buka app

1. Cek single instance. Kalau sudah ada, fokus ke jendela itu. Selesai.
   **[UX]** "Fokus" berarti: tampilkan kalau tersembunyi, keluarkan dari minimize, bawa ke depan.
   Kalau instance pertama masih di splash, fokus ke splash itu.
2. Baca config lokasi repo (§10). Kalau tidak valid, tampilkan pemilih folder.
3. Pilih port ephemeral yang bebas. Kalau terpakai, coba port lain — **jangan bunuh apa pun**.
   **[RISIKO]** Port yang "bebas" saat dicek bisa terambil proses lain sebelum Python sempat
   memakainya. Jadi kegagalan bind pada percobaan pertama bukan keadaan luar biasa; itulah gunanya
   tiga percobaan di bagian "Port terpakai". Lihat juga D2a (§17) untuk port yang stabil antar buka.
4. Tampilkan splash `"Make it ready..."`.
   **[PERF]** Jendela + splash tampil **tanpa menunggu langkah 5**. Langkah 5 dimulai paralel,
   bukan sesudah splash muncul (lihat §9C).
5. Nyalakan sidecar. Poll health sampai siap (maks 15 detik, lihat Q2/Q7).
   **[UX]** Kalau proses sidecar **keluar** saat polling, langsung tampilkan error (jangan menunggu
   15 detik habis).
6. Muat WebView, sembunyikan splash.
   **[UX]** "Sembunyikan splash" terjadi saat WebView melaporkan halaman **selesai dimuat**
   (bukan hanya saat health OK), plus durasi minimum di §9. Ini mencegah kilatan layar putih
   di antara splash dan halaman login.

Kalau langkah 5 gagal: tampilkan pesan yang bisa dibaca, 20 baris terakhir log, dan tombol
"Coba lagi" + "Buka folder log". **JANGAN jendela putih kosong.** Isi dan tata letak layar ini ada di §9A.

### Tutup app

1. SIGTERM ke PID sidecar yang kita catat.
2. Tunggu maksimal 5 detik.
3. Kalau masih hidup, SIGKILL **ke PID itu saja**.
4. Tutup jendela.

**[UX]** Urutan visual: jendela disembunyikan **segera** setelah pengguna menutup (terasa instan),
sementara langkah 1–3 berjalan; proses app baru benar-benar keluar setelah PID sidecar terkonfirmasi
mati. Fungsinya sama dengan di atas, hanya yang terlihat pengguna tidak menunggu hingga 5 detik.
Jalur yang sama dipakai untuk ⌘Q, ⌘W, tombol merah jendela, dan sinyal keluar dari sistem
(logout/shutdown). Satu jendela = satu server, jadi **menutup jendela = keluar dari app**.

### Sidecar mati sendiri (crash)

1. Deteksi exit code bukan 0.
2. Tampilkan layar error + 20 baris terakhir log.
3. Tombol "Nyalakan ulang". **Jangan auto-restart berulang** — itu menyembunyikan bug.

### Port terpakai

Pilih port lain. Tiga percobaan gagal → tampilkan error dengan daftar port yang dicoba.
**Nol `lsof -ti:<port> | xargs kill -9`. Nol `pkill`. Nol `killall`.**

## 8. Sesi login — bertahan sampai laptop restart (D8)

Yang diminta Deny: **login sekali, tidak perlu login ulang tiap buka app — tapi wajib login lagi setelah
laptop restart.**

Ini tidak otomatis tercapai. App ditutup = sidecar Python mati = **sesi di memori proses ikut hilang**.
Jadi tanpa perubahan, Anda akan login ulang setiap kali membuka app.

### Mekanisme yang diusulkan

1. **Cookie WebView bertahan** — Tauri menyimpan cookie per app identifier. Ini sudah default, cukup
   dipastikan tidak dihapus saat shutdown.
   **[RISIKO] Belum cukup.** Dua syarat tambahan, keduanya ada di sisi server (jadi ikut Q4):
   - Cookie sesi harus punya **`Max-Age` atau `Expires` eksplisit**. Cookie "sesi murni" (tanpa
     keduanya) dibuang WebView saat app ditutup, sehingga langkah 2–3 tidak pernah sempat bekerja.
     Masa berlaku panjang aman karena batas sebenarnya dipegang langkah 3 (boot), bukan umur cookie.
   - Cookie **tidak boleh** bertanda `Secure`: WebView menolak menyimpannya untuk `http://127.0.0.1`.
   - Cookie tidak mengikat nomor port, jadi port yang berubah (D2) tidak mematikan sesi. Yang
     terikat port adalah `localStorage` dan sejenisnya — lihat Q8.
   - `identifier` aplikasi (§12) harus **dibekukan**: mengubahnya mereset seluruh data WebView.
2. **Sesi server bertahan di disk** — token sesi disimpan (berkas atau tabel SQLite), bukan hanya
   di memori proses.
3. **Sesi terikat ke boot** — saat sesi dibuat, catat identitas boot mesin. Saat sesi diperiksa,
   bandingkan dengan identitas boot sekarang. **Beda → sesi ditolak.**
   Ini yang membuat sesi mati tepat saat laptop restart, bukan sebelumnya, bukan sesudahnya.
   - **Pilihan utama [RISIKO]: `sysctl -n kern.bootsessionuuid`** — UUID unik per boot, tidak
     terpengaruh perubahan jam. **Wajib dibuktikan di mesin Deny** (jalankan dua kali, lalu setelah
     restart, bandingkan; sertakan outputnya di laporan Q4).
   - **Cadangan:** `sysctl -n kern.boottime` (mis. `{ sec = 1792711872, usec = 0 }`), dibandingkan
     dengan toleransi kecil (mis. ±5 detik pada `sec`). Nilai ini diturunkan dari jam, jadi bisa
     bergeser ketika jam sistem dikoreksi; pembanding tanpa toleransi bisa mengeluarkan pengguna
     secara tiba-tiba tanpa restart.

Tanpa langkah 3, sesi bertahan selamanya (juga setelah restart) — melanggar permintaan.
Tanpa langkah 2, sesi mati tiap app ditutup — juga melanggar permintaan.

**[UX] Yang dilihat pengguna.** Saat sesi ditolak karena boot beda, WebView menampilkan `/login` biasa,
tanpa pesan "sesi berakhir" yang mengagetkan. Tidak ada tampilan data keuangan sesaat sebelum
dialihkan: pemeriksaan sesi harus terjadi di server sebelum halaman berisi data dikirim.

### 🔴 Yang harus diverifikasi (Q4)

Apakah `src/auth.py` sekarang menyimpan sesi di memori, di berkas, atau hanya cookie? Dan bagaimana
atribut cookie-nya (lihat Q4 di atas)?
- **Kalau di memori** → langkah 2 butuh perubahan backend. Itu perubahan kecil tapi **menyentuh kode
  autentikasi** — harus dikerjakan dan diuji terpisah, sebelum app dibangun.
- **Kalau sudah persisten** → cukup tambahkan pemeriksaan boot, dan pastikan atribut cookie di atas.

Jangan menebak. Baca `src/auth.py` dan laporkan.

## 9. Splash screen (D9)

Teks: **`Make it ready...`** — persis, dengan tiga titik. Tidak ditambah ikon, tidak diganti, tidak
diterjemahkan.

- Tampil segera saat app dibuka, sebelum WebView siap.
- Latar netral, teks tengah, tanpa logo animasi.
- Hilang saat langkah 6 (§7) selesai.
- **Kalau cold start ternyata <1 detik** (Q7), splash tetap dipakai tapi dengan durasi minimum ~400 ms
  supaya tidak berkedip. Splash yang muncul-muncul-hilang dalam 80 ms terlihat seperti bug.

### 9.1 Rincian tampilan **[UX]**

| Aspek | Ketentuan |
|---|---|
| Sumber | Berkas statis yang **ditanam di dalam `.app`**. Tidak bergantung pada Python, jaringan, atau repo — splash harus tampil bahkan kalau semua itu gagal |
| Warna | Warna sistem CSS (`Canvas` untuk latar, `CanvasText` untuk teks, `color-scheme: light dark`). Otomatis mengikuti mode terang/gelap macOS dan menjamin kontras tanpa memilih hex |
| Huruf | Font sistem (`-apple-system`), 17 px, bobot 500, rata tengah, satu baris. Tidak ada font yang dimuat |
| Gerak | **Tidak ada animasi.** Teks sudah memuat tiga titik; titik tidak dianimasikan. Dengan begitu `prefers-reduced-motion` otomatis terpenuhi |
| Tanpa kilatan | Jendela dibuat **tersembunyi**, lalu ditampilkan setelah splash selesai digambar pertama kali (bukan sebelum). Ini mencegah kilatan putih di mode gelap |
| Aksesibilitas | Elemen teks memakai `role="status"`, sehingga VoiceOver membacakannya |
| Lambat | Jika sampai **6 detik** belum siap, muncul baris kedua yang lebih kecil dan berwarna sekunder: `Server belum menjawab. Menunggu sampai 15 detik.` Baris ini muncul langsung (tanpa transisi) lewat CSS `animation-delay`. Teks utama **tidak berubah** |
| Tidak ada | Tombol, bilah kemajuan palsu, logo, versi, atau teks lain |

Catatan: baris "lambat" menjawab satu pertanyaan pengguna — "ini macet atau memang belum selesai?" —
tanpa mengubah teks D9. Kalau Deny ingin splash benar-benar hanya satu baris, hapus baris ini; tidak
ada bagian lain yang bergantung padanya.

## 9A. Layar error dan pemilih folder **[UX]**

Semua layar di bagian ini adalah halaman lokal yang ditanam di `.app` (sama seperti splash), **bukan**
halaman dari server Python — karena kejadian yang ditangani justru saat server tidak ada.

### Tata letak (satu pola untuk semua error)

```
┌───────────────────────────────────────────┐
│                                           │
│   Judul: apa yang terjadi                 │
│   Penjelasan satu-dua kalimat + cara      │
│   memperbaiki                             │
│                                           │
│   [ Coba lagi ]  [ Buka folder log ]      │
│                                           │
│   Log terakhir (20 baris)       [Salin]   │
│   ┌─────────────────────────────────────┐ │
│   │ …teks log, monospace, bisa discroll │ │
│   └─────────────────────────────────────┘ │
└───────────────────────────────────────────┘
```

- Rata kiri, kolom teks maksimal ~560 px, di tengah jendela. Judul 20 px semibold, isi 15 px.
- **Aksi utama berada di atas log.** Pengguna yang hanya ingin mencoba lagi tidak perlu menggulir.
- Log tetap **selalu tampil** (syarat asli: "20 baris terakhir log"). Monospace 12 px, teks bisa
  diseleksi, area bisa difokus dengan keyboard dan punya label (`aria-label="Log server"`).
- Warna sistem seperti splash; tombol utama memakai warna aksen sistem (`AccentColor`).
- Keyboard: fokus awal di tombol utama, Enter menjalankannya, Tab melewati tombol lalu log.
  Wadah pesan memakai `role="alert"` supaya VoiceOver membacakannya saat layar muncul.
- Tidak ada ikon peringatan sebagai satu-satunya penanda; maknanya sudah ada di teks judul.

### Teks per kejadian

Aturan penulisan: kalimat biasa (sentence case), kata kerja aktif, sebut penyebab yang spesifik dan apa
yang bisa dilakukan; tidak meminta maaf, tidak samar. Nama tombol sama dengan aksinya, dan konsisten
di seluruh alur.

| Kejadian | Judul | Penjelasan | Tombol |
|---|---|---|---|
| Sidecar gagal siap | Server tidak siap | Server dinyalakan tapi tidak menjawab dalam 15 detik. Lihat log di bawah. | **Coba lagi** · Buka folder log |
| Sidecar keluar saat start | Server berhenti saat dinyalakan | Proses keluar dengan kode {n}. Lihat log di bawah. | **Coba lagi** · Buka folder log |
| Sidecar crash saat dipakai | Server berhenti | Proses keluar dengan kode {n}. Nyalakan ulang untuk melanjutkan; app tidak menyalakan ulang sendiri. | **Nyalakan ulang** · Buka folder log |
| Port habis | Port tidak tersedia | Port yang dicoba: {a}, {b}, {c}. Tutup program yang memakainya, lalu coba lagi. | **Coba lagi** · Buka folder log |
| Python tidak ketemu | Python tidak ditemukan | Finance butuh Python 3 untuk menyalakan server. Lokasi yang dicari: {daftar}. Atur `python_path` di config (§10A). | **Coba lagi** · Buka config |
| Repo tidak valid | Folder finance tidak valid | Berkas yang hilang: {daftar}. Pilih folder repo finance. | **Pilih folder lagi** |
| WebView gagal memuat | Halaman tidak bisa dimuat | Server menjawab, tapi halaman gagal dimuat. Lihat log di bawah. | **Coba lagi** · Buka folder log |

`{n}`, `{a}`, `{daftar}` diisi nilai sebenarnya, bukan placeholder. Dua nama tombol pemulihan
("Coba lagi" untuk gagal saat start, "Nyalakan ulang" untuk crash saat sudah berjalan) dibedakan
sengaja dan tidak dicampur di dalam satu alur.

### Log: di mana disimpan dan bagaimana ditampilkan **[PERF]**

- Stdout dan stderr sidecar ditangkap ke dua tempat: (a) buffer di memori untuk 20 baris terakhir
  yang ditampilkan di layar error, dan (b) berkas `~/Library/Logs/Finance/sidecar.log` (lokasi log
  standar macOS; "Buka folder log" membuka folder ini di Finder).
- Berkas dirotasi: maksimal 1 MB per berkas, simpan 3 berkas. Tidak tumbuh tanpa batas.
- Python dinyalakan dengan `PYTHONUNBUFFERED=1` supaya baris log yang muncul sebelum crash benar-benar
  sampai, bukan tertahan di buffer.
- Log tidak berisi isi transaksi. Kalau server sekarang mencetak data keuangan ke stdout, itu temuan yang
  dilaporkan, bukan dicetak ulang di layar error.

### Pemilih folder (§10)

Memakai dialog folder bawaan macOS, bukan form buatan sendiri.

- Judul dialog: `Pilih folder finance`. Pesan di dalam dialog menyebut berkas yang dicari
  (`src/server.py`, `web/index.html`, `src/schema.sql`).
- Setelah memilih, validasi berjalan segera. Kalau gagal, layar error "Folder finance tidak valid"
  menyebut **berkas mana yang hilang**, bukan "path salah".
- Dialog dibuka di folder yang terakhir dipilih, atau `~/Documents` untuk yang pertama kali.
- Membatalkan dialog kembali ke layar error yang sama (bukan menutup app diam-diam).

## 9B. Jendela, menu, dan navigasi **[UX]**

| Aspek | Ketentuan |
|---|---|
| Judul jendela | `Finance` |
| Bilah judul | Bawaan macOS (tombol traffic-light standar). Tidak overlay |
| Ukuran awal | 1280×800, di tengah layar (pertama kali) |
| Ukuran minimum | 800×600, **setelah Q11 dijawab**. Jangan mengunci minimum yang membuat `web/` terpotong |
| Posisi/ukuran | Mengingat ukuran dan posisi terakhir = opsional, lihat §17 |
| Mode terang/gelap | Splash dan layar error mengikuti sistem. `web/` mengikuti perilakunya sendiri (D4, tidak disentuh) |
| Ikon Dock | Master 1024×1024, mengikuti grid ikon macOS, satu glif sederhana tanpa teks. Warna aksen diambil dari palet `web/` yang sudah ada supaya sebangun |

### Menu bar minimal

Tanpa menu bar, WebView macOS tidak meneruskan ⌘C, ⌘V, ⌘X, ⌘A, ⌘Z — pengguna tidak bisa menempel
kata sandi ke form login. **[RISIKO]** Jadi menu berikut wajib ada. Ini menu aplikasi standar, bukan
"shortcut keyboard global" (§14).

| Menu | Isi |
|---|---|
| Finance | Tentang Finance · Sembunyikan Finance (⌘H) · Keluar (⌘Q) |
| Edit | Urungkan · Ulangi · Potong · Salin · Tempel · Pilih Semua |
| Tampilan | Muat Ulang (⌘R) · Layar Penuh |
| Jendela | Minimalkan (⌘M) · Zoom |

**Muat Ulang (⌘R)** memuat ulang `http://127.0.0.1:<P>/` yang sama — ini yang membuat D4 ("ubah UI
cukup reload") terasa seperti browser. Alat pengembang (inspect) hanya aktif pada build debug.

### Navigasi dan tautan keluar **[SEC]**

- WebView hanya boleh menavigasi ke `http://127.0.0.1:<P>/…` dan halaman lokal milik shell.
- Tautan ke alamat lain (atau `target="_blank"`) dibuka di **browser bawaan**, bukan di dalam jendela
  app. Jendela finance tidak boleh berubah menjadi browser.
- Unduhan/ekspor dan cetak: perilakunya ditentukan setelah Q10 dijawab. Jangan dianggap "pasti
  jalan seperti di Chrome".

## 9C. Anggaran performa **[PERF]**

Tujuan: terasa instan di bagian yang dikendalikan app, dan jujur soal bagian yang ditentukan Python.

| Titik | Target | Cara kerja |
|---|---|---|
| T0 → splash tergambar | ≤ 300 ms | Splash statis di dalam `.app`, tanpa jaringan, tanpa menunggu sidecar |
| T0 → sidecar dinyalakan | segera, **paralel** dengan splash | Spawn tidak menunggu UI. Kerja Rust yang berat dijalankan di thread terpisah supaya jendela tidak membeku |
| Health poll | interval 50 ms (1 detik pertama), lalu 100 ms, lalu 250 ms | Tanpa `sleep` tetap. Tiap permintaan punya batas waktu 400 ms. Total tetap maks 15 detik |
| Health OK → halaman dimuat | ≤ 400 ms overhead app | Navigasi WebView dimulai saat health OK. Splash hilang saat halaman selesai dimuat |
| Sidecar keluar saat start | error **seketika** | Pantau exit proses, jangan menunggu timeout |
| Tutup app | jendela hilang seketika; proses app selesai ≤ ~1 detik lazimnya, ≤ 5 detik batas | SIGTERM → tunggu → SIGKILL ke PID itu saja (§7) |
| Memori | satu WebView, tanpa alat pengembang di rilis | Tidak ada jendela atau proses tambahan |

- Jika Q2 menunjukkan tidak ada endpoint health, "siap" = server menjawab HTTP apa pun yang sah
  (mis. 200 atau 302 dari `/login`) pada permintaan ringan. Jangan menunggu halaman data berat.
- Cold start Python+SQLite (Q7) adalah bagian terbesar waktu tunggu dan **di luar kendali shell**.
  Yang bisa dilakukan shell hanyalah tidak menambah waktu itu dan tidak memperlambat penyajian.
- **Pengukuran sebagai bukti:** shell menulis satu baris log berstempel waktu untuk tiap titik di
  atas (T0, splash tergambar, spawn, health OK, halaman selesai dimuat, sidecar mati). Acceptance (§15)
  memakai log ini untuk menjawab Q7 dan memeriksa anggaran, bukan perasaan.

## 10. Lokasi repo (D10)

`.app` harus tahu di mana `src/` berada, tanpa di-hardcode ke satu path yang bisa berubah.

**Urutan pencarian:**

1. Berkas config: `~/Library/Application Support/Finance/config.json` → field `repo_path`.
2. Kalau tidak ada / tidak valid: coba deteksi `~/Documents/AI/finance`.
3. Kalau tetap tidak ketemu: tampilkan **pemilih folder**, simpan pilihannya ke config.

**Validasi path** — harus lolos semua:
- `src/server.py` ada
- `web/index.html` ada
- `src/schema.sql` ada

Kalau path tersimpan jadi tidak valid (folder dipindah/dihapus): tampilkan pesan jelas + tombol
"Pilih folder lagi". **Jangan crash, jangan jendela putih.** Tampilannya ada di §9A.

Ditolak: membundel `src/` ke dalam `.app`. Setiap perubahan kode jadi butuh rebuild — lambat, dan
bertentangan dengan D4 (UI dari disk).

## 10A. Lokasi Python **[RISIKO]**

Aplikasi yang dibuka dari Dock berjalan dengan `PATH` yang minimal, tidak sama dengan terminal. Tanpa
penanganan, "tidak perlu terminal" bisa berakhir dengan "Python tidak ditemukan" padahal Python ada.

**Urutan pencarian interpreter Python** (sama polanya dengan §10, tanpa mengubah fungsi sidecar):

1. Env `FINANCE_PYTHON` (kalau diset), atau field `python_path` di berkas config yang sama dengan
   `repo_path` (X6) — override manual, didahulukan apa pun isinya.
2. `/opt/homebrew/bin/python3.11` — **UTAMAKAN**. Symlink stabil Homebrew. **Jangan** memakai
   `/opt/homebrew/Cellar/python@3.11/<versi>/bin/python3.11`: path itu berubah tiap `brew upgrade`.
   `/opt/homebrew/bin/python3` **tidak ada** di mesin ini (Homebrew hanya memasang nama berversi),
   jadi jangan dijadikan patokan.
3. Venv di repo, jika ada (mis. `<repo>/.venv/bin/python3`; venv selalu menyediakan nama `python3`)
   — **hanya setelah Q9 memastikan itu yang dipakai server**. Versinya tetap diverifikasi ≥ 3.9.
4. Probe `python3` di `PATH`, **tapi wajib diverifikasi** `--version` ≥ **3.9** sebelum dipakai —
   3.9 adalah **lantai sintaks** kode ini (terbukti: `py_compile` 30/30 dan suite hijau di 3.9.6),
   bukan target. Di mesin ini `PATH` bawaan Dock berujung ke `/usr/bin/python3` = **3.9.6**.
5. Kalau yang terpilih versinya < **3.11**: **JALANKAN**, tapi cetak **peringatan ke `stderr`**
   (satu baris, menyebut versi, path interpreter, dan cara memperbaikinya). Alasannya: Python
   bawaan sistem Apple deprecated sejak macOS 12.3 dan akan dihapus. Server tetap melayani normal;
   peringatan yang sama juga terekspos di `/api/auth/status` sebagai `python_di_bawah_rekomendasi`.
6. Kalau < **3.9**: **TOLAK**. Pesan wajib menyebut **setiap path yang dicoba**, **versi yang
   ditemukan** di path itu, dan **versi minimum** yang dibutuhkan (≥ 3.9).
7. Tidak ada kandidat sama sekali → layar error "Python tidak ditemukan" (§9A), dengan daftar
   lokasi yang sudah dicari.

Interpreter yang dipakai diverifikasi dengan `--version` saat launch (sesuai §13) dan dicatat di log.
Angka 3.9 dan 3.11 sengaja berbeda peran: **3.9 = boleh jalan**, **3.11 = seharusnya dipakai**.
Menolak 3.9.6 tidak lagi benar — kode terbukti jalan di sana (keputusan Deny, 23 Okt 2026).

## 11. Keamanan

- Bind `127.0.0.1` saja (D7).
- Login tetap berlaku — WebView menampilkan `/login` seperti di browser.
- Nol kredensial disimpan di kode Rust. Nol token, nol password.
- `.app` tidak membaca `finance-pribadi/` maupun `finance.db`.
- Config hanya menyimpan **path folder**, bukan rahasia. (Berlaku juga untuk `python_path`.)
- **[SEC] Halaman dari `127.0.0.1` tidak diberi akses ke perintah Tauri apa pun.** Perintah shell
  (coba lagi, pilih folder, buka folder log) hanya boleh dipanggil oleh halaman lokal milik shell
  (splash dan layar error). Halaman `web/` dianggap seperti situs web biasa: bisa menampilkan dan
  memanggil API server, tidak bisa menyuruh app melakukan apa-apa.
- **[SEC]** Halaman lokal shell memakai CSP ketat (tanpa skrip/sumber dari luar).
- **[SEC]** Log sidecar tidak boleh memuat isi transaksi (lihat §9A).

## 12. Distribusi

- Build: `cargo tauri build` → `Finance.app`.
- Sign: ad-hoc (`codesign --sign -`). Cukup untuk mesin sendiri.
- Gatekeeper: pertama kali mungkin perlu klik-kanan → Open. Dokumentasikan di README app.
- Update: tidak ada auto-update. Rebuild manual kalau perlu.
- **[RISIKO]** `identifier` aplikasi (reverse-DNS) ditetapkan **sekali** dan tidak diubah. Mengubahnya
  membuat WebView memakai penyimpanan baru: cookie sesi (§8) dan data `localStorage` (Q8) hilang.

**Toolchain build (Tauri v2).** Dipatok supaya build pertama tidak gagal karena toolchain kebetulan
terlalu tua dengan pesan yang menyesatkan:

- **MSRV Rust: 1.90.** Ini MSRV resmi Tauri v2 — crate `tauri` 2.12.5 (crates.io, 21 Okt 2026)
  mencantumkan `rust_version = 1.90`, dan blog rilis Tauri 2.12 (`v2.tauri.app/blog/tauri-2.12/`)
  menaikkan MSRV ke 1.90 dengan kebijakan `stable - 3`. Cek `rustc --version` ≥ 1.90 sebelum scaffold.
- **Target triple: `aarch64-apple-darwin`** (mesin ini `arm64`, macOS 26.5.1 build 25F80).
  Pasang sekali: `rustup target add aarch64-apple-darwin`.
- **CARGO_HOME/RUSTUP_HOME:** Rust di mesin ini dipasang via rustup dengan CARGO_HOME/RUSTUP_HOME
  **di luar lokasi default** (bukan `~/.cargo`/`~/.rustup`). Perintah `cargo`/`rustup` butuh kedua
  variabel itu diset; tanpa itu toolchain terlihat "tidak ada" padahal terpasang.

## 13. Risiko

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Folder repo dipindah | App tidak bisa start | §10 config + pemilih folder |
| Python hilang / versi berubah | Sidecar gagal start | Cek `python3 --version` saat launch, error jelas. Lihat §10A (PATH Dock tidak sama dengan terminal) |
| Restrukturisasi repo mengubah path | App menunjuk path lama | **Build SETELAH restrukturisasi selesai** |
| Dua instance berebut DB | Saldo kacau | D5 single instance |
| WebView beda perilaku dari Chrome | UI rusak halus | Uji di WebView Tauri, bukan hanya browser. Khusus: unduhan, cetak, tautan keluar (Q10) |
| Sesi tidak bertahan karena backend in-memory | Login tiap buka app | §8 langkah 2 — verifikasi Q4 lebih dulu |
| **Sesi tidak bertahan karena cookie sesi murni** | Login tiap buka app, walau sesi sudah di disk | §8 langkah 1: `Max-Age`/`Expires` eksplisit, tanpa `Secure` |
| **Pembanding boot bergeser karena jam dikoreksi** | Pengguna keluar tiba-tiba tanpa restart | §8 langkah 3: `kern.bootsessionuuid`, cadangan `boottime` dengan toleransi |
| `kill` salah sasaran | Membunuh server lain | §4 aturan 4 — hanya PID yang dicatat |
| **Sidecar yatim (tetap hidup setelah app mati paksa)** | Server berjalan tanpa jendela; port terpakai | Lihat di bawah |
| **`localStorage` hilang tiap buka (port berubah)** | Preferensi tampilan reset | Q8, lalu D2a (§17) |
| **Salin/tempel tidak jalan di form login** | Tidak bisa menempel kata sandi | §9B menu Edit wajib |

**Sidecar yatim.** Menutup app dengan wajar (⌘Q, tombol merah, shutdown) selalu melewati §7 "Tutup app".
Tetapi kalau proses app dimatikan paksa (Force Quit, crash Rust), tidak ada kode yang sempat berjalan, dan
macOS tidak otomatis mematikan anak proses. Aturan §4 melarang app mematikan Python yang bukan miliknya
atau mematikan berdasarkan nama/port, jadi app **tidak** membersihkannya di peluncuran berikutnya.
Port ephemeral membuat yatim itu tidak menghalangi buka app berikutnya (hanya memakai satu proses
lebih). Penjaga yang lebih rapat — sidecar keluar sendiri saat induknya hilang (mis. saat pipa stdin
dari Rust tertutup) — menyentuh kode server, jadi ini **keputusan Deny** di §17, bukan bagian default.

## 14. Di luar lingkup

Auto-update · notifikasi sistem · tray icon · shortcut keyboard global · multi-window ·
sinkronisasi cloud · versi Windows/Linux.

Semua bisa jadi kartu terpisah nanti, kalau perlu.

## 15. Acceptance

App dianggap jadi kalau **semua** terpenuhi:

- [ ] Ikon di Dock, satu klik membuka jendela berisi aplikasi finance
- [ ] Nol terminal dibuka, nol perintah diketik
- [ ] Splash `Make it ready...` tampil, tidak berkedip, hilang saat siap
- [ ] Login berfungsi
- [ ] **Sesi bertahan setelah app ditutup lalu dibuka lagi** (tanpa login ulang)
- [ ] **Sesi ditolak setelah laptop restart** (wajib login lagi)
- [ ] Data terbaca: saldo, transaksi, ringkasan bulanan — sama dengan versi browser
- [ ] Catat transaksi berhasil dari dalam app (bukan hanya tampil)
- [ ] Tutup app → proses Python benar-benar mati (`lsof` kosong untuk PID itu)
- [ ] Buka dua kali → tetap satu jendela, satu server
- [ ] Kill sidecar manual → app menampilkan error + log, bukan jendela putih
- [ ] Folder repo dipindah → app menampilkan pemilih folder, bukan crash
- [ ] `finance.db` nol berubah oleh Rust (mtime sama saat app dibuka/tutup tanpa transaksi)
- [ ] Server manual `:8791` tetap bisa jalan bersamaan dengan app

**Tambahan rev.2** (tidak menggantikan butir di atas):

- [ ] **[UX]** Salin/tempel/pilih semua berfungsi di form login (menu Edit ada)
- [ ] **[UX]** Tidak ada kilatan putih antara splash → login, di mode terang **dan** gelap
- [ ] **[UX]** Dengan sidecar sengaja diperlambat (>6 detik), baris "Server belum menjawab…" muncul; teks utama tetap `Make it ready...`
- [ ] **[UX]** Setiap layar error: fokus awal di tombol utama, Enter menjalankannya, log bisa di-scroll dan diseleksi, VoiceOver membacakan judul
- [ ] **[UX]** Tautan ke alamat luar dibuka di browser bawaan; jendela app tidak pernah berpindah dari `127.0.0.1`
- [ ] **[UX]** ⌘Q, ⌘W, dan tombol merah menghasilkan hasil yang sama: jendela hilang seketika, sidecar mati, tidak ada proses tersisa
- [ ] **[RISIKO]** Cookie sesi punya `Max-Age`/`Expires` dan tidak bertanda `Secure`; sesi bertahan setelah app ditutup-dibuka (diuji, bukan diasumsikan)
- [ ] **[RISIKO]** Output `kern.bootsessionuuid` dari dua boot berbeda dilampirkan sebagai bukti
- [ ] **[RISIKO]** Python ditemukan saat app dibuka **dari Dock** (bukan dari terminal) pada mesin Deny
- [ ] **[PERF]** Log waktu (T0…halaman dimuat) terlampir; splash tergambar ≤ 300 ms; overhead app setelah health OK ≤ 400 ms; angka cold start menjawab Q7
- [ ] **[PERF]** Sidecar dibuat keluar saat start → error muncul seketika, bukan setelah 15 detik
- [ ] **[SEC]** Dari konsol WebView pada halaman `web/`, pemanggilan perintah Tauri apa pun gagal

## 16. Urutan kerja

1. **Selesaikan restrukturisasi repo finance** (kartu `t_afd4798e` sudah selesai inventarisnya;
   eksekusi menyusul). Build app sebelum ini = membangun di atas path yang akan berubah.
2. **Jawab Q1–Q11 dengan bukti.** Khususnya Q4 (sesi di memori atau persisten, **plus** atribut cookie
   dan `kern.bootsessionuuid`) — itu menentukan apakah ada pekerjaan backend tambahan. Q8–Q11 dijawab
   dengan satu kali baca `web/` dan satu kali jalan di mesin Deny.
3. Kalau Q4 menunjukkan sesi in-memory **atau cookie sesi murni**: kerjakan persistensi sesi + boot
   binding + atribut cookie **sebagai kartu terpisah**, uji di browser biasa dulu.
4. Scaffold Tauri + sidecar. Uji lifecycle tanpa UI: nyala, mati, crash, port terpakai.
   **[UX]** Pasang juga pencatat log dan penanda waktu (§9A, §9C) di langkah ini, bukan belakangan —
   kedua hal itu dibutuhkan untuk menguji lifecycle.
5. Pasang WebView + login + splash + layar error + menu (§9, §9A, §9B).
6. Uji acceptance satu per satu.
7. `cargo tauri build` + ad-hoc sign.

## 17. Butir yang butuh keputusan Deny (usulan rev.2)

Semua bersifat opsional dan tidak mengubah fungsi dasar. Default di kolom kanan dipakai jika Deny tidak
memutuskan.

| # | Usulan | Alasan | Default |
|---|---|---|---|
| X1 | **D2a — coba port terakhir dulu.** Simpan port terakhir di config; saat buka, coba port itu lebih dulu, kalau terpakai baru ephemeral | Menjaga *origin* tetap sama sehingga `localStorage` `web/` bertahan (Q8). Jika Q8 menjawab "tidak dipakai", usulan ini tidak perlu | Tidak dipakai kecuali Q8 menunjukkan penyimpanan di sisi browser |
| X2 | Ingat ukuran dan posisi jendela (plugin `window-state`) | Jendela kembali seperti terakhir ditutup. Menambah satu dependensi | Tidak, selalu 1280×800 di tengah |
| X3 | Penjaga sidecar yatim — server keluar sendiri bila induknya hilang | Menutup celah force-quit (§13). Menyentuh kode server | Tidak, risiko dicatat saja |
| X4 | Baris "Server belum menjawab…" di splash (§9.1) | Mencegah kesan macet | Ya |
| X5 | Tombol "Salin log" di layar error | Mempermudah melaporkan masalah | Ya |
| X6 | Field `python_path` di config (§10A) | Menghindari "Python tidak ditemukan" dari Dock | Ya, lewat urutan pencarian §10A |
