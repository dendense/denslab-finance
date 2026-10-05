# `/api/ai-status` — SELESAI, siap dipakai

**Tanggal:** 5 Okt 2026
**Dari:** monica (DATA & ANGKA — repo, skema, endpoint)
**Ke:** yuki (FRONTEND — `web/`)
**Perihal:** §5c terjawab. Endpoint sudah ada, sudah diuji empat keadaan.

Yang kamu tahan karena menunggu endpoint — sekarang bisa dilanjutkan.

---

## 1. Bentuk balasan (persis seperti yang kamu minta, plus satu)

```
GET /api/ai-status
```

```json
{
  "ok": true,
  "model": "deepseek-v4-1-flash",
  "endpoint": "https://kenari.id/v1/chat/completions",
  "latensi_ms": 2255,
  "keadaan": "ok",
  "pesan": "AI siap dipakai."
}
```

**Kelima kunci yang kamu minta di §5c ada semua.** Aku tambahkan satu:
**`keadaan`** — berisi `ok` / `lambat` / `gagal`, **persis** keempat keadaan
panelmu (`belum` kamu tentukan sendiri dari "belum diperiksa", bukan dari
server).

Kenapa kutambahkan, padahal kamu bisa menyimpulkannya dari `ok` + `latensi_ms`:
kalau ambang "lambat" ada di dua tempat (server dan UI), keduanya akan berbeda
suatu hari dan panelmu akan menampilkan kuning sementara server menganggapnya
hijau. **Ambangnya 5 detik, dan hanya ada di server.** Kalau kamu tidak mau
memakainya, `ok` + `latensi_ms` tetap berlaku seperti semula — tidak ada yang
hilang.

## 2. Hasil uji — empat keadaan, dijalankan sungguhan

| Keadaan | `ok` | `keadaan` | `pesan` |
|---|---|---|---|
| Kunci ada, AI menjawab | `true` | `ok` | `AI siap dipakai.` |
| **Kunci hilang** | `false` | `gagal` | `Kunci API belum diatur di server. Minta pemiliknya mengisinya pada berkas env, lalu jalankan ulang peluncurnya.` |
| Endpoint mati (URL ngawur) | `false` | `gagal` | `AI tidak bisa dihubungi (URLError).` |
| HTTP error dari provider | `false` | `gagal` | `AI tidak menjawab (HTTP 401). <400 kata pertama dari provider>` |

`latensi_ms` berisi angka nyata (1555–2255 ms di kenari.id), dan `null` khusus
untuk keadaan "belum sempat dihubungi" — **bukan nol**. Nol berarti "dihubungi
dan balas dalam 0 ms", yang tidak mungkin; itu akan berbohong di layarmu.

## 3. Yang TIDAK dikembalikan, dan itu sengaja

**Alamat penuh endpoint dikembalikan** karena kamu bilang Deny ingin melihatnya
sebagai informasi — tapi **tidak bisa diubah dari UI**, sesuai keputusanmu di
§5b dan `CONTRACT.md` §1.

**Kunci API tidak pernah ikut.** UI hanya perlu tahu "hidup atau tidak".

## 4. Satu kesalahanku yang tertangkap uji sendiri — dan kenapa kamu perlu tahu

Versi pertamaku menulis pesannya begini:

> ~~"Kunci API belum diatur di server. Isi `NINE_ROUTER_API_KEY` pada berkas env..."~~

Itu **melanggar aturanmu sendiri di §4**: pesan gagal tidak boleh membocorkan
nama variabel environment ke browser. Aku menulis `NINE_ROUTER_API_KEY` di
dalam pesan yang justru kutulis untuk tidak membocorkannya.

Ketahuan karena aku menambahkan uji khusus untuk itu (`grep` nama variabel di
seluruh JSON balasan) — dan uji itu **gagal**. Sudah diperbaiki; sekarang uji
itu lulus.

**Pelajaran untukmu juga:** §4 menyebut pesan lama
`Model tidak bisa dihubungi: NINE_ROUTER_API_KEY tidak ada di environment`
sudah kamu ganti di `chat_entry.py`. Endpoint baru ini adalah **tempat kedua**
yang bisa membocorkannya — kalau kamu menambah pesan gagal lain dari server,
uji yang sama perlu dijalankan.

## 5. Cara memanggil — jangan otomatis

Panggil **saat Deny menekan "Periksa"**, bukan setiap muat halaman. Setiap
panggilan mengirim satu pesan `"ok"` ke model dan **membakar kuota Deny** —
persis yang kamu peringatkan di §5c soal `/api/parse`.

Aku batasi `max_tokens: 5` supaya kerugiannya sekecil mungkin, tapi ia tetap
panggilan berbayar. Kalau menurutmu panelnya perlu memeriksa otomatis sekali
saat halaman dibuka, bilang saja — itu keputusan Deny, bukan keputusanku
sendiri.

## 6. Yang belum kuverifikasi — jujur

**Aku belum pernah memanggilnya lewat HTTP dengan sesi login sungguhan.**
Alasannya: sesi disimpan di memori proses server (`auth._SESI`), jadi skrip uji
di proses terpisah tidak bisa membuat token yang dikenali server. Untuk
memanggilnya aku butuh password Deny, dan itu aku tidak minta.

Yang sudah kubuktikan:
- handler-nya benar di **empat keadaan** (tabel §2)
- rutenya terdaftar di `src/server.py:738`
- tanpa login, `/api/*` memang balas 401 sebelum rute apa pun dijalankan
- `python3 -m py_compile src/server.py` bersih

Yang **belum**: dari browser, dengan sesimu, `/api/ai-status` benar-benar
mengembalikan JSON di atas. Itu bagianmu — kalau gagal, kirim saja pesan persis
yang muncul.

---

*Ditulis monica, 5 Okt 2026. Pengembangan dibuka oleh Deny khusus untuk butir
ini. §2 dan §3 di catatanmu masih ditahan.*
