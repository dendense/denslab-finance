# Handoff ke yuki — panel web finance

Dari **monica**, 1 Okt 2026. Surat ini sudah **selesai dijalankan** dan disimpan sebagai arsip.

> **Koreksi 23 Okt 2026 (sebelum diarsipkan).** Lima pernyataan di surat ini sudah tidak benar
> dan dikoreksi di tempat, ditandai **[KOREKSI]**. Alasannya: surat yang dibaca sebagai dokumen
> aktif membuat pembaca mengira `web/` masih kosong dan aturan angkanya masih yang lama.
> Acuan yang berlaku sekarang: `docs/CONTRACT.md` (endpoint), `docs/UI-MOBILE.md` (UI),
> `docs/SCHEMA.md` (skema), `src/schema.sql` (sumber kebenaran DDL).

---

## Yang sudah siap

| Bagian | Status |
|---|---|
| Database SQLite + **4** view analisa | ✅ jalan — **[KOREKSI]** dulu ditulis 3 view; sekarang `v_account_balances`, `v_monthly_flow`, `v_net_worth`, `v_savings_progress` (`src/schema.sql:141,170,217,239`) |
| Data nyata: transaksi BRI Okt 2026 | ✅ terekonsiliasi ke rupiah |
| Server API (`src/server.py`, port 8791) | ✅ jalan |
| Parser chat → draft terstruktur | ✅ 14/15 akurasi (`src/parser_wrap.py`, 255 baris) |

**Server hidup.** Kamu bisa langsung `curl` untuk melihat bentuk datanya.

```
GET  http://localhost:8791/api/summary?month=2026-10
GET  http://localhost:8791/api/transactions?limit=20
POST http://localhost:8791/api/parse   {"text":"makan malam 45000"}
POST http://localhost:8791/api/save    {"transactions":[...]}
```

Folder kerjamu: **`~/Documents/AI/finance/web/`** — **[KOREKSI]** dulu ditulis "masih kosong";
sekarang berisi 9 berkas tracked (`app.js` 4.643 baris, `index.html`, `login.html`, `src.css`,
`tailwind.css` hasil build, `package.json`, `package-lock.json`, `README.md`, `.gitignore`).
`src/server.py:29` (`STATIC = ROOT_DIR / "web"`) menyajikan folder itu di
`http://localhost:8791/`. Halaman yang butuh sesi diarahkan ke `/login`.

## Bacaan wajib sebelum mulai

**`docs/CONTRACT.md`** — **[KOREKSI]** dulu ditulis `~/Documents/AI/finance/CONTRACT.md`;
berkasnya ada di `docs/CONTRACT.md`. Bentuk setiap endpoint, field demi field, sudah
diverifikasi. Jangan mengarang field; kalau butuh tambahan, bilang ke monica.

## Data nyata yang akan kamu lihat

```
net_worth.total : 7.660.000
total_in        : 8.200.000
total_out       : 2.100.000
expense_real    :   284.000   <- pengeluaran sungguhan
receivable_out  :   285.458   <- talangan studio-contoh
debt_payment_out: 1.400.000   <- pelunasan utang
tx_count        : 15
```

---

## Tiga jebakan yang paling mudah salah

### 1. Kartu "Pengeluaran" — bedakan beranda dan grafik

**[KOREKSI]** Dulu surat ini bilang: kartu "Pengeluaran" pakai `flow.expense_real`, **BUKAN**
`flow.total_out`. Itu sudah tidak berlaku untuk **beranda**. Aturan yang benar sekarang
(`docs/CONTRACT.md` §2, kode `web/app.js:537`):

| Tempat | Field | Label |
|---|---|---|
| Kartu "Pengeluaran" di **beranda** | `total_out` | "Pengeluaran" (all-in: konsumsi + talangan + pelunasan utang) |
| Grafik tren 6 bulan · konsumsi per kategori · analisa bulanan | `expense_real` | **"Konsumsi"**, bukan "pengeluaran" |

Oktober ini bedanya ~7-8x lipat: Rp 284.000 vs Rp 2.100.000. Kalau `expense_real` dipakai di
beranda, panel menyembunyikan uang yang benar-benar keluar; kalau `total_out` dipakai di grafik
tanpa label "konsumsi", panel menyebut pelunasan utang sebagai gaya hidup. Dua-duanya salah.
Angka di kartu beranda **≠** angka di grafik — itu memang disengaja.

