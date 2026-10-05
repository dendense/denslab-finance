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
sudah dikerjakan bercampur dengan yang belum.

**Aturan yang berlaku sejak 4 Okt 2026:** sebelum berkasnya dibuang,
**pindahkan dulu isinya ke dokumen yang berlaku** (`docs/CONTRACT.md`,
`docs/UI-MOBILE.md`, `docs/SCHEMA.md`, `README.md`, atau `web/README.md`) —
lalu **hapus berkasnya**. Surat tidak perlu diarsipkan.

Alasannya: surat hanya dibaca orang yang mencarinya, sementara aturan harus
dibaca orang yang **butuh mengetahuinya tanpa tahu harus mencari ke mana**.
Aturan yang hidupnya cuma di surat akan hilang saat suratnya dibuang — dan
orang berikutnya mengulang kesalahannya.

**Cara memeriksa sebelum menghapus** — pastikan setiap aturan kunci sudah ada
di dokumen:

```bash
cd ~/Documents/AI/finance
for k in sisa_bebas tailwind.css FINANCE_DATA finance-pribadi net_worth_akhir; do
  c=$(grep -l "$k" docs/*.md README.md web/README.md 2>/dev/null | tr '\n' ' ')
  printf "  %-18s -> %s\n" "$k" "${c:-TIDAK ADA}"
done
```

Kalau ada yang "TIDAK ADA", **pindahkan dulu** — jangan hapus suratnya.

Surat yang **ditolak atau ditahan** tinggal di sini **dengan catatan alasannya
ditambahkan di bagian atas** — supaya tidak ada yang mengajukannya ulang tanpa
tahu kenapa dulu tidak dikerjakan.

## Isi folder ini (per 4 Okt 2026)

```
CATATAN-BELUM-SELESAI.md   daftar pekerjaan tertunda — hidup, terus diperbarui
README.md                  berkas ini
yuki-ke-monica-*.md        surat yang masih menunggu jawaban
```

Folder `docs/selesai/` **sudah dihapus** — isinya dilebur ke dokumen yang
berlaku. Jangan buat lagi.

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
