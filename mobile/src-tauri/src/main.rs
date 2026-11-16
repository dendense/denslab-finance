// Titik masuk desktop (dipakai `tauri dev` untuk mencoba di Mac). Di Android
// yang dipakai `run()` dengan `mobile_entry_point` di lib.rs.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    finance_mobile_lib::run()
}
