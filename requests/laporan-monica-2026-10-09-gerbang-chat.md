# Laporan: pencatatan lewat chat — draft dulu, simpan hanya atas Deny

**Dari:** monica (DATA & ANGKA)
**Tanggal:** 9 Okt 2026
**Kartu:** `t_0c4c4678`
**Status:** selesai — semua bukti di bawah dijalankan sungguhan, bukan didesain
**Revisi:** ronde 6 (9 Okt 2026) — menutup dua temuan review ronde 5: (1) nilai
non-string dari parser (`account_hint`/`to_account_hint`/`occurred_on`) masih
melempar exception, (2) uji mengunci jumlah baris `finance.db` Deny ke angka
tetap 42 sehingga suite gagal begitu Deny mencatat. Ditambah, dari **self-review
ronde 6**, dua pintu terakhir dari kelas yang sama: `render_draft()` melempar
untuk hasil berbentuk salah, dan `waktu` konfirmasi non-teks membuat baris
ledger **TERTULIS tanpa jejak asal** (lihat bagian (b8) di bawah).

---

## Perubahan ronde 6 — temuan review ronde 5

### Cacat 1 — nilai non-string dari parser melempar exception

Review ronde 5 menemukan kelas "modul memakai KODE, bukan exception" belum
tuntas: penjaga tipe sudah dipasang untuk `flow_type` dan field konfirmasi,
tapi **belum** untuk `account_hint`/`to_account_hint` (`_cocokkan_akun()`) dan
`occurred_on` (`render_draft()`). Keluaran model yang wajar — `account_hint`
berupa angka — melempar `AttributeError` ke pemanggil dan mematikan CLI.

**Reproduksi lewat parser NYATA** (`parser_wrap.parse_kontrak`, hanya
`chat_entry.parse` di-stub untuk mensimulasikan balasan model yang cacat),
dijalankan ke salinan:

```
1. model balas account_hint = 123
   draft() -> ok=True, akun=None          (dulu: LEMPAR AttributeError)
2. transfer, to_account_hint = 7
   draft() -> ok=True, tujuan=None        (dulu: LEMPAR AttributeError)
3. occurred_on = 20261009 + assumed_date truthy
   render_draft -> "20261009 (dianggap hari ini)"  (dulu: LEMPAR TypeError)
4. CLI chat_gate.main() dengan account_hint = 123
   main() kembali kode 0                  (dulu: AttributeError dari baris 254)
```

**Perbaikan** (`src/chat_gate.py`):

- `_cocokkan_akun()`: `if isinstance(hint, str) and hint.strip():` — hint
  non-string diperlakukan **seperti hint kosong** (tidak ditebak, tapi juga
  tidak meledak).
- `render_draft()`: `occurred_on` non-string diubah jadi teks sebelum dirangkai.

Ini bukan pelonggaran gerbang: nilai non-string **tidak membuat apa pun
tersimpan** — nol baris bertambah di keempat probe. Fail-closed tetap: akun
yang tidak bisa dipastikan tetap `None` → draft menandai "(akun belum jelas)".

### Cacat 2 — uji mengunci jumlah baris Deny ke angka tetap 42

`tests/test_chat_gate.py:515` menguji `baris_deny_sebelum == 42`. Kartu meminta
properti **`sesudah == sebelum`**, bukan "sama dengan 42". Assertion absolut itu
mengunci angka yang berubah setiap kali Deny mencatat — dan itu sudah terjadi:
saat review ronde 5 menemukannya `finance.db` Deny **46** baris (kini **62**).
Akibatnya suite GAGAL di checkout bersih, dan klaim "15/15 berkas uji lulus"
tidak lagi benar.

**Perbaikan** (`tests/test_chat_gate.py`): assertion absolut `== 42` dihapus;
yang diuji adalah `sesudah == sebelum`. Ditambah satu cek bahwa tidak ada
`chat_simpan.log` tertinggal di folder data Deny.

### Uji regresi baru — bagian (b7)

4 bentuk nilai non-string dari parser (`account_hint` = `123`/`True`/`["BRI"]`,
`to_account_hint` = `7`) harus menghasilkan **draft**, dan 2 bentuk
`occurred_on` non-string harus menghasilkan **teks** — semuanya tanpa exception.

### Self-review ronde 6 — dua pintu terakhir, bagian (b8)