### 2. Warna dan label per `flow_type`

| `flow_type` | Label | Warna |
|---|---|---|
| `expense` | Pengeluaran | merah |
| `income` | Pemasukan | hijau |
| `receivable` | Talangan (piutang) | biru |
| `debt_payment` | Bayar utang | oranye |
| `transfer` | Pindah akun | abu, netral |

Kalau semua ditampilkan merah sebagai "pengeluaran", panelnya menyesatkan.

### 3. `ada_data: false` bukan nol

Bulan tanpa transaksi mengembalikan `ada_data: false` dan `tx_count: 0`.
Tampilkan **"belum ada data bulan ini"**, jangan angka `0` — nol dan "tidak ada
data" adalah dua hal berbeda.

---

## Yang kuminta darimu

### A. Panel utama — ikuti `docs/UI-MOBILE.md`

Urutan: **total kekayaan** (angka besar, pertama dicari) → pemasukan & pengeluaran
bulan berjalan → selisih → grafik tren → daftar transaksi terbaru.

### B. Daftar transaksi dengan label `flow_type`

Bukan cuma "masuk/keluar" — talangan dan pelunasan utang harus terlihat beda.

### C. Kolom chat di bawah

Input kalimat → `POST /api/parse` → tampilkan kartu draft → Deny konfirmasi →
`POST /api/save`. **Dua langkah, tidak boleh digabung.**

Yang wajib ditangani:
- `assumed_date: true` → penanda "tanggal dianggap hari ini", bisa diubah
- `ok: false` → pesan gagal **+ tombol "isi manual"**
- Lebih dari satu transaksi → daftar yang dicek satu-satu
- `question` terisi dan `transactions` kosong → balasan chat biasa, bukan kartu

### D. Chip koreksi `flow_type` di kartu draft — **ini penting**

Parser menebak `flow_type` dari kata kunci, dan **kadang salah**. Contoh nyata:

> `"saya transfer 100000 buat adik"` → parser menebak `expense` (mungkin benar),
> tapi bisa juga piutang.
> `"top up gopay 100000"` → semua model gagal menebak; kalimatnya memang ambigu.

Karena itu chip koreksi bukan kemewahan — itu yang membuat datanya benar. Parser
menebak, Deny mengoreksi satu tap. Sama seperti kategori: chip, bukan dropdown.

Nilai yang sah: `expense` · `income` · `receivable` · `debt_payment` · `transfer`.

---

## Aturan yang tidak boleh dilanggar

1. **UI tidak menghitung angka keuangan.** Semua angka dari API. Kalau UI
   menjumlahkan sendiri, cepat atau lambat UI dan laporan berbeda.
2. **`/api/parse` tidak menyimpan.** Simpan hanya lewat `/api/save`.
3. **Format uang `Rp 1.100.000`** — titik pemisah ribuan, selalu diformat.
4. **`amount` selalu positif.** Arah dari `direction`, bukan tanda angka.
5. **Target sentuh minimum 44×44 px**, tidak ada tombol kecil di tepi layar.
6. **Mobile-first.** Rancang dari layar HP, bukan desktop yang dikecilkan.

## Yang belum ada — jangan diasumsikan ada

- Pelacakan pelunasan piutang (piutang tercatat keluar, belum bisa ditandai lunas)
- Saldo utang berjalan
- Budget per kategori, ekspor PDF
- Offline / service worker

**[KOREKSI]** Dulu surat ini menyebut "target tabungan" sebagai belum ada. Sekarang **sudah
ada**: tabel `savings_goals` (`src/schema.sql:119`), view `v_savings_progress`
(`src/schema.sql:239`), rute `GET/POST/DELETE /api/savings` (`src/server.py:1165,1211,1252`),
dan uji `tests/test_savings.py` (194 baris). Progres dihitung dari saldo akun, tidak disimpan.

Kalau butuh salah satu ini, koordinasi dengan monica dulu.

---

## Pertanyaan?

Semua yang berhubungan dengan **angka, kategori, sifat transaksi, bentuk data** →
tanya **monica**. Jangan putuskan sendiri; satu kategori yang bergeser diam-diam
membuat laporan tetap terlihat rapi tapi salah.
