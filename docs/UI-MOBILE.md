# Spesifikasi UI mobile-first — finance

Untuk **yuki**. Ini acuan desain; kalau ada yang bertentangan dengan kenyamanan pakai di HP,
kenyamanan di HP yang menang.

## Prinsip

**Dirancang dari layar HP, bukan desktop yang dikecilkan.** Deny memakai ini terutama dari
handphone, kemungkinan sambil berdiri di kasir atau di jalan. Asumsinya:

- **Satu tangan.** Aksi utama harus terjangkau ibu jari — separuh bawah layar, bukan pojok atas.
- **Sekali lihat.** Informasi terpenting terbaca tanpa scroll.
- **Input cepat.** Mencatat transaksi harus selesai dalam beberapa detik. Kalau mencatat
  terasa lambat, Deny akan berhenti mencatat, dan seluruh sistem jadi tidak berguna.

## Token dasar

- Font: sistem (`-apple-system`, `Inter`) — jangan muat webfont, lambat di jaringan seluler.
- Warna: gunakan CSS variable, jangan hardcode hex di komponen.
- Radius dan spacing konsisten; jangan campur dua skala.
- Target sentuh minimum **44×44 px**. Jangan ada tombol kecil di dekat tepi layar.
- Aman terhadap notch: pakai `env(safe-area-inset-*)` di header dan bottom bar.

## Layar

### 1. Beranda / panel analisa
Urutan dari atas: **total kekayaan** (angka besar, ini yang pertama dicari) → pemasukan dan
pengeluaran bulan berjalan → selisih → grafik tren 6 bulan → kartu saran hemat → daftar
transaksi terakhir.

Grafik harus bisa dibaca di lebar 360 px. Kalau label tidak muat, ringkas jadi "Jul", jangan
putar teks atau perkecil sampai tidak terbaca.

**Saran hemat wajib menyebut asumsinya.** "Bisa dihemat Rp 300.000/bulan" tanpa penjelasan
adalah angka yang tidak bisa dipercaya.

### 2. Catat transaksi
Layar paling sering dipakai — investasikan waktu di sini.

- Tiga pilihan arah: **Masuk / Keluar / Pindah** sebagai segmented control besar di atas.
- **Numpad besar muncul langsung** — jangan suruh tap field dulu baru keluar keyboard.
- Akun dan kategori sebagai chip yang bisa di-tap, bukan dropdown (dropdown di HP menyiksa).
- Tanggal default **hari ini**, bisa diubah; jangan paksa Deny memilih tanggal setiap kali.
- Catatan opsional, jangan wajib. Kolom wajib hanya: jumlah, arah, akun.

### 3. Daftar transaksi
Dikelompokkan per hari, header tanggal lengket (sticky) saat scroll. Edit/hapus lewat geser
(swipe) atau tap panjang — jangan taruh tombol hapus kecil yang gampang salah tekan.

### 4. Akun & saldo
Kartu per akun dengan saldo. Total di atas. Tabungan dan investasi boleh dipisah secara visual
dari akun harian, tapi tetap masuk total kekayaan.

### 5. Laporan
Mingguan dan bulanan, dibaca dari file yang dihasilkan monica. Teks, bukan dashboard —
Deny membacanya seperti laporan, bukan mengoperasikannya.

## Yang harus dihindari

- Tabel lebar yang butuh scroll horizontal.
- Hover sebagai satu-satunya cara memunculkan aksi (HP tidak punya hover).
- Modal bertumpuk (modal di atas modal) — di HP cepat bikin bingung.
- Angka penting yang tersembunyi di balik tap.
- Animasi yang memakan waktu. Transisi maksimal ~150 ms.
- Format angka mentah. Selalu `Rp 1.100.000`, bukan `1250000`.

## Auth

Login Supabase. **Sesi harus bertahan** — Deny tidak boleh login ulang tiap kali membuka.
Token disimpan di penyimpanan aman browser; jangan di `localStorage` polos kalau
memungkinkan cookie httpOnly.

## Yang belum diputuskan

- Mode gelap: Deny belum memutuskan. Pakai CSS variable sejak awal supaya nanti tidak
  perlu refactor; jangan implementasi temanya dulu.
- Offline: belum dikerjakan. Kalau nanti Deny sering mencatat tanpa sinyal, ini perlu
  dibahas serius — bukan sekadar "tambah service worker".
