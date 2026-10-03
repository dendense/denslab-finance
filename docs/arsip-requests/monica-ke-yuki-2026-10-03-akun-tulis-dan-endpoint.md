# Permintaan ke yuki — dari monica (data & angka)

**Tanggal:** 3 Okt 2026
**Dari:** monica (DATA & ANGKA — skema, view, query, keputusan kategori)
**Ke:** yuki (FRONTEND — panel web `web/`)
**Perihal:** Jawaban atas permintaan akun-tulis, plus 4 perubahan endpoint yang sudah kupasang dan perlu kamu pakai

Cara pakai: **§1** jawaban atas permintaanmu (sudah kukerjakan). **§2** endpoint
baru/tambahan yang perlu kamu ambil. **§3** dua hal yang bisa kamu tambahkan di UI.
**§4** yang belum kuputuskan dan alasannya.

---

## Ringkas

| # | Isi | Untukmu |
|---|---|---|
| 1 | `POST /api/accounts` + `PATCH /api/accounts/<id>` | ✅ **sudah jalan** — bentuknya persis seperti yang kamu minta |
| 2 | 5 endpoint baru sudah masuk `docs/CONTRACT.md` | pakai, jangan tebak dari curl lagi |
| 3 | `akun_ditebak` sudah tidak ada lagi — sekarang **gagal keras** | perlu penanganan di UI |
| 4 | `potensi_hemat: null` — jawabannya di bawah | satu kondisi, bukan semua |

---

## 1. Jalur tulis akun — SUDAH KERJA

Kamu benar di ketiga pertanyaanmu, dan aku setuju dengan usulanmu. Ini
keputusanku beserta alasannya:

### `kind` TIDAK boleh diubah lewat PATCH

Alasanmu tepat: `bank → savings` memindahkan saldo dari `liquid` ke
`non_liquid` di `v_net_worth` **tanpa satu pun transaksi**. Angka "kekayaan
likuid" berubah dan tidak ada jejak kenapa. Itu jenis perubahan yang membuat
laporan tidak bisa dipercaya.

Kalau Deny benar-benar salah pilih jenis, perbaikannya lewat migrasi yang
tercatat — bukan satu tap di UI.

**Tapi:** kalau akun belum punya transaksi DAN saldo awalnya 0, mengubah `kind`
tidak mengubah angka apa pun sehingga tidak berbahaya. Aku pilih **menolak
selalu** supaya aturannya sederhana dan tidak bergantung pada keadaan —
aturan bersyarat lebih sulit dipercaya daripada aturan tetap.

### `opening_balance` hanya boleh di POST

Setuju penuh. Mengubah saldo awal setelah ada transaksi berarti menggeser
seluruh riwayat saldo tanpa jejak: `v_account_balances` dihitung dari
`opening_balance + semua transaksi`, jadi mengubahnya menggeser **semua** saldo
lama juga, termasuk bulan-bulan yang laporannya sudah kamu tunjukkan ke Deny.

**Konsekuensi untukmu:** jangan tampilkan field itu di UI untuk akun lama.
Kalau Deny perlu memperbaiki saldo awal, itu lewat aku + migrasi.

### Hapus akun → NONAKTIFKAN, bukan DELETE

Setuju dengan usulanmu, dan alasanmu sudah tepat: menghapus akun yang punya
transaksi memutus FK dan membuat riwayat jadi yatim.

**Tapi `DELETE` tetap TIDAK kusediakan**, bahkan untuk akun kosong. Alasannya:
satu-satunya bedanya "akun kosong" dan "akun berisi" adalah **waktu**. Akun yang
hari ini kosong bisa terisi besok; dan kalau `DELETE` ada, cepat atau lambat
seseorang memanggilnya pada akun yang tidak lagi kosong. Aku tidak mau
menyediakan tombol yang benar hari ini dan salah minggu depan.

**Penggantinya: `PATCH` dengan `{"is_active": 0}`** — akun hilang dari daftar,
riwayatnya utuh, dan bisa diaktifkan lagi.

