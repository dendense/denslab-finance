# Laporan: pencatatan lewat chat — draft dulu, simpan hanya atas Deny

**Dari:** monica (DATA & ANGKA)
**Tanggal:** 9 Okt 2026
**Kartu:** `t_0c4c4678`
**Status:** selesai — semua bukti di bawah dijalankan sungguhan, bukan didesain
**Revisi:** ronde 2 (9 Okt 2026) — menutup temuan review ronde 1 (fail-open negasi)

---

## Perubahan ronde 2 — penjaga negasi

Review ronde 1 menemukan cacat **fail-open**: `periksa_konfirmasi()` mencocokkan
kata afirmatif sebagai substring **tanpa penjaga negasi**, sehingga
`"simpan"` ⊂ `"jangan simpan"` dan `"setuju"` ⊂ `"tidak setuju"`. Kalimat
**penolakan** Deny lolos gerbang dan tertulis ke ledger — kebalikan dari
Definisi selesai #2 ("ragu → berhenti, fail-closed").

Perbaikan di `src/chat_gate.py`:

| Tambahan | Perilaku |
|---|---|
| `NEGASI_SUB` / `NEGASI_KATA` | teks memuat penyangkal → kode `ditolak` |
| `KATA_TANYA` + deteksi `?` | kalimat bertanya → kode `pertanyaan` |

Urutannya: cek afirmatif dulu (supaya teks tanpa perintah sama sekali tetap
`tidak_afirmatif`), lalu penjaga negasi, lalu penjaga pertanyaan. Penyangkal
**menang** atas kata afirmatif — itu inti fail-closed-nya.

Sikapnya sengaja boros: **seluruh** teks yang memuat penyangkal ditolak, bukan
hanya pola "penyangkal + afirmatif". Konsekuensinya "jangan lupa simpan" ikut
ditolak — disengaja. Menebak kalimat bermakna ganda adalah jalur "mungkin
benar" yang tidak ada di gerbang ini.

Uji: 44 → **74 pemeriksaan**, semua lulus. 21 regresi negasi/pertanyaan + 8
kontrol yang memastikan penjaga tidak terlalu luas sampai ikut menolak
perintah sah ("simpan", "ya, simpan", "oke simpan", "setuju", "sip",
"tolong catat", "lanjut simpan", "silakan simpan").

`CONTRACT.md` §18 diperbarui: tabel "Yang DITOLAK" kini memuat `ditolak` dan
`pertanyaan`, plus bagian "Penjaga negasi".

---

## Keputusan yang mengikat (dari Deny, dijawab langsung)

| # | Pertanyaan | Keputusan |
|---|---|---|
| 1 | Boleh mencatat lewat chat atas perintah yang disampaikan Rin? | **YA** |
| 2 | Konfirmasi tetap dua langkah? | **YA — wajib** |
| 3 | Rin boleh menyimpan sendiri? | **TIDAK — setiap simpan lewat Deny** |

---

## Yang dikerjakan

| Berkas | Isi |
|---|---|
| `src/chat_gate.py` | Gerbang: `draft()` (baca-saja) + `simpan()` (menulis, tapi menuntut konfirmasi Deny), dengan penjaga negasi. |
| `tests/test_chat_gate.py` | 74 pemeriksaan: (a) draft tidak menulis, (b) simpan tanpa Deny ditolak, (b2) penjaga negasi, (c) simpan setelah Deny berhasil, (d) asal tercatat, (+) Rin tidak punya jalur simpan. |
| `scripts/contoh_draft_chat.py` | Contoh keluaran draft NYATA lewat parser hidup. |
| `scripts/uji_hidup_chat.py` | Alur hidup: draft → tolak negasi → tolak Rin → simpan Deny, di salinan. |
| `docs/CONTRACT.md` §18 | Aturan lengkap, termasuk penjaga negasi dan batas yang jujur. |
| `.gitignore` | `chat_simpan.log` (data, bukan kode). |

`draft()` memakai **parser yang sama** dengan halaman Catat
(`parser_wrap.parse_kontrak`) — tidak ada jalur parse kedua. Diuji dengan spy.

Commit: `9f6a56d` (ronde 2), di atas `bbe807c` (ronde 1).

---

## Bukti

### Uji otomatis

```
python3 tests/test_chat_gate.py     ->  HASIL: semua uji lulus  (74 pemeriksaan)
seluruh 15 berkas uji di tests/     ->  15 lulus, 0 gagal
```

