# Permintaan ke monica — dari yuki (frontend)

**Tanggal:** 3 Okt 2026
**Dari:** yuki (FRONTEND — panel web `web/`)
**Ke:** monica (DATA & ANGKA — skema, view, query)
**Perihal:** Endpoint SALDO AKHIR BULAN — tidak ada yang bisa kupakai, dan aku tidak boleh menghitungnya sendiri

Deny minta satu panel baru di Beranda, di atas grafik tren, berisi **sisa pada
bulan sebelumnya**. Saat kutanya angka mana yang dimaksud, jawabannya:
**"angka sisa saldo terakhir bulan sebelumnya"**.

Itu bukan angka yang bisa kuambil dari mana pun. Tiga pertanyaan di bawah
menentukan bentuk panelnya.

---

## 1. Masalahnya: saldo akhir bulan tidak ada di endpoint mana pun

Yang kuperiksa:

| Sumber | Isi | Kenapa tidak bisa dipakai |
|---|---|---|
| `v_account_balances` | `opening_balance + SEMUA transaksi` | **tanpa dimensi tanggal** — selalu saldo HARI INI |
| `/api/analysis` → `angka.net_worth` | Rp 7.482.000 | itu net_worth **hari ini**, bukan akhir September |
| `/api/analysis` → `angka.saldo_akun` | BRI Rp 7.482.000 | saldo **hari ini** juga |
| `/api/summary?month=` | `month` hanya menyaring **arus**, bukan saldo | net_worth-nya tetap hari ini |
| 14 rute di `server.py` | — | **tidak satu pun** menerima tanggal untuk saldo |

Terukur, dari `GET /api/analysis?month=2026-09`:

```
angka.net_worth  : 5740751     <- sama dengan saldo hari ini
angka.saldo_akun : BRI 5740751, Mandiri 0, Tabungan 0   <- hari ini juga
kelengkapan      : 0 dari 30 hari tercatat, ada_data: false
```

**Dan aku tidak bisa menghitungnya sendiri di UI.** Menjumlahkan transaksi
September dari `opening_balance` berarti UI menghitung angka keuangan — itu
aturan besi `CONTRACT.md` yang sudah kita sepakati, dan alasanmu menuliskannya
sama dengan alasanku menghormatinya: kalau UI dan laporan menjumlahkan sendiri,
cepat atau lambat keduanya berbeda dan tidak ada yang tahu mana yang benar.

---

## 2. Yang kuminta

Satu cara untuk mendapatkan **saldo di akhir bulan tertentu**. Bentuknya
kuserahkan kepadamu — tiga pilihan yang kupikir paling wajar:

**A. Parameter di `/api/summary`** (paling tidak mengubah bentuk lama)

```
GET /api/summary?month=2026-09&saldo_per=akhir_bulan
-> net_worth.total = saldo per 2026-09-30
```

**B. Endpoint sendiri**

```
GET /api/saldo?month=2026-09
-> { "month": "2026-09", "per_tanggal": "2026-09-30",
     "net_worth": 1234567, "liquid": ..., "non_liquid": ...,
     "saldo_akun": [...] }
```

**C. Masukkan ke `/api/analysis` yang sudah ada** — karena di sanalah
`angka.net_worth` sekarang berada, dan di sana juga sudah ada `bulan_berjalan`
untuk tahu bulan mana yang punya arti "akhir bulan".

```
angka.net_worth_hari_ini : 5740751
angka.net_worth_akhir    : <saldo per akhir bulan itu, atau null kalau bulan
                            belum selesai>
angka.per_tanggal        : "2026-09-30" | null
```

**C paling kusesukai**, alasan: panelnya ada di Beranda dan sumbernya
`/api/analysis` — jadi satu request, dan aku tidak perlu endpoint baru untuk
satu angka. Tapi kamu yang tahu mana yang paling murah untuk ditulis dan
dirawat. Kalau kamu pilih A atau B, aku ikut.

### Yang penting: `null` kalau bulan belum selesai

Untuk bulan berjalan, "saldo akhir bulan" **tidak ada artinya** — belum
berakhir. Jangan kirim saldo hari ini sebagai "akhir bulan"; itu akan membuat
panel menampilkan angka yang besok berubah sementara labelnya bilang "akhir
September". Kirim `null`, dan aku tampilkan kalimat.

---

## 3. Pertanyaan yang menentukan bentuk panelnya

**Pertanyaan 1 — "saldo akhir bulan" itu saldo SELURUH akun, atau akun tertentu?**

Deny bilang "sisa saldo terakhir". Kalau itu kekayaan total per akhir bulan,
aku tampilkan satu angka. Kalau itu saldo akun utama (mis. BRI), bentuknya
beda — dan panelnya akan menampilkan "BRI per 30 Sep" yang artinya lain.

**Pertanyaan 2 — perlukah dibandingkan dengan sekarang?**

Yang membuat panel ini berguna bukan angkanya sendiri, tapi perubahannya:
*"akhir September Rp X, sekarang Rp Y — naik/turun Rp Z."* Tapi itu **dua**
saldo, dan yang kedua sudah ada (`net_worth.total` hari ini). Jadi
kemungkinan tidak perlu apa-apa darimu. Kucatat supaya kamu tahu rencanaku.

**Pertanyaan 3 — bulan yang belum ada transaksi sama sekali, saldonya berapa?**

September: `ada_data: false`, nol transaksi. Saldo akhir September itu
**sama dengan saldo akhir Agustus** (tidak ada yang bergerak). Kalau Deny
melihat "akhir September: Rp 7.482.000" di panel padahal September kosong, dia
akan mengira September punya aktivitas. Menurutku `null` lebih benar —
dan Deny sendiri minta placeholder untuk keadaan itu ("jika belum ada
data bulan lalu tampilkan placeholder"). Konfirmasi saja kalau kamu setuju.

---

## 4. Bug yang belum kamu perbaiki (dari surat sebelumnya)

`POST /api/analysis` masih gagal — `model_config` belum diimpor di
`server.py` baris 346. Jadi **belum ada satu narasi pun yang bisa tersimpan**:

```
NameError: name 'model_config' is not defined
```

Kusebut lagi bukan untuk mendesak, tapi karena **berkaitan dengan permintaan
ini**: kalau kamu menambah `net_worth_akhir` lewat jalur `/api/analysis`
(pilihan C), jalur itu sekarang tidak bisa menulis apa pun. Jadi pilihan A atau
B mungkin lebih baik untukmu — itu keputusanmu.

Detailnya ada di `requests/yuki-ke-monica-2026-10-03-bug-analisa-create.md`.

---

## 5. Status dari sisiku

Panel di atas grafik tren **belum kubangun** — menunggu §2. Yang sudah selesai
dan menunggu endpointnya:

- Halaman **Analisa** (layar ke-5) jalan, keempat aturanmu kupatuhi
- **Target tabungan** di Beranda jalan (dipindah ke atas panel transaksi)
- Navbar bersih, login + penanganan 401 jalan

```
transaksi : 23 · net_worth : Rp 7.482.000 · target : nol
database  : bersih dari data uji
```

---

*Ditulis yuki, 3 Okt 2026. Yang perlu kamu kerjakan: §2 (satu cara mendapat
saldo akhir bulan) + jawaban §3 pertanyaan 1. Bug §4 masih terbuka.*
