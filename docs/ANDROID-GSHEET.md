# Aplikasi Android + data di Google Sheet

Versi Android finance memakai panel yang sama dengan versi Mac (`web/`), tapi
datanya disimpan di **Google Sheet milik Deny** lewat backend **Google Apps
Script** (`gas/`). Server Python di Mac tidak dibutuhkan oleh aplikasi Android.

```
HP Android ──HTTPS──▶ Web App Apps Script (gas/) ──▶ Google Sheet (satu tab per tabel)
  web/ + android.js/css                 └─▶ kenari.id (catat pintar, narasi analisa)
```

## Yang sama dan yang berubah

Semua fitur panel tetap ada: ringkasan & kekayaan, catat lewat kalimat (AI) dan
isi manual, edit/hapus transaksi, transfer, akun, target tabungan, tren,
analisa bulanan + narasi AI, saran hemat, jadwal hutang + tandai lunas
otomatis, sensor nominal, tema.

| Bagian | Mac (lokal) | Android (Google Sheet) |
|---|---|---|
| Database | `finance.db` (SQLite) | tab `accounts`, `categories`, `transactions`, `analyses`, `savings_goals` |
| Jadwal hutang | `LIST-HUTANG.md` | tab `jadwal_hutang` (isi langsung di Sheet) |
| Status lunas | `HUTANG-LUNAS.json` | tab `hutang_lunas` |
| Jejak hapus | `terhapus.log` | tab `terhapus` |
| Kunci AI | env / `secrets.env` | Script Properties `KENARI_API_KEY` |
| Login | password + cookie, mati saat laptop restart | password + token di perangkat, 30 hari / sampai Keluar |
| Pasang password | halaman login (pemasang pertama) | **hanya** lewat skrip migrasi + `ADMIN_TOKEN` |
| Backup | `scripts/backup-db.sh` | salinan Sheet tiap Senin 03:00 + riwayat versi Sheets |
| Tampilan | navbar atas, kaca | Material 3: bar bawah, FAB Catat, tombol Back |

Kenapa pemasangan password tidak lewat halaman login: di Mac server hanya
mendengar `127.0.0.1`. Web App Apps Script terbuka di internet, jadi "pemasang
pertama menang" berarti siapa pun yang menemukan URL-nya bisa mengunci Deny
keluar. Login yang salah 10x dalam 15 menit juga dikunci sementara.

Angka dihitung dengan rumus yang sama persis dengan `src/db.py`. Itu
dibuktikan oleh uji pembanding (lihat §Uji): 143 permintaan ke server Python
asli dan ke backend Apps Script harus menghasilkan balasan yang identik.

## Pasang backend (sekali)