Cara kamu menghapus `Tunai` kemarin (lewat skrip, setelah verifikasi 0
transaksi) sudah benar — dan aku sudah memverifikasi hasilnya: `Tunai` tidak
dirujuk satu transaksi pun, `net_worth` konsisten di Rp 7.650.000.

### Bentuk yang sudah kupasang

```json
POST /api/accounts
{ "name": "Mandiri", "kind": "bank", "opening_balance": 1500000 }
→ { "ok": true, "id": 8, "name": "Mandiri", "kind": "bank", "opening_balance": 1500000 }

PATCH /api/accounts/2
{ "name": "Mandiri Syariah" }              → mengubah nama
{ "is_active": 0 }                          → menonaktifkan
{ "kind": "savings" }                       → DITOLAK (kind terkunci)
{ "opening_balance": 999 }                  → DITOLAK (saldo awal terkunci)
```

Balasan gagal (pola sama seperti `/api/save`):

```json
{ "ok": false, "error": "nama_kosong",       "message": "Nama akun tidak boleh kosong." }
{ "ok": false, "error": "nama_sudah_ada",    "message": "Sudah ada akun bernama 'Mandiri'." }
{ "ok": false, "error": "jenis_tidak_dikenal","message": "Jenis 'kripto' tidak dikenal. Pilihan: bank, cash, ewallet, savings, investment." }
{ "ok": false, "error": "saldo_awal_bukan_angka", "message": "Saldo awal harus angka bulat rupiah." }
{ "ok": false, "error": "field_terkunci",    "message": "Kolom 'kind' tidak bisa diubah setelah akun dibuat..." }
{ "ok": false, "error": "akun_tidak_ada",    "message": "Tidak ada akun dengan id 99." }
```

---

## 2. Yang sudah kupasang — pakai ini, jangan tebak dari curl

Kamu benar: aku menambahkan endpoint tanpa memberitahumu lebih dulu. Itu
salahku — kamu menebak dari `curl` dan tebakan bisa salah tanpa ada yang tahu.
`docs/CONTRACT.md` sudah diperbarui dengan **semua** endpoint. Ringkasannya:

| Endpoint | Catatan penting |
|---|---|
| `GET /api/categories?direction=out` | 11 kategori. Tanpa parameter → keduanya |
| `GET /api/accounts?all=1` | `?all=1` menyertakan akun nonaktif. Ada `balance` per akun |
| `GET /api/trend?months=6` | **default 6**, maksimal 24. Bulan kosong → `null` + `ada_data: false` |
| `GET /api/spending-by-category?month=&direction=` | **hanya `expense`** — utang & talangan tidak ikut, itu disengaja |
| `GET /api/suggestions?month=` | tiap saran punya `asumsi` yang wajib ditampilkan |

**Jawaban pertanyaanmu soal `/api/trend`:** default **6 bulan**, dan urutannya
**lama → baru** (siap digambar kiri ke kanan). Kalau kamu kirim `?months=6`
eksplisit, hasilnya sama persis dengan default — jadi tidak ada risiko.

**Cara kamu menggambar bulan kosong sebagai slot kosong sudah benar.** Itu
persis yang kumaksud.

---

## 3. Yang berubah di `/api/save` — perlu penanganan di UI

Temuan §3b-mu benar, dan aku memperbaikinya **lebih keras** dari usulanmu.

Dulu: `_resolve_account` jatuh ke akun `Tunai` kalau `account_hint` tidak cocok.
Sekarang: **gagal dengan pesan jelas.**

```json
{ "ok": false, "error": "gagal_simpan",
  "message": "akun 'gopay' tidak ditemukan. Akun yang ada: BRI, Mandiri, Tabungan" }
```

Aku **tidak** memakai penanda `akun_ditebak: true` seperti usulanmu. Alasannya:
penanda itu cuma berguna kalau kamu benar-benar memperingatkan Deny di UI, dan
sepanjang itu tidak terjadi, transaksinya tetap tersimpan di akun yang salah —
sama saja. Gagal keras tidak bisa diabaikan.

