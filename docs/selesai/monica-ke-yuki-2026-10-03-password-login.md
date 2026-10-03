# Permintaan ke yuki — dari monica (data & angka)

**Tanggal:** 3 Okt 2026
**Dari:** monica (DATA & ANGKA)
**Ke:** yuki (FRONTEND — panel web `web/`)
**Perihal:** Panel sekarang butuh password — 1 halaman baru + perubahan di `app.js`

Deny minta panelnya dikunci password. Sisi server **sudah jalan dan teruji**.
Yang perlu kamu kerjakan: **satu halaman login**, dan **penanganan 401 di
`app.js`**. Rinciannya di §3 dan §4.

---

## Ringkas

| # | Isi | Prioritas |
|---|---|---|
| 1 | `web/login.html` — halaman login baru | **tinggi** |
| 2 | `app.js` — tangani `401` dengan mengalihkan ke `/login` | **tinggi** |
| 3 | `app.js` — tombol keluar (logout) | sedang |
| 4 | Konfirmasi: semua endpoint lama tetap sama, hanya butuh cookie | — |

---

## 1. Keputusan Deny, dan batasnya

Deny memilih **pengamanan standar** — bukan enkripsi. Ini penting kamu tahu
supaya kamu tidak menulis klaim yang tidak benar di panelnya:

| Dilindungi | **Tidak** dilindungi |
|---|---|
| Orang yang lewat / memakai Mac sebentar tidak bisa melihat angka lewat panel | `data/finance.db` tetap terbaca langsung dengan SQLite |
| | Siapa pun yang bisa buka terminal bisa mereset password |

**Jangan tulis "aman", "terenkripsi", atau "data terlindungi" di halaman login.**
Yang benar: *"Masuk untuk melihat data keuangan."* Kalau kamu menulis klaim
keamanan, Deny akan mengira datanya terlindungi padahal tidak.

---

## 2. Cara kerjanya (supaya kamu paham kenapa 401 bisa muncul)

```
1. Buka panel       -> belum ada cookie -> server alihkan (302) ke /login
2. Isi password     -> POST /api/auth   -> server kirim cookie httpOnly
3. Semua fetch      -> browser ikut mengirim cookie otomatis
4. Server restart   -> token di memori hilang -> SEMUA fetch jadi 401
```

**Poin 4 itu perilaku yang DIMINTA Deny**, bukan bug. Dia bilang: *"kunci kembali
jika di tengah jalan server terputus."* Jadi kalau kamu menyalakan ulang server
saat mengerjakan, panelmu akan tiba-tiba 401 — itu benar.

**Konsekuensi penting untuk `app.js`:** sesi bisa mati **kapan saja**, bahkan
saat Deny sedang memakai panelnya. Setiap `fetch` harus siap menerima 401.

---

## 3. `web/login.html` — halaman baru

Server menyajikannya di **`/login`** (juga `/login.html` dan `/masuk`).
Berkasnya harus ada di `web/login.html` — server membacanya langsung.

### Yang harus ditangani: DUA keadaan berbeda

**Keadaan A — belum ada password (pertama kali).** Kalau `GET /api/auth`
mengembalikan `sudah_ada_password: false`, halaman harus minta **password baru
+ konfirmasi**, bukan "masuk".

```json
GET /api/auth
{ "sudah_ada_password": false, "jumlah_sesi": 0,
  "catatan": "Sesi hilang kalau server dimatikan — itu memang disengaja." }
```

**Keadaan B — sudah ada password.** Hanya satu field: password.

### Kirim ke `POST /api/auth`

```json
{ "password": "rahasia123", "konfirmasi": "rahasia123" }
```

`konfirmasi` **hanya** dikirim di keadaan A. Sukses → server mengirim cookie dan
balasan:

```json
{ "ok": true, "baru_dipasang": true, "masuk": true }
{ "ok": true, "masuk": true }
```

**Setelah sukses, arahkan ke `/`.** Cookie sudah dikirim server; kamu tidak
perlu menyimpan apa pun di JavaScript. **Cookie-nya `httpOnly` — JavaScript
tidak bisa (dan tidak boleh) membacanya.**

### Gagal — tampilkan `message` apa adanya

```json
{ "ok": false, "error": "password_salah",          "message": "Password salah." }
{ "ok": false, "error": "password_terlalu_pendek", "message": "Password minimal 6 karakter." }
{ "ok": false, "error": "konfirmasi_beda",         "message": "Dua password yang dimasukkan berbeda." }
```

Ketiganya datang sebagai **HTTP 401** (bukan 200), jadi pastikan kamu membaca
body-nya walau statusnya error.

### Yang penting di halaman ini

- `autocomplete="current-password"` (keadaan B) dan `autocomplete="new-password"`
  (keadaan A) — supaya password manager bekerja dan browser tidak menawarkan
  menyimpan password lama saat memasang yang baru
- Target sentuh 44 px, sama seperti halaman lain
- `type="password"`, plus **tombol lihat/sembunyikan** — membantu karena ini
  dipakai di HP
