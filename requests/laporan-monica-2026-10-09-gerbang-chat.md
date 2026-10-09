# Laporan: pencatatan lewat chat — draft dulu, simpan hanya atas Deny

**Dari:** monica (DATA & ANGKA)
**Tanggal:** 9 Okt 2026
**Kartu:** `t_0c4c4678`
**Status:** selesai — semua bukti di bawah dijalankan sungguhan, bukan didesain

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
| `src/chat_gate.py` | Gerbang: `draft()` (baca-saja) + `simpan()` (menulis, tapi menuntut konfirmasi Deny). |
| `tests/test_chat_gate.py` | 44 pemeriksaan: (a) draft tidak menulis, (b) simpan tanpa Deny ditolak, (c) simpan setelah Deny berhasil, (d) asal tercatat, (+) Rin tidak punya jalur simpan. |
| `scripts/contoh_draft_chat.py` | Contoh keluaran draft NYATA lewat parser hidup. |
| `docs/CONTRACT.md` §18 | Aturan lengkap, termasuk batas yang jujur. |
| `.gitignore` | `chat_simpan.log` (data, bukan kode). |

`draft()` memakai **parser yang sama** dengan halaman Catat
(`parser_wrap.parse_kontrak`) — tidak ada jalur parse kedua. Diuji dengan spy.

---

## Bukti

### Uji otomatis

```
python3 tests/test_chat_gate.py     ->  HASIL: semua uji lulus  (42 pemeriksaan)
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
yang tertinggal di folder data Deny.

### Contoh keluaran draft NYATA (parser hidup, model `deepseek-v4-1-flash`)

```
KAMU : beli makan malam 32000
  1. Rp 32.000  Pengeluaran  (akun belum jelas)  2026-10-09 (dianggap hari ini)
     catatan: beli makan malam
  Akun belum jelas. Pilih salah satu: BRI, Mandiri, Tabungan
  Belum ada yang tersimpan. Balas "simpan" untuk menyimpan.

KAMU : makan siang 25rb sama parkir 5rb
  1. Rp 25.000  Pengeluaran  ...    2. Rp 5.000  Pengeluaran  ...
  (dua transaksi, tidak digabung)

KAMU : bayar cicilan pinjaman online 500rb
  1. Rp 500.000  Bayar utang  ...   (bukan Pengeluaran)
```

### Simpan sungguhan, ke salinan

```
DRAFT   : "beli makan malam 32000 pakai BRI"   -> akun BRI, Pengeluaran, Rp 32.000
SIMPAY  : pengirim=deny, kanal=telegram, teks="simpan"
HASIL   : TERSIMPAN: 1 transaksi, id [113]
JEJAK   : {"disimpan_pada": "...", "pengirim": "deny", "kanal": "telegram",
           "waktu_konfirmasi": "...", "teks_konfirmasi": "simpan",
           "jumlah": 1, "saved_ids": [113]}
```

Dan yang **ditolak**, dengan `pengirim=rin`:

```
DITOLAK (bukan_deny): Perintah simpan hanya sah kalau datang dari Deny
sendiri. Yang mengirim ini 'rin', bukan Deny. Draft belum disimpan.
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
