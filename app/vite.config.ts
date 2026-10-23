import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base: './' WAJIB — Tauri memuat aset dari tauri://localhost, path absolut ("/assets/…") = 404.
export default defineConfig({
  plugins: [react()],
  base: "./",
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: "127.0.0.1",
  },
});
