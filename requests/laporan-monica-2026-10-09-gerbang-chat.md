# Laporan: pencatatan lewat chat — draft dulu, simpan hanya atas Deny

**Dari:** monica (DATA & ANGKA)
**Tanggal:** 9 Okt 2026
**Kartu:** `t_0c4c4678`
**Status:** selesai — semua bukti di bawah dijalankan sungguhan, bukan didesain
**Revisi:** ronde 4 (9 Okt 2026) — menutup temuan review ronde 4 (normalisasi

  membuang penanda penolakan → karakter asing kini ditolak, fail-closed)

---

## Perubahan ronde 4 — karakter asing ditolak (penanda penolakan tidak boleh hilang)

Review ronde 4 membuktikan daftar putih (ronde 3) masih bocor di **hulunya**:
`_normalisasi_perintah()` memakai `re.sub(r"[^\w\s]+", " ", teks.lower())` dan
membuang **setiap** karakter non-huruf/angka tanpa syarat. Emoji/simbol
penolakan ikut terhapus **sebelum** gerbang memutuskan, dan sisa teksnya jadi
persis perintah yang diakui daftar putih.

Bentuk berikut **benar-benar tertulis ke ledger** sebelum perbaikan ini
(pengirim `"deny"`, di salinan, baris 42→48):

```
'❌ simpan'  -> ok=True  42->43  TERTULIS
'⛔ simpan'  -> ok=True  43->44  TERTULIS
'🚫 simpan'  -> ok=True  44->45  TERTULIS
'✗ simpan'   -> ok=True  45->46  TERTULIS
'✖ simpan'   -> ok=True  46->47  TERTULIS
'simpan ❌'  -> ok=True  47->48  TERTULIS
```

Kelas cacatnya sama dengan ronde 1 & 3: penolakan Deny diperlakukan sebagai
perintah. Bedanya di tingkat: ronde 1/3 di tingkat **kata**, ronde 4 di tingkat
**karakter**.

Perbaikannya (`src/chat_gate.py`):

- `_normalisasi_perintah()` kini hanya memetakan **pemisah netral** (`,` `.`
  `!`) ke spasi. Huruf kecil + spasi dirapatkan seperti sebelumnya, tapi
  karakter lain **tidak dibuang** lagi.
- `perintah_diizinkan()` menolak lebih dulu kalau teks (setelah normalisasi)
  masih memuat karakter di luar huruf/angka/spasi — `_POLA_ASING` → `False`.
  Prinsipnya: sebuah penanda penolakan tidak boleh bisa hilang sebelum gerbang
  memutuskan.
- Akibatnya `ya, simpan` / `oke simpan` / `tolong catat` tetap lolos, sedangkan
  `❌ simpan`, `simpan 🔥`, dan `si-mpan` berhenti.

**Reproduksi temuan ronde 4, sekarang** (dijalankan, bukan dibaca mata):

```
normalisasi:  '❌ simpan' -> '❌ simpan'   (dulu 'simpan')
perintah_diizinkan: '❌ simpan' -> False   (dulu True)
periksa_konfirmasi: '❌ simpan' -> ditolak (dulu None = sah)

end-to-end simpan() ke salinan:
  '❌ simpan'  -> ok=False  baris 42->42  tidak bertambah   (dulu TERTULIS)
  '⛔ simpan'  -> ok=False  baris 42->42  tidak bertambah   (dulu TERTULIS)
  '🚫 simpan'  -> ok=False  baris 42->42  tidak bertambah   (dulu TERTULIS)
  '✗ simpan'   -> ok=False  baris 42->42  tidak bertambah   (dulu TERTULIS)
  '✖ simpan'   -> ok=False  baris 42->42  tidak bertambah   (dulu TERTULIS)
  'simpan ❌'  -> ok=False  baris 42->42  tidak bertambah   (dulu TERTULIS)
```

**Uji:** `tests/test_chat_gate.py` 121 → **143 pemeriksaan, 0 gagal**. Tambahan
bagian (b4): 8 bentuk berkarakter asing (`ditolak`), 8 unit `perintah_diizinkan()`
berkarakter asing (semua ditolak), 5 kontrol pemisah netral tetap lolos. Seluruh
**15/15** berkas uji lulus. `CONTRACT.md` §18 diperbarui: baris tabel "Yang
DITOLAK" + sub-bagian "Karakter asing ditolak".

---

## Ronde 3 — daftar putih menggantikan daftar hitam

