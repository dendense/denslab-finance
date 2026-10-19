#!/usr/bin/env bash
# Backup finance.db — sqlite3 .backup (BUKAN cp: cp pada DB hidup bisa rusak),
# verifikasi integrity_check, rotasi simpan N terakhir.
#
# Pakai:  bash scripts/backup-db.sh
# Env:    FINANCE_DATA (folder data), FINANCE_BACKUP_DIR, FINANCE_BACKUP_KEEP
# Keluar: 0 = backup sah tersimpan · 1 = gagal (tidak ada berkas rusak tertinggal)
set -uo pipefail

DB="${FINANCE_DB:-${FINANCE_DATA:-$HOME/Documents/AI/finance-pribadi}/finance.db}"
DEST="${FINANCE_BACKUP_DIR:-$HOME/Documents/AI/finance-backups}"
KEEP="${FINANCE_BACKUP_KEEP:-30}"

[ -f "$DB" ] || { echo "backup: DB tidak ada: $DB" >&2; exit 1; }

mkdir -p "$DEST" || exit 1
chmod 700 "$DEST" || exit 1

TS="$(date +%Y%m%d-%H%M%S)"
OUT="$DEST/finance-$TS.db"
[ -e "$OUT" ] && { echo "backup: sudah ada berkas untuk detik ini: $OUT" >&2; exit 1; }

if ! sqlite3 "$DB" ".backup '$OUT'"; then
  rm -f -- "$OUT"
  echo "backup: sqlite3 .backup GAGAL" >&2
  exit 1
fi

# Verifikasi isi salinan, bukan keberadaan berkas.
CHECK="$(sqlite3 "$OUT" "PRAGMA integrity_check;" 2>&1)"
if [ "$CHECK" != "ok" ]; then
  rm -f -- "$OUT"
  echo "backup: integrity_check BUKAN ok — salinan dibuang: $CHECK" >&2
  exit 1
fi

# Jumlah baris harus sama; menangkap salinan terpotong yang lolos integrity_check.
ASLI="$(sqlite3 "$DB" "SELECT COUNT(*) FROM transactions;" 2>/dev/null || true)"
SALIN="$(sqlite3 "$OUT" "SELECT COUNT(*) FROM transactions;" 2>/dev/null || true)"
if [ -n "$ASLI" ] && [ "$ASLI" != "$SALIN" ]; then
  rm -f -- "$OUT"
  echo "backup: jumlah transactions beda (asli=$ASLI salin=$SALIN) — salinan dibuang" >&2
  exit 1
fi

chmod 600 "$OUT" || { rm -f -- "$OUT"; exit 1; }

# Rotasi: simpan KEEP terakhir. Nama berstempel waktu -> urutan sort = urutan umur.
TOTAL="$(find "$DEST" -maxdepth 1 -type f -name 'finance-*.db' | wc -l | tr -d ' ')"
if [ "$TOTAL" -gt "$KEEP" ]; then
  # BSD head tidak menerima `-n -N`, jadi hitung jumlah yang dibuang lalu ambil yang tertua.
  find "$DEST" -maxdepth 1 -type f -name 'finance-*.db' | sort | head -n "$((TOTAL - KEEP))" |
    while IFS= read -r f; do rm -f -- "$f"; done
fi

echo "backup: ok $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes, transactions=$SALIN)"
