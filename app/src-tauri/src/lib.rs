// Sidecar Python untuk Finance.app.
//
// Aturan yang menentukan bentuk kode ini (DESIGN_NEW.md §7, §9C, §10, §10A, §11):
// - Sidecar dipanggil LANGSUNG (`python3 src/server.py --port N`), bukan lewat
//   `scripts/start-server.sh`, karena launcher itu daemonize (double-fork + setsid) sehingga
//   proses Python lepas dari Rust dan tidak bisa dimatikan saat app ditutup.
// - Port dipilih Rust (bind :0 → baca port → drop listener) supaya tidak ada port hardcode.
// - Jendela dibuat `visible: false`, ditampilkan setelah `GET /api/auth` 200 DAN ≥400 ms.
// - Saat app keluar: SIGTERM ke PID anak, tunggu ≤3 s, lalu SIGKILL ke PID itu saja.
use std::collections::VecDeque;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

const SIAP_TIMEOUT: Duration = Duration::from_secs(10);
const POLL: Duration = Duration::from_millis(100);
const SPLASH_MIN: Duration = Duration::from_millis(400);
const MATI_GRACE: Duration = Duration::from_secs(3);
const LOG_TAIL: usize = 20;

struct Sidecar {
    anak: Child,
    pid: u32,
}

type Slot = Arc<Mutex<Option<Sidecar>>>;

fn home() -> PathBuf {
    PathBuf::from(std::env::var("HOME").unwrap_or_default())
}

fn config() -> Option<serde_json::Value> {
    let p = home().join("Library/Application Support/Finance/config.json");
    serde_json::from_str(&std::fs::read_to_string(p).ok()?).ok()
}

fn field_config(nama: &str) -> Option<String> {
    config()?.get(nama)?.as_str().map(|s| s.to_string())
}

fn repo_valid(p: &Path) -> bool {
    p.join("src/server.py").is_file()
        && p.join("web/index.html").is_file()
        && p.join("src/schema.sql").is_file()
}

/// §10: config `repo_path` → `~/Documents/AI/finance`. Pemilih folder (§9A) belum ada di kartu ini.
fn repo_path() -> Option<PathBuf> {
    if let Some(p) = field_config("repo_path") {
        let p = PathBuf::from(p);
        if repo_valid(&p) {
            return Some(p);
        }
    }
    let p = home().join("Documents/AI/finance");
    if repo_valid(&p) {
        return Some(p);
    }
    None
}

/// Versi mayor.minor dari `<py> --version`. None kalau tidak bisa dijalankan.
fn versi(py: &Path) -> Option<(u32, u32)> {
    let out = Command::new(py).arg("--version").output().ok()?;
    let teks =
        String::from_utf8_lossy(&out.stdout).to_string() + &String::from_utf8_lossy(&out.stderr);
    let angka = teks
        .split_whitespace()
        .find(|t| t.chars().next().is_some_and(|c| c.is_ascii_digit()))?;
    let mut it = angka.split('.');
    let mayor = it.next()?.parse().ok()?;
    let minor = it.next()?.parse().ok()?;
    Some((mayor, minor))
}

fn python_ok(py: &Path) -> Option<PathBuf> {
    match versi(py) {
        Some((3, m)) if m >= 9 => Some(py.to_path_buf()),
        _ => None,
    }
}

/// §10A: `FINANCE_PYTHON` / config `python_path` → `/opt/homebrew/bin/python3.11` → venv repo → `python3` PATH.
fn python_path(repo: &Path) -> Option<PathBuf> {
    let mut kandidat: Vec<PathBuf> = Vec::new();
    if let Ok(p) = std::env::var("FINANCE_PYTHON") {
        kandidat.push(PathBuf::from(p));
    }
    if let Some(p) = field_config("python_path") {
        kandidat.push(PathBuf::from(p));
    }
    kandidat.push(PathBuf::from("/opt/homebrew/bin/python3.11"));
    kandidat.push(repo.join(".venv/bin/python3"));
    if let Ok(path) = std::env::var("PATH") {
        for dir in path.split(':') {
            kandidat.push(PathBuf::from(dir).join("python3"));
        }
    }
    kandidat.iter().find_map(|p| python_ok(p))
}

fn port_bebas() -> std::io::Result<u16> {
    let l = TcpListener::bind("127.0.0.1:0")?;
    let p = l.local_addr()?.port();
    drop(l);
    Ok(p)
}

