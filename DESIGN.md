# DESIGN.md — Finance Mac App (Tauri shell)

Status: **DRAF untuk direview.** Belum ada kode ditulis.
Pemilik keputusan: Deny. Orkestrasi: steve.
Dokumen ini dimaksudkan untuk diajukan ke agent lain guna revisi, lalu dikembalikan sebagai spesifikasi
final untuk dibangun.

## 1. Tujuan

Aplikasi macOS yang dibuka dari Dock, satu klik, tanpa terminal.
Isinya tetap aplikasi finance yang sudah ada — **tidak ada logika uang yang ditulis ulang**.

## 2. Non-tujuan (tegas)

- BUKAN port ulang backend ke Rust. Python tetap backend-nya.
- BUKAN UI baru. `web/` yang sekarang dipakai apa adanya.
- BUKAN aplikasi untuk dibagikan ke orang lain. Satu mesin, satu pengguna.
- BUKAN pengganti server manual `:8791`. Keduanya harus bisa jalan bersamaan.

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
| Q4 | Sesi login sekarang disimpan di mana — memori proses, berkas, atau cookie saja? | Menentukan cara D8 diwujudkan (§8) |
| Q5 | `start-server.sh` men-daemonize (PPID 1) atau jalan di foreground? | Sidecar butuh foreground supaya bisa dimatikan |
| Q6 | Path absolut di-hardcode di mana saja? | §10 — inventaris sudah menyebut `scripts/backup-db.sh:10-11` |
| Q7 | Berapa lama cold start Python + SQLite? | Menentukan timeout & apakah splash perlu |

## 7. Perilaku

### Buka app

1. Cek single instance. Kalau sudah ada, fokus ke jendela itu. Selesai.
2. Baca config lokasi repo (§10). Kalau tidak valid, tampilkan pemilih folder.
3. Pilih port ephemeral yang bebas. Kalau terpakai, coba port lain — **jangan bunuh apa pun**.
4. Tampilkan splash `"Make it ready..."`.
5. Nyalakan sidecar. Poll health sampai siap (maks 15 detik, lihat Q2/Q7).
6. Muat WebView, sembunyikan splash.

Kalau langkah 5 gagal: tampilkan pesan yang bisa dibaca, 20 baris terakhir log, dan tombol
"Coba lagi" + "Buka folder log". **JANGAN jendela putih kosong.**

### Tutup app

1. SIGTERM ke PID sidecar yang kita catat.
2. Tunggu maksimal 5 detik.
3. Kalau masih hidup, SIGKILL **ke PID itu saja**.
4. Tutup jendela.

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
2. **Sesi server bertahan di disk** — token sesi disimpan (berkas atau tabel SQLite), bukan hanya
   di memori proses.
3. **Sesi terikat ke boot** — saat sesi dibuat, catat waktu boot mesin:
   `sysctl -n kern.boottime` (mis. `{ sec = 1792711872, usec = 0 }`).
   Saat sesi diperiksa, bandingkan dengan boot time sekarang. **Beda → sesi ditolak.**
   Ini yang membuat sesi mati tepat saat laptop restart, bukan sebelumnya, bukan sesudahnya.

Tanpa langkah 3, sesi bertahan selamanya (juga setelah restart) — melanggar permintaan.
Tanpa langkah 2, sesi mati tiap app ditutup — juga melanggar permintaan.

### 🔴 Yang harus diverifikasi (Q4)

Apakah `src/auth.py` sekarang menyimpan sesi di memori, di berkas, atau hanya cookie?
- **Kalau di memori** → langkah 2 butuh perubahan backend. Itu perubahan kecil tapi **menyentuh kode
  autentikasi** — harus dikerjakan dan diuji terpisah, sebelum app dibangun.
- **Kalau sudah persisten** → cukup tambahkan pemeriksaan boot time.

Jangan menebak. Baca `src/auth.py` dan laporkan.

## 9. Splash screen (D9)

Teks: **`Make it ready...`** — persis, dengan tiga titik.

- Tampil segera saat app dibuka, sebelum WebView siap.
- Latar netral, teks tengah, tanpa logo animasi.
- Hilang saat langkah 5 (§7) selesai.
- **Kalau cold start ternyata <1 detik** (Q7), splash tetap dipakai tapi dengan durasi minimum ~400 ms
  supaya tidak berkedip. Splash yang muncul-muncul-hilang dalam 80 ms terlihat seperti bug.

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
"Pilih folder lagi". **Jangan crash, jangan jendela putih.**

Ditolak: membundel `src/` ke dalam `.app`. Setiap perubahan kode jadi butuh rebuild — lambat, dan
bertentangan dengan D4 (UI dari disk).

## 11. Keamanan

- Bind `127.0.0.1` saja (D7).
- Login tetap berlaku — WebView menampilkan `/login` seperti di browser.
- Nol kredensial disimpan di kode Rust. Nol token, nol password.
- `.app` tidak membaca `finance-pribadi/` maupun `finance.db`.
- Config hanya menyimpan **path folder**, bukan rahasia.

## 12. Distribusi

- Build: `cargo tauri build` → `Finance.app`.
- Sign: ad-hoc (`codesign --sign -`). Cukup untuk mesin sendiri.
- Gatekeeper: pertama kali mungkin perlu klik-kanan → Open. Dokumentasikan di README app.
- Update: tidak ada auto-update. Rebuild manual kalau perlu.

## 13. Risiko

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Folder repo dipindah | App tidak bisa start | §10 config + pemilih folder |
| Python hilang / versi berubah | Sidecar gagal start | Cek `python3 --version` saat launch, error jelas |
| Restrukturisasi repo mengubah path | App menunjuk path lama | **Build SETELAH restrukturisasi selesai** |
| Dua instance berebut DB | Saldo kacau | D5 single instance |
| WebView beda perilaku dari Chrome | UI rusak halus | Uji di WebView Tauri, bukan hanya browser |
| Sesi tidak bertahan karena backend in-memory | Login tiap buka app | §8 langkah 2 — verifikasi Q4 lebih dulu |
| `kill` salah sasaran | Membunuh server lain | §4 aturan 4 — hanya PID yang dicatat |

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

## 16. Urutan kerja

1. **Selesaikan restrukturisasi repo finance** (kartu `t_afd4798e` sudah selesai inventarisnya;
   eksekusi menyusul). Build app sebelum ini = membangun di atas path yang akan berubah.
2. **Jawab Q1–Q7 dengan bukti.** Khususnya Q4 (sesi di memori atau persisten) — itu menentukan apakah
   ada pekerjaan backend tambahan.
3. Kalau Q4 menunjukkan sesi in-memory: kerjakan persistensi sesi + boot binding **sebagai kartu
   terpisah**, uji di browser biasa dulu.
4. Scaffold Tauri + sidecar. Uji lifecycle tanpa UI: nyala, mati, crash, port terpakai.
5. Pasang WebView + login + splash.
6. Uji acceptance satu per satu.
7. `cargo tauri build` + ad-hoc sign.
