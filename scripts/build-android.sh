#!/usr/bin/env bash
# Bangun APK Android finance.
#
#   bash scripts/build-android.sh            # APK debug (langsung bisa dipasang)
#   bash scripts/build-android.sh --rilis    # APK rilis (butuh keystore, lihat docs/ANDROID-GSHEET.md)
#
# Yang dilakukan:
#   1. Salin web/ -> mobile/dist/, lalu timpa config.js dengan
#      FIN_MODE='gas' + FIN_UI='android'. web/ sendiri TIDAK diubah, jadi
#      panel di Mac tetap mode lokal.
#   2. Salin ikon dari app/src-tauri/icons.
#   3. `tauri android init` (sekali) lalu `tauri android build --apk`.
#
# Prasyarat (diperiksa di bawah): Android Studio/SDK + NDK, JDK 17+, rustup
# dengan target Android, pnpm.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MOBILE="$ROOT/mobile"
RILIS=0
[ "${1:-}" = "--rilis" ] && RILIS=1

kurang=()
command -v pnpm >/dev/null || kurang+=("pnpm (brew install pnpm)")
command -v rustup >/dev/null || kurang+=("rustup (https://rustup.rs) — cargo dari Homebrew tidak bisa menambah target Android")
[ -n "${ANDROID_HOME:-}" ] && [ -d "${ANDROID_HOME}" ] || kurang+=("ANDROID_HOME (Android Studio > SDK Manager; biasanya ~/Library/Android/sdk)")
[ -n "${NDK_HOME:-}" ] && [ -d "${NDK_HOME}" ] || kurang+=("NDK_HOME (SDK Manager > SDK Tools > NDK; contoh \$ANDROID_HOME/ndk/<versi>)")
[ -n "${JAVA_HOME:-}" ] && [ -d "${JAVA_HOME}" ] || kurang+=("JAVA_HOME (JDK 17+; bisa pakai '/Applications/Android Studio.app/Contents/jbr/Contents/Home')")
if [ ${#kurang[@]} -gt 0 ]; then
  echo "Belum bisa build. Yang kurang:" >&2
  for k in "${kurang[@]}"; do echo "  - $k" >&2; done
  echo "Panduan lengkap: docs/ANDROID-GSHEET.md §Build APK" >&2
  exit 1
fi
rustup target add aarch64-linux-android armv7-linux-androideabi x86_64-linux-android i686-linux-android >/dev/null

echo "→ Menyiapkan aset web (mode gas + tampilan android)"
rm -rf "$MOBILE/dist"
mkdir -p "$MOBILE/dist"
for f in index.html login.html app.js backend.js android.js android.css tailwind.css; do
  cp "$ROOT/web/$f" "$MOBILE/dist/$f"
done
cat > "$MOBILE/dist/config.js" <<'EOF'
/* Dibuat scripts/build-android.sh — jangan disunting di sini. */
window.FIN_MODE = 'gas';
window.FIN_UI = 'android';
EOF

echo "→ Menyalin ikon"
rm -rf "$MOBILE/src-tauri/icons"
cp -R "$ROOT/app/src-tauri/icons" "$MOBILE/src-tauri/icons"

cd "$MOBILE"
pnpm install --silent
if [ ! -d src-tauri/gen/android ]; then
  echo "→ tauri android init (sekali saja)"
  pnpm tauri android init
fi

if [ $RILIS -eq 1 ]; then
  pnpm tauri android build --apk
  echo "APK rilis: $MOBILE/src-tauri/gen/android/app/build/outputs/apk/universal/release/"
else
  pnpm tauri android build --apk --debug
  echo "APK debug: $MOBILE/src-tauri/gen/android/app/build/outputs/apk/universal/debug/"
fi