/// `GET /api/auth` → 200. Request HTTP mentah supaya tidak menambah dependency HTTP client.
fn siap_http(port: u16) -> bool {
    let alamat = std::net::SocketAddr::from(([127, 0, 0, 1], port));
    let Ok(mut s) = TcpStream::connect_timeout(&alamat, Duration::from_millis(300)) else {
        return false;
    };
    let _ = s.set_read_timeout(Some(Duration::from_millis(700)));
    let req = "GET /api/auth HTTP/1.0\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n";
    if s.write_all(req.as_bytes()).is_err() {
        return false;
    }
    let mut buf = [0u8; 12];
    match s.read_exact(&mut buf) {
        Ok(()) => &buf == b"HTTP/1.0 200" || &buf == b"HTTP/1.1 200",
        Err(_) => false,
    }
}

fn log_tail(log: &Arc<Mutex<VecDeque<String>>>) -> String {
    log.lock()
        .map(|l| l.iter().cloned().collect::<Vec<_>>().join("\n"))
        .unwrap_or_default()
}

fn rekam(log: &Arc<Mutex<VecDeque<String>>>, baris: String) {
    if let Ok(mut l) = log.lock() {
        if l.len() == LOG_TAIL {
            l.pop_front();
        }
        l.push_back(baris.clone());
    }
    let dir = home().join("Library/Logs/Finance");
    let _ = std::fs::create_dir_all(&dir);
    // ponytail: tanpa rotasi 1 MB/3 berkas (§9A). Tambah kalau log mulai tumbuh.
    if let Ok(mut f) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(dir.join("sidecar.log"))
    {
        let _ = writeln!(f, "{baris}");
    }
}

fn esc(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

/// §9A: jangan jendela kosong — sebut perintah, port, dan 20 baris log terakhir.
fn tampilkan_error(
    win: &WebviewWindow,
    judul: &str,
    penjelasan: &str,
    perintah: &str,
    port: &str,
    log: &str,
) {
    let html = format!(
        "<!doctype html><html lang=\"id\"><meta charset=\"utf-8\"><title>Finance</title>\
         <body style=\"font:15px -apple-system;margin:48px;max-width:560px\">\
         <h1 style=\"font-size:20px;font-weight:600\">{judul}</h1>\
         <p>{penjelasan}</p>\
         <p style=\"font:12px ui-monospace,monospace\">Perintah: {perintah}<br>Port: {port}</p>\
         <p style=\"font:12px ui-monospace,monospace;white-space:pre-wrap;max-height:40vh;\
         overflow:auto\" aria-label=\"Log server\">{log}</p></body></html>",
        judul = esc(judul),
        penjelasan = esc(penjelasan),
        perintah = esc(perintah),
        port = esc(port),
        log = esc(log),
    );
    let js = format!(
        "document.open();document.write({});document.close();",
        serde_json::to_string(&html).unwrap_or_else(|_| "\"\"".into())
    );
    let _ = win.eval(&js);
    let _ = win.show();
}

fn nyalakan(win: WebviewWindow, slot: Slot) {
    let mulai = Instant::now();

    let Some(repo) = repo_path() else {
        tampilkan_error(
            &win,
            "Folder finance tidak valid",
            "Berkas src/server.py, web/index.html, atau src/schema.sql tidak ditemukan. Pilih folder repo finance.",
            "-",
            "-",
            "",
        );
        return;
    };
    let Some(py) = python_path(&repo) else {
        tampilkan_error(
            &win,
            "Python tidak ditemukan",
            "Finance butuh Python 3.9 atau lebih baru untuk menyalakan server. Lokasi yang dicari: FINANCE_PYTHON, config python_path, /opt/homebrew/bin/python3.11, .venv/bin/python3, python3 di PATH.",
            "-",
            "-",
            "",
        );
        return;
    };
    let port = match port_bebas() {
        Ok(p) => p,
        Err(e) => {
            tampilkan_error(
                &win,
                "Port tidak tersedia",
                &format!("Gagal memilih port bebas: {e}"),
                "-",
                "-",
                "",
            );
            return;
        }
    };
    let perintah = format!("{} src/server.py --port {}", py.display(), port);

    let log: Arc<Mutex<VecDeque<String>>> = Arc::new(Mutex::new(VecDeque::new()));
    let mut anak = match Command::new(&py)
        .arg("src/server.py")
        .arg("--port")
        .arg(port.to_string())
        .current_dir(&repo)
        .env("PYTHONUNBUFFERED", "1")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => {
            tampilkan_error(
                &win,
                "Server tidak bisa dinyalakan",
                &format!("Gagal menjalankan {perintah}: {e}"),
                &perintah,
                &port.to_string(),
                "",
            );
            return;
        }
    };
    let pid = anak.id();
    for pipa in [
        anak.stdout.take().map(|s| Box::new(s) as Box<dyn Read + Send>),
        anak.stderr.take().map(|s| Box::new(s) as Box<dyn Read + Send>),
    ]
    .into_iter()
    .flatten()
    {
        let log = log.clone();
        thread::spawn(move || {
            for baris in BufReader::new(pipa).lines().map_while(Result::ok) {
                rekam(&log, baris);
            }
        });
    }
    *slot.lock().unwrap() = Some(Sidecar { anak, pid });

    // Poll, bukan sleep: cold start 0,2 s di mesin hangat, 2–3 s di disk dingin.
    let mut hasil = Err("tidak menjawab".to_string());
    while mulai.elapsed() < SIAP_TIMEOUT {
        if siap_http(port) {
            hasil = Ok(());
            break;
        }
        let keluar = slot
            .lock()
            .unwrap()
            .as_mut()
            .and_then(|s| s.anak.try_wait().ok().flatten());
        if let Some(status) = keluar {
            hasil = Err(format!(
                "Server berhenti saat dinyalakan (kode {}).",
                status.code().unwrap_or(-1)
            ));
            break;
        }
        thread::sleep(POLL);
    }

    if let Err(pesan) = hasil {
        tampilkan_error(
            &win,
            "Server tidak siap",
            &format!(
                "{pesan} Server tidak menjawab dalam {} detik. Lihat log di bawah.",
                SIAP_TIMEOUT.as_secs()
            ),
            &perintah,
            &port.to_string(),
            &log_tail(&log),
        );
        return;
    }

    let sisa = SPLASH_MIN.saturating_sub(mulai.elapsed());
    if !sisa.is_zero() {
        thread::sleep(sisa);
    }
    if let Ok(url) = format!("http://127.0.0.1:{port}/").parse() {
        let _ = win.navigate(url);
    }
    let _ = win.show();
    eprintln!(
        "sidecar siap: pid {pid}, port {port}, {:.3} s",
        mulai.elapsed().as_secs_f64()
    );
}