Termasuk, lewat AST (bukan dibaca mata):
- hanya `simpan()` yang memanggil penulisan ledger;
- `server.py` tidak mengimpor `chat_gate`; tidak ada rute `/api/chat`;
- memanggil `simpan()` dengan `pengirim: "rin"` **tetap ditolak**.

### Salinan database, bukan `finance.db` Deny

| | Jumlah baris |
|---|---|
| `finance-pribadi/finance.db` SEBELUM | 42 |
| `finance-pribadi/finance.db` SESUDAH | **42** |

Semua penulisan uji terjadi di salinan `/tmp`. Tidak ada `chat_simpan.log`
yang tertinggal di folder data Deny (diperiksa langsung).

### Alur hidup (`scripts/uji_hidup_chat.py`, parser hidup, model `deepseek-v4-1-flash`)

```
1. DRAFT "beli makan malam 32000 pakai BRI"
     1. Rp 32.000  Pengeluaran  BRI  2026-10-09 (dianggap hari ini)
     baris sebelum=42 sesudah=42  TIDAK bertambah

2. Deny membalas PENOLAKAN
     "jangan simpan"           -> ditolak
     "tidak setuju"            -> ditolak
     "batal, jangan lanjut"    -> ditolak
     baris sebelum=42 sesudah=42  TIDAK bertambah
     jejak dibuat? tidak

3. Rin mencoba menyimpan sendiri
     -> bukan_deny: Perintah simpan hanya sah kalau datang dari Deny sendiri.
     baris masih 42

4. Deny memerintahkan simpan
     -> ok=True id=[113]
     baris sebelum=42 sesudah=43
     jejak asal: {"disimpan_pada": "2026-10-09T09:36:23", "pengirim": "deny",
                  "kanal": "telegram", "waktu_konfirmasi": "2026-10-09T21:30:00",
                  "teks_konfirmasi": "simpan", "jumlah": 1, "saved_ids": [113]}
```

### Contoh keluaran draft NYATA (parser hidup, `scripts/contoh_draft_chat.py`)

```
KAMU : beli makan malam 32000
  1. Rp 32.000  Pengeluaran  (akun belum jelas)  2026-10-09 (dianggap hari ini)
     catatan: beli makan malam
  Akun belum jelas. Pilih salah satu: BRI, Mandiri, Tabungan
  Belum ada yang tersimpan. Balas "simpan" untuk menyimpan.

KAMU : makan siang 25rb sama parkir 5rb
  1. Rp 25.000  Pengeluaran ...  2. Rp 5.000  Pengeluaran ...   (dua transaksi, tidak digabung)

KAMU : bayar cicilan pinjaman online 500rb
  1. Rp 500.000  Bayar utang ...  (bukan Pengeluaran)
```

---

## Postur jaringan tidak berubah

`chat_gate.py` tidak mengimpor modul jaringan apa pun, tidak membuka port, dan
tidak menyentuh kunci API. Server tetap `127.0.0.1`. Modul ini membaca
`finance.db` langsung sebagai proses di Mac yang sama.

---

## Batas yang jujur

Gerbang ini **tidak bisa memverifikasi identitas.** Tidak ada kriptografi, dan
tidak ditambahkan karena keputusan Deny melarang kunci API baru. Yang ditegakkan
hanya **struktur perintah**: dua langkah, orang-pertama (bukan laporan tentang
orang lain), dan jejak asal.

Kalau seseorang mengetik `pengirim: "deny"` padahal bukan Deny, gerbang ini
tidak tahu. Aturan "Rin tidak punya jalur simpan" dipenuhi oleh kenyataan bahwa
**tidak ada** fungsi/endpoint/perintah yang bisa dipanggil Rin tanpa melewati
satu langkah yang dipegang manusia — bukan oleh gerbang ini sendiri. Ini
ditulis apa adanya di `CONTRACT.md` §18 supaya tidak diklaim lebih dari yang
bisa dibuktikan.

---

## Sisa yang belum dikerjakan (butuh keputusan, bukan kode)

Jalur ini **belum terhubung ke chat mana pun.** Yang ada sekarang adalah
gerbangnya, sudah teruji. Menyambungkannya ke Telegram berarti memberi Rin
kemampuan memanggil `draft()` (aman, baca-saja) — tapi Deny sendiri yang harus
memasukkan `konfirmasi` dengan `pengirim: "deny"`. Belum ada yang memutuskan
bentuk sambungan itu, dan itu di luar kartu ini.