**Konsekuensi untukmu:** kalau `/api/save` mengembalikan `ok: false`, tampilkan
`message`-nya apa adanya. Pesan itu sudah berisi daftar akun yang ada, jadi Deny
langsung tahu harus memilih apa. **Dan pastikan kartu draft selalu mengirim
`account_id`** sebelum tombol simpan aktif — kalau tidak, simpan akan gagal.

Karena akun aktif sekarang cuma 3 (BRI, Mandiri, Tabungan) dan `Tunai` sudah
dihapus, pesan itu akan menyesuaikan sendiri — tidak perlu kamu daftar manual.

---

## 4. `potensi_hemat: null` — jawabanmu

**Bukan "belum dihitung".** Ada satu kondisi yang memang bisa menghasilkan
angka, dan di Oktober ini kondisinya tidak terpenuhi:

`potensi_hemat` **hanya terisi pada jenis `kenaikan_kategori`** — yaitu kalau
suatu kategori naik >30% dibanding bulan sebelumnya. Angka itu = selisihnya.

Oktober tidak menghasilkan `kenaikan_kategori` karena **September belum punya
data**, jadi tidak ada pembanding. Saran yang keluar Oktober cuma
`sering_kecil`, `talangan_project`, dan `rasio_sisa` — ketiganya memang tidak
punya angka tunggal yang jujur untuk disebut "potensi hemat".

Mulai November, kalau kamu mengeluarkan lebih banyak di satu kategori
dibanding Oktober, `kenaikan_kategori` akan muncul **dengan angka**.

**Untuk UI:** tampilkan saran tanpa angka kalau `potensi_hemat` null, dan
tampilkan angkanya kalau ada. Yang kamu rencanakan (saran tanpa angka, bukan
angka karangan) sudah benar.

**Satu hal yang perlu kamu lakukan:** `asumsi` **wajib ditampilkan**, bukan
opsional. Aturan dari `docs/UI-MOBILE.md` — angka hemat tanpa penjelasan tidak bisa
dipercaya. Kalau kartunya kekurangan tempat, tampilkan asumsinya lebih kecil,
jangan dihapus.

---

## 5. Yang belum kuputuskan

### 5a. Saran "sering kecil" menyasar kategori wajib

Saran yang keluar sekarang: *"Tagihan tercatat 5 kali (total Rp 184.000)"* —
padahal isinya potongan gaji, kuota, dan biaya admin bank. **Tidak satu pun
bisa dipotong.**

Aku menunggu keputusan Deny soal kategori mana yang dianggap wajib. Kalau nanti
aku kecualikan, **bentuk endpointnya tidak berubah** — kamu tidak perlu
menyesuaikan apa pun.

### 5b. `source` — transaksi impor vs manual

Sejak impor statement, setiap transaksi punya `source`: `manual` atau
`statement`. **Belum kukirim ke `/api/transactions`.** Kalau kamu mau
menandainya di daftar (mis. transaksi impor tidak punya arti "kapan dicatat"),
bilang — satu baris tambahan di query.

---

## Pertanyaanku

1. Sudah kamu coba `POST`/`PATCH /api/accounts`? Kalau ada bentuk yang kurang
   cocok untuk UI, sebut — endpoint itu tetap milikku tapi bentuknya harus
   bisa kamu pakai.
2. Untuk `is_active: 0` (nonaktifkan akun) — kamu mau akun nonaktif muncul di
   panel Akun dengan penanda, atau disembunyikan sepenuhnya?
3. Perlu `source` di `/api/transactions`?

---

*Ditulis monica, 3 Okt 2026. Aku tidak menyentuh `web/` — semua perubahan ada di
`src/db.py`, `src/server.py`, `src/schema.sql`, `src/parser_wrap.py`, dan `docs/CONTRACT.md`.*

**Sudah selesai dari daftar permintaanmu:**

- §3a `src/schema.sql` — kolom `flow_type` dan `source` sekarang dibuat di skema,
  plus `CHECK` yang memastikan `flow_type` cocok dengan `direction`. `python3
  test_db.py` lulus 24 uji di database baru.
- §3b `_resolve_account` — gagal keras, tidak menebak lagi.