/// SIGTERM dulu (Python punya cleanup; SIGKILL bisa meninggalkan `-journal` SQLite), tunggu ≤3 s.
fn matikan(slot: &Slot) {
    let Some(mut s) = slot.lock().unwrap().take() else {
        return;
    };
    let _ = Command::new("/bin/kill")
        .arg("-TERM")
        .arg(s.pid.to_string())
        .status();
    let mulai = Instant::now();
    loop {
        match s.anak.try_wait() {
            Ok(Some(status)) => {
                eprintln!("sidecar {pid} mati (SIGTERM, {status})", pid = s.pid);
                return;
            }
            Ok(None) => {}
            Err(e) => {
                eprintln!("sidecar {}: try_wait gagal: {e}", s.pid);
                return;
            }
        }
        if mulai.elapsed() > MATI_GRACE {
            eprintln!("sidecar {}: SIGTERM tidak berefek, SIGKILL", s.pid);
            let _ = s.anak.kill();
            let _ = s.anak.wait();
            return;
        }
        thread::sleep(Duration::from_millis(50));
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let slot: Slot = Arc::new(Mutex::new(None));
    let slot_setup = slot.clone();
    let slot_exit = slot.clone();

    let app = tauri::Builder::default()
        .setup(move |app| {
            // Jendela tampil belakangan: URL-nya bergantung pada port yang dipilih runtime.
            let win = WebviewWindowBuilder::new(
                app,
                "main",
                WebviewUrl::External("about:blank".parse()?),
            )
            .title("Finance")
            .inner_size(1100.0, 760.0)
            .visible(false)
            .build()?;
            let slot = slot_setup.clone();
            thread::spawn(move || nyalakan(win, slot));
            Ok(())
        })
        .on_window_event(|window, event| {
            // Satu jendela = satu server (§7): menutup jendela = keluar dari app.
            if matches!(event, tauri::WindowEvent::CloseRequested { .. }) {
                window.app_handle().exit(0);
            }
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application");

    app.run(move |_handle, event| {
        if let RunEvent::Exit = event {
            matikan(&slot_exit);
        }
    });
}
