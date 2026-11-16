/* Mode backend panel.
 *   'lokal' — server Python di Mac (src/server.py). Bawaan berkas ini.
 *   'gas'   — backend Google Apps Script + Google Sheet. Build Android
 *             (scripts/build-android.sh) menimpa berkas ini dengan 'gas'.
 * Tidak berisi rahasia: alamat Web App disimpan di perangkat, bukan di sini. */
window.FIN_MODE = window.FIN_MODE || 'lokal';
/* Tampilan: 'web' (bawaan) atau 'android' (bar bawah, FAB, tombol Back —
 * lihat web/android.css + web/android.js). Build Android menimpanya. */
window.FIN_UI = window.FIN_UI || 'web';