- Saat mengirim, matikan tombolnya supaya tidak terkirim dua kali
- Kalau gagal, jangan kosongkan field passwordnya — Deny hanya salah ketik

---

## 4. `app.js` — penanganan 401 (WAJIB)

Semua `fetch` di `app.js` sekarang bisa menerima **401** kapan saja. Kalau tidak
ditangani, panel akan menampilkan error yang membingungkan atau — lebih buruk —
tampilan lama yang angkanya sudah basi.

**Aturan:** 401 → arahkan ke `/login`. Titik. Jangan coba lagi, jangan tampilkan
pesan error, jangan biarkan isi layar lama terlihat.

Saran implementasi: satu pembungkus `fetch` yang sudah kamu punya, tambahkan
pemeriksaan status di situ — bukan di setiap pemanggil. Kalau ada 12 tempat
memanggil `fetch`, menambah 12 pemeriksaan berarti 12 kesempatan lupa.

```js
// di pembungkus fetch-mu, sebelum memproses body:
if (r.status === 401) {
  window.location.href = '/login';
  throw new Error('sesi berakhir');   // hentikan pemrosesan
}
```

**Kenapa penting, bukan sekadar rapi:** server restart saat Deny sedang memakai
panel. Tanpa penanganan ini, dia melihat panel dengan angka lama dan mengira
datanya masih hidup — padahal setiap kali dia menekan simpan, gagal.

---

## 5. Tombol keluar

```json
POST /api/auth/keluar
{ "ok": true, "keluar": true }
```

Server mencabut token dan menghapus cookie. Setelah itu arahkan ke `/login`.

**Letakkan di mana:** bebas kamu tentukan. Saranku di area yang butuh dua tap
(di balik menu atau di layar Akun paling bawah), bukan tombol yang mudah
tersentuh — keluar tidak sengaja saat sedang mencatat transaksi itu menjengkelkan.

**Yang tidak perlu kamu lakukan:** konfirmasi "yakin keluar?". Keluar itu tidak
merusak apa pun; yang berbahaya adalah hapus transaksi, bukan keluar.

---

## 6. Yang TIDAK berubah

**Semua endpoint lama tetap sama persis.** Tidak ada perubahan bentuk data,
tidak ada field baru. Yang berbeda hanya: **sekarang butuh cookie**.

| Endpoint | Status |
|---|---|
| `/api/summary`, `/api/transactions`, `/api/accounts`, `/api/categories` | tidak berubah |
| `/api/trend`, `/api/suggestions`, `/api/spending-by-category` | tidak berubah |
| `/api/parse`, `/api/save` | tidak berubah |
| `/api/transactions/<id>` (PATCH/DELETE) | tidak berubah |
| `/api/analysis`, `/api/savings`, `/api/months` | tidak berubah |

Kalau kamu menguji dengan `curl`, tambahkan `-H 'Cookie: sesi=...'`. Tanpa itu,
semua endpoint akan menjawab 401 — dan itu memang benar.

---

## 7. Yang perlu kamu tahu saat menguji

**Cookie-nya hilang setiap server restart.** Jadi jangan heran kalau:
- Kamu login, lalu restart server untuk memuat kode baru, lalu panel kembali
  ke halaman login. **Itu benar**, bukan bug.
- Kamu sedang menguji dan tiba-tiba semua 401. Cek dulu: servernya baru
  dinyalakan?

**Jebakan yang sama seperti kemarin:** server yang memegang kode lama. Kalau
perilakunya tidak cocok dengan kontrak ini, restart dulu sebelum melaporkan.

**Password untuk menguji:** Deny belum memasang password. Saat pertama kamu
buka `/login`, kamu akan diminta memasangnya. **Jangan pakai password sungguhan
Deny** — pakai apa saja untuk menguji, lalu minta dia memasang sendiri setelah
selesai. Berkas kredensialnya ada di `data/kredensial.json` (hash, bukan teks
polos) dan **jangan kamu sentuh**.

---

## Pertanyaanku

1. Halaman login: mau gaya terang/gelap mengikuti sistem seperti panel, atau
   selalu terang saja? (Halaman login tidak punya akses ke tema panel.)
2. Tombol keluar — di mana menurutmu paling pas?
3. Perlu nagging "sesi berakhir, masuk lagi" di halaman login, atau cukup
   langsung tampilkan formnya? Menurutku cukup formnya — kalau ada pesan,
   Deny akan mengira ada yang rusak.

---

*Ditulis monica, 3 Okt 2026. Perubahan baru di `src/auth.py` (baru),
`src/server.py` (penjagaan sesi di semua rute), `scripts/reset_password.py`
(baru), dan uji `tests/test_auth.py` (12 bagian). `web/` tidak kusentuh.*

**Status endpoint:** 18 rute, semuanya di balik login kecuali `/login`,
`/api/auth` (POST), dan `/api/auth/keluar`.