Saya tidak berhenti di dua temuan review. Kelas yang sama ("modul memakai
**KODE**, bukan exception") saya sisir lagi ke dua pintu yang justru paling
dekat dengan chat, dan keduanya **dijalankan**, bukan dibaca mata:

**1. `render_draft()` melempar untuk hasil berbentuk salah.** `draft()` sudah
dijaga bentuknya, tapi fungsi yang menampilkan draft ke chat belum:

```
render_draft(None)                                  -> LEMPAR AttributeError
render_draft("x")                                   -> LEMPAR AttributeError
render_draft({"ok": True, "draft": "x"})             -> LEMPAR AttributeError
render_draft({"ok": True, "draft": {"transactions": "x"}}) -> LEMPAR AttributeError
```

Sekarang semuanya mengembalikan **teks** ("Gagal mengurai: ..."). Ditambah
penjaga jalur parser: `draft()` dengan `parse_fn` yang **melempar** kini
menghasilkan kode `parser_melempar`, bukan exception ke pemanggil chat.

**2. `waktu` konfirmasi non-teks → baris TERTULIS tanpa jejak asal.** Ini yang
paling serius, karena melanggar Definisi selesai #4 ("catat asal setiap
penyimpanan"). `waktu` tidak pernah dijaga tipenya, padahal ia masuk jejak asal
lewat `json.dumps`. Pemanggil chat yang wajar mengirim `datetime`, bukan teks —
dan `json.dumps` melempar **sesudah** `db.save_transactions` berhasil:

```
waktu = datetime(2026,10,12,15,30)  -> LEMPAR TypeError  baris 62->63 TERTULIS  jejak HILANG
waktu = object()                    -> LEMPAR TypeError  baris 63->64 TERTULIS  jejak HILANG
```

Perbaikannya: jejak asal **dibangun dan dinormalkan SEBELUM** ledger tersentuh
(`_teks_aman()`: `datetime` → ISO, nilai lain → JSON/repr), jadi tidak ada lagi
langkah yang bisa gagal setelah baris masuk. Gagal menulis berkas jejak
(`OSError`) juga tidak lagi melempar — `simpan()` mengembalikan `ok: True`
dengan `jejak: null` + `jejak_error`, karena baris ledger sudah masuk dan itu
tidak boleh dilaporkan sebagai "beres".

```
waktu = datetime -> ok=True  baris +1  jejak tertulis  (sebelumnya: exception + jejak hilang)
waktu = int/list/dict/hilang -> ok=True  baris +1  jejak tertulis
jejak: waktu_konfirmasi selalu berbentuk teks
```

**Uji:** `tests/test_chat_gate.py` 165 → **197 pemeriksaan, 0 gagal**. Seluruh
**15/15** berkas uji lulus (dijalankan satu per satu lewat subprocess).
`CONTRACT.md` §18 ditambah sub-bagian "Nilai non-string dari parser ditangani,
bukan melempar" dan "Jejak asal tidak boleh hilang sesudah baris tersimpan".

**Sapuan adversarial ronde 6** (sebelum menyerahkan, bukan sesudah dikomplain):
432 kalimat penolakan turunan (`jangan/ndak/kagak/gak/no/udah/mbok/cancel/stop/
nanti/tunggu` × `simpan/catat/ya simpan/oke simpan`, dengan koma dan tanda
seru) → **0 bocor, 0 baris bertambah**. 22 kontrol perintah sah → **0 salah
ditolak**. 11 jalur yang dipanggil dengan argumen berbentuk salah →
**0 exception**. AST → fungsi penulis ledger tetap hanya `['simpan']`.

Sapuan itu menemukan satu pintu terakhir yang belum kututup di ronde ini:
`_normalisasi_perintah(123)` melempar `AttributeError` (`.lower()` dipanggil
sebelum penjaga tipe). Sudah ditutup — non-teks → `""`, dan ada regresinya.

**Data Deny:** `finance-pribadi/finance.db` = **62 baris** sebelum & sesudah
(dihitung langsung dengan sqlite3). Tidak ada `chat_simpan.log` di folder data
Deny.

---

## Perubahan ronde 5 — bentuk salah dikembalikan sebagai KODE, bukan exception

Review ronde 4 menemukan satu cacat yang **bukan** fail-open (nol baris
tersimpan), tapi tetap cacat kontrak: `periksa_konfirmasi()` memanggil `.strip()`
pada field konfirmasi tanpa penjaga tipe, jadi konfirmasi berbentuk salah
melempar `AttributeError` ke pemanggil — di luar `try/except` `simpan()`. Itu
bertabrakan dengan docstring `simpan()` sendiri ("Tidak pernah melempar
exception untuk penolakan: pemanggil harus bisa menampilkan alasannya") dan
dengan pola yang sudah dipakai `periksa_konfirmasi()` di tingkat atas
(`isinstance(konfirmasi, dict)` → `konfirmasi_rusak`).

**Reproduksi temuan ronde 4, sebelum → sesudah** (dijalankan ke salinan):

```
pengirim=1          -> CRASH AttributeError    -> kode=konfirmasi_rusak  baris 42
pengirim=['deny']   -> CRASH AttributeError    -> kode=konfirmasi_rusak  baris 42
teks=12345          -> CRASH AttributeError    -> kode=konfirmasi_rusak  baris 42
teks=['simpan']     -> CRASH AttributeError    -> kode=konfirmasi_rusak  baris 42
kanal=99            -> CRASH AttributeError    -> kode=konfirmasi_rusak  baris 42
kanal=['telegram']  -> CRASH AttributeError    -> kode=konfirmasi_rusak  baris 42
```

**Kelas yang sama di jalur draft, pada ronde yang sama.** Saya menyisir jalur
tetangga dengan prinsip yang sama, dan ketemu pintu yang sama masih terbuka:
`draft()` dengan hasil parser berbentuk salah dan `simpan()` dengan `draft_hasil`
berbentuk salah juga melempar ke pemanggil.

```
draft(parse_fn -> list/str/int/None)     -> ok=False (hasil_parser_rusak)
draft(parse_fn -> draft bukan dict)      -> ok=False (hasil_parser_rusak)
draft(parse_fn -> transactions bukan list)-> ok=False (hasil_parser_rusak)
draft(parse_fn -> tx bukan dict)         -> ok=False (hasil_parser_rusak)
simpan("x"/123)                          -> error=draft_tidak_sah
simpan({"ok":True,"draft":"x"})          -> error=draft_tidak_sah
simpan({"ok":True,"draft":{"transactions":5}}) -> error=draft_tidak_sah
simpan({"ok":True,"draft":{"transactions":["x"]}}) -> error=draft_tidak_sah
```

Yang **tidak** berubah, supaya kode lama tidak bergeser artinya: field yang
**hilang** tetap `bukan_deny` / `konfirmasi_kosong` / `kanal_kosong`; draft yang
sah-tapi-kosong tetap `draft_kosong`; draft yang hilang tetap `draft_tidak_sah`.

**Uji:** `tests/test_chat_gate.py` 143 → **165 pemeriksaan, 0 gagal**. Tambahan
bagian (b5) 6 bentuk field salah + 3 field hilang, (b6) 6 bentuk parser salah +
5 bentuk draft salah. Seluruh **15/15** berkas uji lulus. `CONTRACT.md` §18
diperbarui: baris tabel `konfirmasi_rusak` + sub-bagian "Field konfirmasi
non-string ditolak — bukan exception". Commit `2864f87`.

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
| `tests/test_chat_gate.py` | **197 pemeriksaan**: (a) draft tidak menulis, (b) simpan tanpa Deny ditolak, (b2) penjaga negasi, (b3) daftar putih, (b4) karakter asing, (b5) field konfirmasi non-string, (b6) bentuk salah dari parser/draft, (b7) nilai non-string dari parser, (b8) jalur tampil & jejak, (c) simpan setelah Deny berhasil, (d) asal tercatat, (+) Rin tidak punya jalur simpan. |
| `scripts/contoh_draft_chat.py` | Contoh keluaran draft NYATA lewat parser hidup. |
| `scripts/uji_hidup_chat.py` | Alur hidup: draft → tolak (termasuk bentuk bocor ronde 3 & 4) → tolak Rin → simpan Deny, di salinan. |
| `docs/CONTRACT.md` §18 | Aturan lengkap, termasuk daftar putih, aturan karakter asing, penjagaan nilai non-string, dan batas yang jujur. |
| `.gitignore` | `chat_simpan.log` (data, bukan kode). |

`draft()` memakai **parser yang sama** dengan halaman Catat
(`parser_wrap.parse_kontrak`) — tidak ada jalur parse kedua. Diuji dengan spy.

Commit: ronde 1 `bbe807c`, ronde 2 `9f6a56d` + `d26447d`, ronde 3 `ca0ec4c`,
ronde 4 `affa942`, ronde 5 `2864f87` + `ad5395a`, ronde 6 belum di-commit
(lihat "Status commit" di bawah).

---

## Bukti

### Uji otomatis

```
python3 tests/test_chat_gate.py     ->  HASIL: semua uji lulus  (197 pemeriksaan, 0 gagal)
seluruh 15 berkas uji di tests/     ->  15 lulus, 0 gagal
```

Termasuk, lewat AST (bukan dibaca mata):
- hanya `simpan()` yang memanggil penulisan ledger;
- `server.py` tidak mengimpor `chat_gate`; tidak ada rute `/api/chat`;
- memanggil `simpan()` dengan `pengirim: "rin"` **tetap ditolak**.

### Salinan database, bukan `finance.db` Deny

| | Jumlah baris |
|---|---|
| `finance-pribadi/finance.db` SEBELUM | 62 |
| `finance-pribadi/finance.db` SESUDAH | **62** |

Angka ini adalah **keadaan Deny saat uji dijalankan**, bukan angka yang diuji —
assertion absolut `== 42` sudah dihapus (temuan review ronde 5, cacat 2). Yang
diuji adalah properti `sesudah == sebelum`.

Semua penulisan uji terjadi di salinan `/tmp`. Tidak ada `chat_simpan.log`
yang tertinggal di folder data Deny (diperiksa langsung).

### Alur hidup (`scripts/uji_hidup_chat.py`, parser hidup, model `deepseek-v4-1-flash`)

Dijalankan ulang 12 Okt 2026 setelah perbaikan ronde 6:

```
1. DRAFT "beli makan malam 32000 pakai BRI"
     1. Rp 32.000  Pengeluaran  BRI  2026-10-12 (dianggap hari ini)
        catatan: beli makan malam
     baris sebelum=62 sesudah=62  TIDAK bertambah

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
     baris sebelum=62 sesudah=62  TIDAK bertambah
     jejak dibuat? tidak

3. Rin mencoba menyimpan sendiri
     -> bukan_deny: Perintah simpan hanya sah kalau datang dari Deny sendiri.
     baris masih 62

4. Deny memerintahkan simpan
     -> ok=True id=[133]
     baris sebelum=62 sesudah=63
     jejak asal: {"disimpan_pada": "2026-10-12T15:35:50", "pengirim": "deny",
                  "kanal": "telegram", "waktu_konfirmasi": "2026-10-09T21:30:00",
                  "teks_konfirmasi": "simpan", "jumlah": 1, "saved_ids": [133]}
```

### Contoh keluaran draft NYATA (parser hidup, `scripts/contoh_draft_chat.py`)

Dijalankan ulang 12 Okt 2026 (parser hidup, `deepseek-v4-1-flash`, salinan):

```
KAMU : beli makan malam 32000
  1. Rp 32.000  Pengeluaran  (akun belum jelas)  2026-10-12 (dianggap hari ini)
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

## Status commit — sengaja NOL commit di ronde ini

Ronde 6 **tidak di-commit**, atas perintah Steve (orkestrator, komentar kartu
12 Okt 2026): kartu `t_451ec8fa` (yuki) bekerja di working tree yang **sama**
(`~/Documents/AI/finance`), dan satu `git commit -a` akan menerbitkan
pekerjaannya sebagai milikku. Jadi seluruh perubahan ronde 6 ada di working
tree, belum di HEAD.

Berkas yang saya sentuh di ronde 6 — semuanya di wilayah yang Steve tetapkan
milikku:

```
src/chat_gate.py        (perbaikan + regresi)
tests/test_chat_gate.py (bagian (b7)/(b8))
docs/CONTRACT.md        (§18)
requests/laporan-monica-2026-10-09-gerbang-chat.md
```

`web/**` **tidak disentuh** (itu milik yuki). Perubahan `web/app.js`,
`web/index.html`, `web/src.css`, `web/tailwind.css` yang terlihat di
`git status` bukan milikku.

Yang belum di-commit siapa pun, dan bukan milikku: `docs/LIST-HUTANG.md`
(untracked, bukan berkas yang saya buat atau sentuh).

---

## Sisa yang belum dikerjakan (butuh keputusan, bukan kode)

Jalur ini **belum terhubung ke chat mana pun.** Yang ada sekarang adalah
gerbangnya, sudah teruji. Menyambungkannya ke Telegram berarti memberi Rin
kemampuan memanggil `draft()` (aman, baca-saja) — tapi Deny sendiri yang harus
memasukkan `konfirmasi` dengan `pengirim: "deny"`. Belum ada yang memutuskan
bentuk sambungan itu, dan itu di luar kartu ini.