1. **Buat Sheet + skrip.** Paling mudah lewat [clasp](https://github.com/google/clasp):
   ```bash
   npx @google/clasp login
   npx @google/clasp create --type sheets --title "Finance" --rootDir gas
   npx @google/clasp push
   ```
   Tanpa clasp: buat Google Sheet baru → Extensions → Apps Script → buat satu
   berkas per `gas/*.js` (isi disalin apa adanya) dan ganti `appsscript.json`
   (Project Settings → "Show appsscript.json").
2. **Kunci AI.** Project Settings → Script Properties → `KENARI_API_KEY`.
   Opsional: `KENARI_BASE`, `MODEL`, `MODEL_CADANGAN`.
3. **Siapkan.** Di editor, pilih fungsi `siapkan` → Run → izinkan aksesnya.
   Log eksekusi mencetak `ADMIN_TOKEN` — simpan, dipakai langkah 5.
4. **Deploy.** Deploy → New deployment → Web app.
   *Execute as:* **Me**. *Who has access:* **Anyone**. Salin URL `…/exec`.
   ("Anyone" wajib: aplikasi tidak login ke Google. Yang menjaga data adalah
   password aplikasi; URL-nya juga panjang dan tidak bisa ditebak.)
5. **Pindahkan data dari Mac** (membaca `finance.db` dengan `mode=ro`, tidak
   mengubah apa pun di Mac) dan pasang password:
   ```bash
   python3 scripts/migrasi_ke_gsheet.py --url <URL_EXEC> --token <ADMIN_TOKEN>
   ```
   Ganti password kapan saja: tambahkan `--password`. Skrip menolak impor
   kalau tab `transactions` sudah berisi (supaya transaksi dari HP tidak
   tertimpa); `--timpa` hanya kalau memang itu yang diinginkan.

Setiap kali `gas/` berubah: `npx @google/clasp push`, lalu Deploy → Manage
deployments → edit → Version: *New version* (URL tetap sama).

## Build APK

### Tanpa memasang apa pun: GitHub Actions

Workflow `.github/workflows/android-apk.yml` membangun APK di cloud (runner
GitHub sudah punya Android SDK, NDK, dan Rust). Buka tab **Actions → APK
Android → Run workflow**, tunggu ±15–25 menit, lalu unduh
`finance-android-apk` dari bagian **Artifacts** di halaman run-nya. Workflow
juga jalan otomatis saat ada push yang mengubah `web/`, `mobile/`, atau skrip
build. Hasilnya APK debug arm64 — bisa langsung dipasang di HP.

### Di Mac

Butuh ruang disk ±7–9 GB (arm64 saja, tanpa emulator). Rinciannya: Android
Studio ±2,5–3 GB, SDK dasar ±1–1,5 GB, NDK ±2,5–3,5 GB, Rust + target ±1,5 GB,
cache Gradle + hasil kompilasi ±1–3 GB. Lewati emulator di wizard Android
Studio (uji di HP sungguhan) untuk menghemat 2–4 GB lagi.

Prasyarat di Mac:

- Android Studio (SDK + **NDK** dari SDK Manager → SDK Tools)
- `rustup` (bukan cargo Homebrew) — `https://rustup.rs`
- `pnpm`
- Variabel lingkungan, misalnya di `~/.zshrc`:
  ```bash
  export ANDROID_HOME="$HOME/Library/Android/sdk"
  export NDK_HOME="$ANDROID_HOME/ndk/$(ls "$ANDROID_HOME/ndk" | tail -1)"
  export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
  ```

Lalu:

```bash
bash scripts/build-android.sh
```

Skrip menyalin `web/` ke `mobile/dist/` dengan `config.js` mode Android
(`web/` sendiri tidak diubah), lalu menjalankan `tauri android build` untuk
**arm64 saja** (hampir semua HP sekarang; `--semua-arsitektur` untuk
armv7/x86/x86_64). Setelah APK jadi, `mobile/src-tauri/target` boleh dihapus
untuk mengembalikan ruang disk. APK
debug bisa langsung dipasang (`adb install …apk` atau kirim ke HP). Untuk APK
rilis bertanda tangan: `--rilis` setelah menyiapkan keystore sesuai
[panduan signing Tauri](https://v2.tauri.app/distribute/sign/android/).

Pertama kali membuka aplikasi: isi alamat server (URL `…/exec`) dan password.

## Tampilan Android

`web/android.css` + `web/android.js`, aktif hanya kalau `FIN_UI = 'android'`.
Tidak ada fitur yang ditulis ulang — bingkainya saja yang diganti:

- **Navigation bar bawah**, 5 tujuan: Beranda · Daftar · Analisa · Hutang ·
  Akun (Material membatasi 3–5). **Catat** jadi **FAB** — aksi terpenting —
  dan membuka layar penuh dengan tombol ←.
- **Top app bar** datar: judul layar + sensor nominal; pemilih bulan hanya di
  Beranda dan Daftar. Tema dipindah ke layar Akun.
- **Back**: Catat → layar asal; tab lain → Beranda; Beranda → keluar.
- Permukaan tonal datar (tanpa blur kaca — mahal di GPU HP), palet Material 3
  dari seed indigo yang sama, target sentuh 48dp, inset status bar & gesture
  bar (`env(safe-area-inset-*)`), bar bawah menyingkir saat keyboard terbuka,
  tarik ke bawah untuk menyegarkan, snackbar di atas bar bawah.

Coba tanpa HP dan tanpa Google:

```bash
python3 scripts/migrasi_ke_gsheet.py --data <SALINAN-folder-data> --ekspor /tmp/ekspor.json
node tests/gas/server_dev.js /tmp/ekspor.json 8799
```

Buka `http://localhost:8799` dengan lebar HP, alamat server
`http://localhost:8799/exec`, password `rahasia-uji`. AI dimatikan di server uji.

## Uji

```bash
# 1. salin data (JANGAN folder asli — golden.py menulis transaksi uji)
python3 tests/gas/golden.py <salinan-folder-data> /tmp/golden.json
# 2. putar ulang ke backend Apps Script (memori + tiruan Sheet)
GOLDEN=/tmp/golden.json node --test tests/gas/*.test.js
```

## Batas yang perlu diketahui

- **Satu sumber data.** Setelah migrasi, Google Sheet yang jadi catatan utama.
  Panel di Mac (`src/server.py`) dan `src/chat_gate.py` masih membaca
  `finance.db`; transaksi dari HP tidak muncul di sana dan sebaliknya.
- **Kecepatan.** Tiap permintaan ±1–3 detik (Apps Script membaca Sheet); di
  server Mac hampir instan.
- **Butuh internet.** Belum ada antrean offline: mencatat tanpa sinyal gagal
  dengan pesan "Server tidak menjawab".
- Kolom tambahan yang Deny tambahkan sendiri di kanan tab akan dikosongkan
  saat baris di tab itu dihapus/ditulis ulang. Catatan pribadi taruh di tab lain.
