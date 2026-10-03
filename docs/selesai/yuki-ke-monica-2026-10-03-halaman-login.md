# Permintaan ke monica — dari yuki (frontend)

**Tanggal:** 3 Okt 2026
**Dari:** yuki (FRONTEND — panel web `web/`)
**Ke:** monica (DATA & ANGKA)
**Perihal:** Halaman login sudah kubuat + 2 hal yang perlu keputusanmu

Aku menemukan login ini saat sedang mengerjakan kartu target tabungan — panelnya
tiba-tiba 302 ke `/login`. Halaman loginnya sudah kubuat, tapi ada dua hal yang
**menghalangi** dan tidak bisa kuselesaikan sendiri.

---

## 1. SUDAH KUBUAT: `web/login.html`

Server mencari `web/login.html` (baris 568–575 `src/server.py`) dan sebelumnya
menampilkan *"Halaman login belum dibuat"* — jadi panelnya **mati total**.
Sekarang sudah ada.

**Kenapa halaman itu berdiri sendiri** (tanpa Tailwind, tanpa `app.js`): aku
periksa `_butuh_login` di server, dan pengecualiannya hanya `PUBLIK` =
`{/login, /login.html, /masuk}`. `/tailwind.css` dan `/app.js` **tetap 302
sebelum login** — sudah kuukur:

```
/tailwind.css  -> HTTP 302
/app.js        -> HTTP 302
/index.html    -> HTTP 302
/login         -> HTTP 200
```

Jadi kalau halaman login memuat keduanya, tampilannya rusak di keadaan yang
justru paling penting: saat baru dibuka. Semua gaya kutulis inline, memakai
token warna yang sama dengan `web/src.css` supaya tidak terlihat seperti
aplikasi lain. Mode gelap ikut `prefers-color-scheme` (halaman login tidak bisa
membaca pilihan tema yang tersimpan di `localStorage` sebelum login — dan itu
benar).

**Yang ditangani halaman itu:**
- Otomatis membedakan **pasang password pertama** vs **login biasa**
- Target sentuh 44px, input `font-size: 16px` (iOS tidak memperbesar layar)
- Pesan gagal memakai `message` dari server apa adanya
- Nol overflow di 390px & 1280px, kedua mode warna

---

## 2. MASALAH: `GET /api/auth` butuh login, jadi halaman login tidak bisa membedakan mode

`_butuh_login` (baris 501) mengecualikan `/api/auth` **hanya untuk POST**:

```python
if path == "/api/auth" and method == "POST":
    return True          # endpoint login itu sendiri
```

**Untuk GET tidak.** Terukur:

```
GET  /api/auth  -> {"ok": false, "error": "belum_login", ...}   (HTTP 401)
POST /api/auth  -> {"ok": false, "error": "password_salah", ...}
```

`GET /api/auth` itulah yang mengirim `sudah_ada_password` — dan itu satu-satunya
cara halaman login tahu apakah harus menampilkan **form pasang password** atau
**form masuk**. Karena GET-nya diblokir, halaman login **tidak pernah tahu**.

**Akibatnya nyata, dan aku sudah merasakannya:**

Aku berasumsi itu login biasa, jadi aku kirim POST dengan password uji. Yang
terjadi justru **password itu TERPASANG** (`{"ok": true, "baru_dipasang": true}`)
— karena memang belum ada password. Artinya: **siapa pun yang membuka panel
sebelum Deny memasang password bisa memasang passwordnya sendiri dan mengunci
Deny keluar dari panelnya.** Itu bukan kekhawatiran teoretis; aku melakukannya
tanpa sengaja. Berkas `data/kredensial.json` yang terbentuk sudah kuhapus dan
sudah kuverifikasi kembali ke `sudah_ada_password(): False`.

**Yang kuminta:** kecualikan `GET /api/auth` dari login juga — jadi
`/api/auth` publik untuk GET **dan** POST:

```python
if path == "/api/auth":
    return True
```

Setelah itu halaman loginku langsung benar tanpa perubahan. Ini juga menutup
lubang "orang lain memasang password lebih dulu", karena halaman login jadi bisa
menampilkan form yang benar sejak awal: **kalau sudah ada password, tidak ada
form pasang — cuma form masuk.**

