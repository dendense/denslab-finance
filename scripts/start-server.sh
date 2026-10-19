#!/usr/bin/env bash
# Launcher Panel Finance (port 8791), detached (PPID=1).
#
#   bash scripts/start-server.sh            start kalau belum jalan (idempoten)
#   bash scripts/start-server.sh --restart  hentikan yang sedang dengar port, lalu start
#
# Urutan: BACKUP dulu, baru start. Backup gagal TIDAK menghentikan server —
# aplikasi yang mati karena backup gagal lebih buruk daripada jalan tanpa backup hari itu.
# Kegagalan backup masuk log, bukan hilang.
#
# Detach: python double-fork + os.setsid() (setsid(1) tidak ada di macOS).
set -u

FIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIN_DATA="${FINANCE_DATA:-$FIN_DIR/../finance-pribadi}"
FIN_ENV="$FIN_DATA/env.sh"
FIN_PORT="${FIN_PORT:-8791}"
LOG="${FINANCE_LOG:-$HOME/.hermes/cache/scratch/finance-8791.log}"

mkdir -p "$(dirname "$LOG")"
touch "$LOG" 2>/dev/null || true

log() { printf '%s launcher: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG"; }

export FINANCE_DATA="$FIN_DATA"

# ── 1. Backup (tidak fatal) ─────────────────────────────────────────────────
if bash "$FIN_DIR/scripts/backup-db.sh" >>"$LOG" 2>&1; then
  log "backup ok"
else
  log "BACKUP GAGAL — server tetap dijalankan"
fi

# ── 2. Port ─────────────────────────────────────────────────────────────────
pid_di_port() { lsof -nP -iTCP:"$FIN_PORT" -sTCP:LISTEN -t 2>/dev/null | head -1; }

PID_LAMA="$(pid_di_port)"
if [ -n "$PID_LAMA" ]; then
  if [ "${1:-}" = "--restart" ]; then
    log "restart: hentikan pid $PID_LAMA"
    kill -TERM "$PID_LAMA" 2>/dev/null || true
    i=0
    while [ "$i" -lt 20 ] && [ -n "$(pid_di_port)" ]; do sleep 0.5; i=$((i + 1)); done
    [ -n "$(pid_di_port)" ] && { log "restart GAGAL: port $FIN_PORT masih dipakai"; exit 1; }
  else
    echo "sudah jalan di port $FIN_PORT (pid $PID_LAMA)"
    log "sudah jalan (pid $PID_LAMA), tidak start kedua"
    exit 0
  fi
fi

# ── 3. Start detached ───────────────────────────────────────────────────────
# Pin ke Python yang sama dengan server yang berjalan sebelumnya (homebrew 3.11);
# /usr/bin/python3 di macOS masih 3.9 dan repo butuh 3.10+.
PY=""
for c in /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11 "$(command -v python3)"; do
  [ -x "$c" ] && PY="$c" && break
done
[ -n "$PY" ] || { log "python3 tidak ada"; exit 1; }

"$PY" - "$FIN_DIR" "$FIN_ENV" "$FIN_PORT" "$LOG" "$PY" <<'PYEOF'
import os, sys

repo, env_sh, port, log, py = sys.argv[1:6]

pid = os.fork()
if pid > 0:
    print(pid)
    os._exit(0)

os.setsid()

pid = os.fork()
if pid > 0:
    os._exit(0)

fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
os.dup2(fd, 1)
os.dup2(fd, 2)
os.dup2(os.open(os.devnull, os.O_RDONLY), 0)

# env.sh di-source oleh bash anak, bukan oleh python: isinya shell, dan nilainya
# hanya perlu ada di proses server. Isinya tidak pernah dicetak.
script = 'cd "$1" || exit 1; [ -f "$2" ] && . "$2"; exec "$4" src/server.py --port "$3"'
os.execvp("bash", ["bash", "-c", script, "bash", repo, env_sh, port, py])
PYEOF

# ── 4. Tunggu siap ──────────────────────────────────────────────────────────
i=0
while [ "$i" -lt 30 ]; do
  if curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$FIN_PORT/"; then
    log "siap di http://localhost:$FIN_PORT (pid $(pid_di_port))"
    echo "siap: http://localhost:$FIN_PORT (pid $(pid_di_port))"
    exit 0
  fi
  sleep 1
  i=$((i + 1))
done

log "GAGAL siap dalam 30s — cek $LOG"
echo "gagal siap — cek $LOG"
exit 1
