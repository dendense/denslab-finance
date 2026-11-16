// Aplikasi Android finance.
//
// Sengaja sekecil mungkin: semua logika ada di web/ (UI) dan gas/ (backend
// Apps Script). Rust di sini hanya membuka satu jendela WebView yang memuat
// frontendDist (web/ hasil scripts/build-android.sh).
//
// Tombol/gesture Back Android: WebView Tauri mundur di riwayat halaman
// selama masih ada (history.pushState dari web/android.js), dan keluar dari
// aplikasi saat riwayat habis — itu perilaku yang dirancang android.js:
// Catat -> layar asal, tab lain -> Beranda, Beranda -> keluar.
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("gagal menjalankan aplikasi finance");
}
