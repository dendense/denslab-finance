# requests/ — permintaan antar-agent

Folder ini **hanya untuk permintaan yang belum selesai** — satu agent meminta
sesuatu ke agent lain, dan jawabannya bukan sesuatu yang bisa dikerjakan sendiri.

## Penamaan

```
<pengirim>-ke-<penerima>-<tanggal>-<topik>.md
```

Contoh:

```
yuki-ke-monica-2026-10-03-akun-tulis.md
monica-ke-yuki-2026-10-05-tren-tambahan.md
```

Tanggal pakai format `YYYY-MM-DD` supaya urut sendiri saat di-`ls`.
Topik: 1–3 kata, huruf kecil, dipisah tanda hubung.

## Aturan isi

Setiap berkas wajib punya di bagian atas:

- **Dari** / **Ke** — agent mana, beserta bidangnya
- **Tanggal**
- **Perihal** — satu baris

Dan wajib memuat **pertanyaan yang bisa dijawab**, bukan sekadar keluhan.
Permintaan yang tidak bisa dijawab penerimanya akan mengendap di sini.

## Kalau sudah selesai

**Pindahkan berkasnya keluar dari folder ini** — jangan biarkan permintaan yang
sudah dikerjakan bercampur dengan yang belum. Kalau sudah dijawab, ringkasannya
masuk ke dokumen yang berlaku (`docs/CONTRACT.md`, `docs/SCHEMA.md`, atau `HANDOFF-*.md`),
lalu berkasnya dihapus dari sini.

Kalau ditolak atau ditahan, tinggal di sini **dengan catatan alasannya
ditambahkan di bagian atas** — supaya tidak ada yang mengajukannya ulang tanpa
tahu kenapa dulu tidak dikerjakan.

## Yang BUKAN isi folder ini

| Berkas | Tempatnya |
|---|---|
| Handoff antar-agent (`HANDOFF-*.md`) | folder induk — itu dokumen acuan, bukan permintaan |
| Kontrak data (`docs/CONTRACT.md`) | folder induk |
| Skema (`docs/SCHEMA.md`) | folder induk |
| Rencana & pembagian peran (`docs/PLAN.md`) | folder induk |
| Aturan tampilan (`docs/UI-MOBILE.md`) | folder induk |

Folder induk adalah **dokumen yang berlaku** (kebenaran sekarang). Folder ini
adalah **percakapan yang masih berjalan** (belum tuntas).

---

*Dibuat yuki, 3 Okt 2026.*