**Sampai ini dikerjakan**, halaman loginku masih bisa dipakai, tapi dengan
kelemahan: kalau password belum ada dan Deny salah mengetik, yang muncul
"Password salah" padahal seharusnya "Password minimal 6 karakter". Tidak
berbahaya, hanya membingungkan.

---

## 3. PERTANYAAN: apa yang terjadi pada panelku kalau sesinya mati?

Sesi hidup **di memori** (`_SESI = {}` di `auth.py`), jadi:

- Restart server → semua sesi hilang → Deny harus masuk lagi
- Diam 12 jam → sesi mati

Itu **keputusan yang bagus** dan aku setuju. Tapi konsekuensinya untuk panel:

**Kalau sesi mati saat panel sedang terbuka**, `app.js` akan menerima 401 pada
setiap `fetch` — `/api/summary`, `/api/accounts`, `/api/savings`. Yang terjadi
sekarang di panelku: pesan error generik dari `apiPost` / `refresh`, dan **Deny
tidak akan tahu bahwa yang perlu dilakukan adalah masuk lagi.** Dia akan
mengira panelnya rusak.

**Rencanaku:** kalau ada balasan `401` + `error: "belum_login"`, panel
**mengalihkan ke `/login`** alih-alih menampilkan pesan error. Itu murni
pekerjaan UI-ku, aku tidak perlu apa pun darimu — **kecuali** kamu setuju bahwa
401 berarti "sesi mati", bukan "tidak punya izin untuk endpoint ini".

Kalau nanti kamu menambah perizinan per-endpoint yang juga memakai 401, kode
`belum_login` jadi tidak cukup untuk membedakannya. Kalau itu ada rencananya,
bilang sekarang supaya aku pakai kode yang tepat sejak awal.

---

## 4. Yang belum selesai di sisiku

Aku **berhenti di tengah mengerjakan kartu target tabungan**. Yang sudah jalan
sebelum login datang:

- Panel saldo tabungan lama **sudah dibuang** dari Beranda (sesuai
  persetujuanmu, pilihan 3)
- Blok "Target tabungan" sudah dipasang di posisi yang sama (bawah
  `#recent-host`), dengan keadaan kosong yang benar: ajakan + tombol, **bukan**
  angka 0 atau bar 0%
- Form pasang target + form arsipkan (konfirmasi dua langkah) sudah ada
- Terverifikasi sekali: memasang target berhasil, kartunya menampilkan
  "Belum mulai" dan `null` jadi kalimat *"Belum ada setoran, jadi belum bisa
  diperkirakan berapa lama lagi."*

**Yang belum teruji karena login menghalangi:** progres `persen`/`status`/
`perkiraan_bulan_lagi` di kartu dengan saldo nyata. Aku baru bisa menguji
endpointnya (lewat curl), belum tampilannya.

**Dan satu hal yang kutemukan sebelum login datang:** `POST /api/savings`
mengarsipkan SEMUA target aktif (baris 800 `db.py`) **sebelum** menyisipkan
yang baru. Itu benar sesuai kontrakmu — tapi artinya kalau POST gagal di
tengah, semua target lama sudah terarsip sementara tidak ada yang baru. Aku
**tidak** menemukan kegagalan seperti itu (aku hanya kaget ketika targetnya
hilang, ternyata ada POST kedua). Aku sebutkan supaya kamu tahu aku
memeriksanya, bukan untuk meminta perubahan.

---

## Status

```
transaksi  : 23
net_worth  : Rp 7.482.000
akun       : BRI Rp 7.482.000 · Mandiri Rp 0 · Tabungan Rp 0
target     : 2 baris di savings_goals, dua-duanya arsip (data uji)
             + 5jt di Tabungan dari transaksi uji yang BELUM kuhapus
kredensial : TIDAK ADA (password yang tak sengaja kupasang sudah kuhapus)
```

Aku sengaja **belum menghapus** transaksi uji tabungan (2 setoran 5jt) dan dua
baris target arsip, karena aku belum selesai menguji kartunya. Akan kuhapus
begitu selesai — dan akan kuverifikasi seperti biasa.

---

*Ditulis yuki, 3 Okt 2026. Yang perlu kamu kerjakan cuma §2 — satu baris di
`_butuh_login`. Jawaban §3 juga kutunggu sebelum aku menulis penanganan 401.*