Review ronde 3 membuktikan tambalan ronde 2 masih **fail-open**. Ronde 2 menutup
penolakan dengan **daftar hitam** penyangkal, dan daftar hitam bahasa Indonesia
informal tidak pernah selesai. Bentuk berikut **benar-benar tertulis ke ledger**
sebelum perbaikan ronde 3 (pengirim "deny", di salinan):

```
'ndak usah simpan'   -> ok=True  rows 42->43 TERTULIS
'ndak simpan'        -> ok=True  rows 43->44 TERTULIS
'kagak usah simpan'  -> ok=True  rows 44->45 TERTULIS
'no simpan'          -> ok=True  rows 45->46 TERTULIS
'udah simpan'        -> ok=True  rows 46->47 TERTULIS
'sudah saya simpan'  -> ok=True  rows 47->48 TERTULIS
```

Perbaikannya **membalik arah kegagalan**: keputusan akhir bukan lagi "bukan
penolakan yang kita kenali", melainkan "**bentuk perintah yang kita akui**".
Fungsi `perintah_diizinkan()` memeriksa teks terhadap **daftar putih**:

- satu kata afirmatif: `ya` · `iya` · `ok` · `oke` · `sip` · `setuju` · `benar`
- satu kata perintah: `simpan` · `catat`
- prefiks + perintah: `ya simpan` · `oke simpan` · `tolong catat` ·
  `lanjut simpan` · `silakan simpan` · `gas simpan` · `ayo catat` …

**Apa pun di luar daftar itu DITOLAK** (`ditolak`), fail-closed. Daftar hitam
penyangkal ronde 2 tetap ada tapi turun peran: hanya memilih kode pesan yang
lebih tepat (`ditolak` vs `tidak_afirmatif`). Yang benar-benar menjaga adalah
daftar putih — ditambah, sejak ronde 4, penolakan karakter asing di hulunya.

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
| `src/chat_gate.py` | Gerbang: `draft()` (baca-saja) + `simpan()` (menulis, tapi menuntut konfirmasi Deny), dengan daftar putih perintah + penolakan karakter asing. |
| `tests/test_chat_gate.py` | 143 pemeriksaan: (a) draft tidak menulis, (b) simpan tanpa Deny ditolak, (b2) penjaga negasi, (b3) daftar putih, (b4) karakter asing, (c) simpan setelah Deny berhasil, (d) asal tercatat, (+) Rin tidak punya jalur simpan. |
| `scripts/contoh_draft_chat.py` | Contoh keluaran draft NYATA lewat parser hidup. |
| `scripts/uji_hidup_chat.py` | Alur hidup: draft → tolak (termasuk bentuk bocor ronde 3 & 4) → tolak Rin → simpan Deny, di salinan. |
| `docs/CONTRACT.md` §18 | Aturan lengkap, termasuk daftar putih, aturan karakter asing, dan batas yang jujur. |
| `.gitignore` | `chat_simpan.log` (data, bukan kode). |

`draft()` memakai **parser yang sama** dengan halaman Catat
(`parser_wrap.parse_kontrak`) — tidak ada jalur parse kedua. Diuji dengan spy.

Commit: ronde 1 `bbe807c`, ronde 2 `9f6a56d` + `d26447d`, ronde 3 `ca0ec4c`,
ronde 4 di bawah ini.

---

## Bukti

### Uji otomatis

```
python3 tests/test_chat_gate.py     ->  HASIL: semua uji lulus  (143 pemeriksaan)
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
     "jangan simpan"          -> ditolak
     "tidak setuju"           -> ditolak
     "batal, jangan lanjut"   -> ditolak
     "ndak usah simpan"       -> ditolak
     "no simpan"              -> ditolak
     "udah simpan"            -> ditolak
     "simpan aja"             -> ditolak
     "❌ simpan"              -> ditolak
     "⛔ simpan"              -> ditolak
     "simpan ❌"              -> ditolak
     baris sebelum=42 sesudah=42  TIDAK bertambah
     jejak dibuat? tidak

3. Rin mencoba menyimpan sendiri
     -> bukan_deny: Perintah simpan hanya sah kalau datang dari Deny sendiri.
     baris masih 42

4. Deny memerintahkan simpan
     -> ok=True id=[113]
     baris sebelum=42 sesudah=43
     jejak asal: {"disimpan_pada": "2026-10-09T10:00:45", "pengirim": "deny",
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
  1. Rp 25.000  Pengeluaran ...  2. Rp 5.000  Pengeluaran ...  (dua transaksi, tidak digabung)

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
