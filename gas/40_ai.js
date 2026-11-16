/**
 * Port src/model_config.py + chat_entry.py + parser_wrap.py + monthly_analysis.py
 * + api_ai_status.
 *
 * Kunci API disimpan di Script Properties (KENARI_API_KEY), BUKAN di HP:
 * aplikasi Android hanya tahu alamat Web App, tidak pernah melihat kuncinya.
 *
 * Script Properties yang dibaca:
 *   KENARI_API_KEY   wajib untuk catat pintar & narasi analisa
 *   KENARI_BASE      opsional; bawaan https://kenari.id/v1/chat/completions
 *   MODEL            opsional; bawaan sama dengan model_config.MODEL
 *   MODEL_CADANGAN   opsional; bawaan sama dengan model_config.MODEL_CADANGAN
 */
var MODEL_BAWAAN = 'qwen3-8-27b:free';
var MODEL_CADANGAN_BAWAAN = 'llama-3-3-70b-instruct:free';
var BASE_BAWAAN = 'https://kenari.id/v1/chat/completions';

function _prop(nama) {
  if (typeof KONFIG_UJI !== 'undefined' && KONFIG_UJI) return KONFIG_UJI[nama] || null;
  return PropertiesService.getScriptProperties().getProperty(nama);
}

function konfigAI() {
  var url = String(_prop('KENARI_BASE') || '').trim().replace(/\/+$/, '');
  if (!url) url = BASE_BAWAAN;
  else if (/\/chat\/completions$/.test(url)) { /* apa adanya */ }
  else if (/\/v1$/.test(url)) url = url + '/chat/completions';
  return { key: String(_prop('KENARI_API_KEY') || '').trim(), base: url,
    model: _prop('MODEL') || MODEL_BAWAAN, cadangan: _prop('MODEL_CADANGAN') || MODEL_CADANGAN_BAWAAN };
}

/** POST JSON. Mengembalikan {code, text}. Uji menimpa `HTTP_UJI`. */
function httpPost(url, body, key) {
  if (typeof HTTP_UJI !== 'undefined' && HTTP_UJI) return HTTP_UJI(url, body, key);
  var r = UrlFetchApp.fetch(url, { method: 'post', contentType: 'application/json',
    payload: JSON.stringify(body), headers: { Authorization: 'Bearer ' + key },
    muteHttpExceptions: true });
  return { code: r.getResponseCode(), text: r.getContentText('UTF-8') };
}

/** Seperti urlopen: HTTP bukan 2xx = exception. */
function _panggil(url, body, key) {
  var r = httpPost(url, body, key);
  if (r.code < 200 || r.code >= 300) {
    var e = new Error('HTTP Error ' + r.code + ': ' + String(r.text || '').slice(0, 200));
    e.http = r.code; e.detail = String(r.text || '').slice(0, 200);
    throw e;
  }
  return r.text;
}

/** Gabungkan potongan SSE `data: {...}` jadi teks utuh. */
function _gabungSSE(raw) {
  var chunks = [];
  var baris = String(raw).split(/\r?\n/);
  for (var i = 0; i < baris.length; i++) {
    var line = baris[i].trim();
    if (line.indexOf('data:') !== 0) continue;
    var p = line.slice(5).trim();
    if (p === '[DONE]') break;
    try {
      var d = JSON.parse(p);
      var ch = d.choices || [];
      if (ch.length && (ch[0].delta || {}).content) chunks.push(ch[0].delta.content);
    } catch (e) { /* lewati */ }
  }
  return chunks.join('').trim().split('```json').join('').split('```').join('').trim();
}

// ── chat_entry.py ───────────────────────────────────────────────────────────
var KATEGORI_PARSER = ['Makan', 'Transport', 'Belanja', 'Hiburan', 'Tagihan',
  'Kesehatan', 'Pendidikan', 'Gaji', 'Lainnya'];

function _sysParser() {
  return 'Kamu parser transaksi keuangan berbahasa Indonesia. Balas HANYA JSON valid, tanpa penjelasan, tanpa markdown.\n\n' +
    'Format:\n{"transactions": [\n  {"direction": "in"|"out"|"transfer", "amount": number,\n' +
    '   "category": string|null, "note": string,\n   "occurred_on": "YYYY-MM-DD"|null, "account_hint": string|null,\n' +
    '   "to_account_hint": string|null, "assumed_date": bool}\n], "question": string|null}\n\n' +
    'Aturan WAJIB:\n' +
    '- Kalau satu pesan berisi LEBIH DARI SATU transaksi, keluarkan SEMUA sebagai elemen\n' +
    '  terpisah di "transactions". Contoh: "makan siang 25rb sama parkir 5rb" ->\n' +
    '  DUA transaksi: 25000 Makan, dan 5000 Transport. Jangan pernah gabungkan jadi satu,\n' +
    '  dan jangan pernah buang salah satunya.\n' +
    '- amount SELALU positif. Arah disimpan di "direction", bukan di tanda angka.\n' +
    '- "transfer"/"pindah"/"masukin ke tabungan" -> "transfer".\n' +
    '- Untuk "transfer": "account_hint" = akun ASAL, "to_account_hint" = akun TUJUAN.\n' +
    '  JANGAN menggabungkan dua akun dalam satu field ("Mandiri -> Tabungan" SALAH).\n' +
    '  Kalau hanya tujuan yang disebut ("pindah dana 100000 ke Tabungan"), isi\n' +
    '  "to_account_hint" dan biarkan "account_hint" null. Jangan mengarang akun asal.\n' +
    '- "terima"/"gaji"/"masuk"/"dapat"/"bonus"/"dibayar" -> "in". Sisanya "out".\n' +
    '- category HARUS salah satu dari: ' + KATEGORI_PARSER.join(', ') + '\n' +
    '  Category adalah JENIS transaksi, BUKAN arah. Untuk direction "transfer", category = null.\n' +
    '- "occurred_on": kalau user tidak menyebut tanggal, isi null dan set "assumed_date": true.\n' +
    '  Kalau menyebut ("kemarin", "tadi pagi", "3 hari lalu"), hitung dari hari ini = ' + hariIni() + '.\n' +
    '- "note": deskripsi singkat dari user, jangan tambah sendiri.\n' +
    '- Kalau pesan BUKAN transaksi (sapaan, pertanyaan), transactions = [] dan isi "question".\n' +
    '- Kalau ada angka tapi arah/kategori benar-benar tidak bisa ditentukan, tetap keluarkan\n' +
    '  transaksinya dengan category "Lainnya" dan sebutkan keraguanmu di "note".';
}

function _muatJson(txt) {
  function coba(s) {
    s = s.trim();
    if (!(s.charAt(0) === '{' && s.charAt(s.length - 1) === '}')) return null;
    try { return JSON.parse(s); } catch (e) { return null; }
  }
  var d = coba(txt);
  if (d !== null) return d;
  var a = txt.indexOf('{'), b = txt.lastIndexOf('}');
  if (a !== -1 && b > a && b - a <= 20000) return coba(txt.slice(a, b + 1));
  return null;
}

function chat_entry_parse(text) {
  var k = konfigAI();
  if (!k.key) throw new Error('Kunci API belum diatur (Script Properties KENARI_API_KEY)');
  var body = { model: k.model, max_tokens: 1200, stream: true, temperature: 0,
    messages: [{ role: 'system', content: _sysParser() }, { role: 'user', content: text }] };
  var raw;
  try { raw = _panggil(k.base, body, k.key); }
  catch (e) {
    if (k.cadangan && k.cadangan !== k.model) {
      body.model = k.cadangan;
      try { raw = _panggil(k.base, body, k.key); }
      catch (e2) {
        throw new Error('Model utama dan cadangan dua-duanya gagal. Utama: ' + e.message +
          ' · Cadangan: ' + e2.message);
      }
    } else throw e;
  }
  var txt = _gabungSSE(raw);
  if (!txt) return { transactions: [], question: 'Model tidak membalas (content kosong).' };
  var data = _muatJson(txt);
  if (data === null) {
    console.log('[chat_entry] respon model bukan JSON (' + txt.length + ' karakter). Potongan: ' +
      txt.slice(0, 300));
    return { transactions: [], question: 'Catat pintar tidak bisa memahami pesanmu sekarang — ' +
      'model menjawab di luar format. Coba tulis ulang, atau isi manual.' };
  }
  var today = hariIni();
  (data.transactions || []).forEach(function (tx) {
    if (!tx.occurred_on) { tx.occurred_on = today; tx.assumed_date = true; }
    if (tx.direction === 'transfer') tx.category = null;
  });
  return data;
}

// ── parser_wrap.py ──────────────────────────────────────────────────────────
var KATA_UTANG = ['utang', 'hutang', 'cicilan', 'angsuran', 'lunas', 'pinjam',
  'paylater', 'spaylater', 'spinjam', 'kredit'];
var KATA_TALANGAN = ['topup project', 'top up project', 'top-up project', 'biaya project',
  'operasional project', 'talangan', 'saldo kenari', 'topup kenari', 'top up kenari',
  'saldo siray', 'topup siray', 'top up siray', 'kenari', 'siray', 'studio-contoh', 'rin studio'];
var BUKAN_AKUN_SENDIRI = ['kenari', 'siray', 'openai', 'anthropic', 'cloud', 'hosting',
  'vercel', 'supabase', 'domain'];
var KATEGORI_OUT = ['Makan', 'Transport', 'Belanja', 'Hiburan', 'Tagihan', 'Kesehatan', 'Pendidikan', 'Lainnya'];
var KATEGORI_IN = ['Gaji', 'Bonus', 'Lainnya'];
var KATA_PEMISAH = ['ke', 'dari', 'dan', 'lalu', 'terus', 'dengan', 'buat', 'untuk'];

function _adaSalah(teks, daftar) { return daftar.some(function (k) { return teks.indexOf(k) >= 0; }); }

function _frasa_akun(teks, kata) {
  var m = new RegExp('\\b' + kata + '\\s+([A-Za-z][A-Za-z\\- ]{0,30})', 'i').exec(teks || '');
  if (!m) return null;
  var hasil = [];
  var kk = m[1].split(/\s+/).filter(Boolean);
  for (var i = 0; i < kk.length; i++) {
    var w = kk[i];
    if (KATA_PEMISAH.indexOf(w.toLowerCase()) >= 0 || /\d/.test(w)) break;
    hasil.push(w);
    if (hasil.length === 2) break;
  }
  return hasil.join(' ') || null;
}

function lengkapi_akun_transfer(tx, teks) {
  if (tx.direction !== 'transfer') return tx;
  var dari = _frasa_akun(teks, 'dari');
  var ke = _frasa_akun(teks, 'ke');
  var asal = typeof tx.account_hint === 'string' ? tx.account_hint.trim() : '';
  if (asal.indexOf('->') >= 0 || asal.indexOf('→') >= 0 || /\bke\b/i.test(asal)) asal = '';
  if (ke && asal.toLowerCase() === ke.toLowerCase()) asal = '';
  if (dari) asal = dari;
  tx.account_hint = asal || null;
  if (ke) tx.to_account_hint = ke;
  return tx;
}

function tebak_flow_type(tx) {
  var text = ((benar(tx.note) ? String(tx.note) : '') + ' ' +
    (benar(tx.category) ? String(tx.category) : '')).toLowerCase();
  var d = tx.direction;
  if (d !== 'in' && _adaSalah(text, KATA_TALANGAN)) return 'receivable';
  if (d !== 'in' && _adaSalah(text, KATA_UTANG)) return 'debt_payment';
  if (d === 'transfer') return _adaSalah(text, BUKAN_AKUN_SENDIRI) ? 'receivable' : 'transfer';
  if (d === 'in') return 'income';
  return 'expense';
}

function bersihkan(tx) {
  var direction = tx.direction;
  if (['in', 'out', 'transfer'].indexOf(direction) < 0) direction = 'out';
  var category = tx.category;
  if (direction === 'transfer') category = null;
  else {
    var sah = direction === 'in' ? KATEGORI_IN : KATEGORI_OUT;
    if (sah.indexOf(category) < 0) category = 'Lainnya';
  }
  var amount;
  try { amount = bulatRupiah(tx.amount || 0); } catch (e) { amount = 0; }
  return { direction: direction, flow_type: tebak_flow_type(tx), amount: amount,
    category: category, account_hint: tx.account_hint === undefined ? null : tx.account_hint,
    to_account_hint: tx.to_account_hint === undefined ? null : tx.to_account_hint,
    note: tx.note === undefined ? null : tx.note, occurred_on: tx.occurred_on || hariIni(),
    assumed_date: !!tx.assumed_date };
}

function layak_jadi_pertanyaan(q, asli) {
  q = String(q || '').trim();
  if (!q) return false;
  if (q.toLowerCase() === String(asli || '').trim().toLowerCase()) return false;
  if (q.length <= 12) return false;
  var penanda = ['?', 'tidak', 'bukan', 'belum', 'mohon', 'coba', 'maksud', 'transaksi',
    'catat', 'berapa', 'nominal', 'jumlah'];
  return _adaSalah(q.toLowerCase(), penanda);
}

function parse_kontrak(text) {
  text = String(text || '').trim();
  if (!text) return { ok: false, error: 'teks_kosong', message: 'Tidak ada teks untuk diurai.' };
  var hasil;
  try { hasil = chat_entry_parse(text); }
  catch (e) {
    console.log('[parser] uraian gagal: ' + e.message);
    return { ok: false, error: 'model_tidak_membalas',
      message: 'Catat pintar sedang tidak bisa dipakai — model tidak menjawab. ' +
        'Kamu tetap bisa mengisi manual.' };
  }
  var txs = hasil.transactions || [];
  var q = hasil.question;
  if (!txs.length) {
    return { ok: true, draft: { transactions: [],
      question: layak_jadi_pertanyaan(q, text) ? String(q).trim()
        : 'Aku tidak menemukan transaksi di pesan itu.' } };
  }
  var bersih = txs.map(bersihkan)
    .map(function (tx) { return lengkapi_akun_transfer(tx, text); })
    .filter(function (tx) { return tx.amount > 0; });
  if (!bersih.length) {
    return { ok: true, draft: { transactions: [], question: "Ada angka yang tidak terbaca. " +
      "Coba tulis ulang, misal: 'makan malam 45000'." } };
  }
  return { ok: true, draft: { transactions: bersih, question: null } };
}

// ── monthly_analysis.py ─────────────────────────────────────────────────────
var SYS_ANALISA = 'Kamu menganalisa keuangan pribadi berbahasa Indonesia. Balas HANYA JSON valid, tanpa penjelasan, tanpa markdown.\n\n' +
  'Kamu menerima FAKTA keuangan satu bulan. Tugasmu menjelaskannya dengan bahasa manusia.\n\n' +
  'ATURAN WAJIB — melanggar berarti kalimatmu dibuang:\n' +
  '- JANGAN menulis persentase. Tidak "naik 73%", tidak "73 persen". Sebut selisihnya dalam rupiah saja.\n' +
  '- JANGAN menulis angka apa pun yang tidak ada di FAKTA. Tidak boleh menghitung sendiri, tidak boleh memperkirakan, tidak boleh membulatkan.\n' +
  '- SELALU tulis nominal dalam format rupiah lengkap dengan titik dan awalan "Rp": Rp 8.200.000 — bukan 8096600.\n' +
  '- Kalau sebuah kategori tidak punya pembanding bulan lalu, KATAKAN bahwa belum ada pembanding. Jangan mengarang perbandingan.\n' +
  '- Jangan menasihati memotong kategori yang ditandai "wajib": true.\n' +
  '- Jangan menyebut utang atau talangan sebagai "pengeluaran" — keduanya sudah dipisah dan artinya berbeda.\n' +
  '- Kalau "data_lengkap" bernilai false, KATAKAN di ringkasan bahwa data bulan itu belum lengkap (sebutkan berapa hari yang tercatat dari jumlah hari bulan itu). Jangan menyimpulkan "masih banyak sisa" seolah bulan itu sudah penuh.\n' +
  '- Nada: tenang, langsung, tidak menghakimi. Tidak ada pujian, tidak ada ceramah.\n\n' +
  'Format balasan:\n{"ringkasan": "2-3 kalimat tentang bulan itu",\n' +
  ' "per_kategori": {"NamaKategori": "1-2 kalimat tentang kategori itu",\n' +
  '                  "NamaKategoriLain": "..."},\n "penutup": "1 kalimat tentang sisa yang bisa ditabung"}\n\n' +
  'PENTING: "per_kategori" WAJIB memuat SETIAP kategori yang ada di FAKTA, memakai\n' +
  'nama persis seperti di FAKTA. Kalau kamu melewatkan satu kategori, penjelasan\n' +
  'kategori itu hilang dari laporan.\n';

function _bersihkanPersen(teks) {
  var t = String(teks);
  t = t.replace(/\b(naik|turun|lebih tinggi|lebih rendah)\s+\d[\d.,]*\s*(%|persen)/gi, '');
  t = t.replace(/\d[\d.,]*\s*%/g, '');
  t = t.replace(/\b\d[\d.,]*\s*persen\b/gi, '');
  t = t.replace(/\s+([,.;])/g, '$1');
  t = t.replace(/\s{2,}/g, ' ').trim();
  t = t.replace(/^[,;]\s*/, '');
  t = t.replace(/\s*[,;]$/, '');
  if (t) t = t.charAt(0).toUpperCase() + t.slice(1);
  return t.trim();
}

function _angkaDalam(teks) {
  var hasil = {};
  (String(teks).match(/\d[\d.,]*/g) || []).forEach(function (m) {
    var b = m.split('.').join('').split(',').join('.');
    if (b.charAt(b.length - 1) === '.') b = b.slice(0, -1);
    var v = Number(b);
    if (b !== '' && !isNaN(v) && v >= 1000) hasil[Math.trunc(v)] = true;
  });
  return Object.keys(hasil).map(Number);
}

function _adaPersen(teks) { return /\d[\d.,]*\s*%|\bpersen\b/i.test(String(teks)); }

function _faktaAngka(fakta) {
  var sah = {};
  (function telusuri(x) {
    if (x === null || x === undefined || typeof x === 'boolean') return;
    if (Array.isArray(x)) x.forEach(telusuri);
    else if (typeof x === 'object') Object.keys(x).forEach(function (k) { telusuri(x[k]); });
    else if (typeof x === 'number') sah[Math.trunc(x)] = true;
    else if (typeof x === 'string') _angkaDalam(x).forEach(function (a) { sah[a] = true; });
  })(fakta);
  return sah;
}

function _formatRupiah(teks) {
  var MIN = 1900, MAKS = 2100;
  function rapikan(angka) {
    var v = parseInt(angka, 10);
    if (isNaN(v) || v < 1000) return null;
    if (v >= MIN && v <= MAKS) return null;
    return rupiah(v);
  }
  teks = teks.replace(/Rp\.?\s*(\d{1,3}(?:\.\d{3})+|\d+)/g, function (m0, isi) {
    if (/^\d{1,3}(?:\.\d{3})+$/.test(isi)) return rupiah(parseInt(isi.split('.').join(''), 10));
    var h = rapikan(isi);
    return h ? h : m0;
  });
  return teks.replace(/(?<![\d.\-:/])([1-9]\d{3,})(?![\d.\-:/])/g, function (m0) {
    var h = rapikan(m0);
    return h ? h : m0;
  });
}

function _kalimatBawaan(analisa) {
  var h = {};
  analisa.saran.kategori.forEach(function (s) { h[s.kategori] = s.asumsi; });
  return h;
}

function _ringkasUntukModel(analisa) {
  var a = analisa.angka, s = analisa.saran;
  var per = {};
  s.kategori.forEach(function (k) { per[k.kategori] = k; });
  return {
    bulan: analisa.nama_bulan, jumlah_transaksi: a.tx_count, uang_masuk: a.masuk,
    uang_keluar_semua: a.keluar_semua, pengeluaran_sesungguhnya: a.konsumsi,
    pelunasan_utang: a.pelunasan_utang, talangan_ke_project: a.talangan_piutang,
    sisa_kas: a.sisa_kas, sisa_bebas: a.sisa_bebas,
    kelengkapan_data: { hari_tercatat: analisa.kelengkapan.hari_tercatat,
      jumlah_hari_bulan: analisa.kelengkapan.jumlah_hari_bulan,
      data_lengkap: analisa.kelengkapan.lengkap },
    ada_pembanding_bulan_lalu: s.ada_pembanding, bulan_pembanding: s.bulan_pembanding,
    kategori: a.kategori.map(function (k) {
      var sr = per[k.category] || {};
      return { nama: k.category, total: k.total, transaksi: k.tx_count, wajib: k.wajib,
        bulan_lalu: k.total_bulan_lalu, perubahan_persen: k.perubahan_persen,
        potensi_hemat: sr.potensi_hemat === undefined ? null : sr.potensi_hemat };
    }),
  };
}

function _panggilModelAnalisa(fakta) {
  var k = konfigAI();
  if (!k.key) throw new Error('Kunci API belum diatur (Script Properties KENARI_API_KEY)');
  var raw = _panggil(k.base, { model: k.model, max_tokens: 1400, stream: true, temperature: 0.3,
    messages: [{ role: 'system', content: SYS_ANALISA },
      { role: 'user', content: 'FAKTA keuangan bulan ini:\n' + JSON.stringify(fakta, null, 1) +
        '\n\nTulis analisanya.' }] }, k.key);
  var txt = _gabungSSE(raw);
  if (!txt) throw new Error('model tidak membalas (content kosong)');
  return JSON.parse(txt);
}

function buat_narasi(analisa) {
  var fakta = _ringkasUntukModel(analisa);
  var sah = _faktaAngka(fakta);
  var bawaan = _kalimatBawaan(analisa);
  var hasil;
  try { hasil = _panggilModelAnalisa(fakta); }
  catch (e) {
    return { ringkasan: null, per_kategori: bawaan, penutup: null,
      catatan: 'Model tidak bisa dihubungi (' + e.message + '). Dipakai penjelasan dari data.',
      dibuang: [], persen_dipotong: [], kategori_diganti: Object.keys(bawaan).sort(cmp) };
  }
  var dibuang = [], dipotong = [];
  function olah(kalimat, label) {
    kalimat = String(kalimat || '').trim();
    if (!kalimat) return null;
    if (_adaPersen(kalimat)) {
      var asli = kalimat;
      kalimat = _bersihkanPersen(kalimat);
      if (kalimat && kalimat !== asli) dipotong.push({ tempat: label, asli: asli, hasil: kalimat });
    }
    if (!kalimat) return null;
    kalimat = _formatRupiah(kalimat);
    var angka = _angkaDalam(kalimat);
    for (var i = 0; i < angka.length; i++) {
      if (!sah[angka[i]]) {
        dibuang.push({ tempat: label, kalimat: kalimat, angka_asing: angka.slice().sort(function (a, b) { return a - b; }) });
        return null;
      }
    }
    return kalimat;
  }
  var ringkasan = olah(hasil.ringkasan, 'ringkasan');
  var penutup = olah(hasil.penutup, 'penutup');
  var perKat = {}, diganti = [];
  analisa.saran.kategori.forEach(function (k) {
    var kal = olah((hasil.per_kategori || {})[k.kategori], 'kategori:' + k.kategori);
    if (kal) perKat[k.kategori] = kal;
    else { perKat[k.kategori] = bawaan[k.kategori] === undefined ? null : bawaan[k.kategori]; diganti.push(k.kategori); }
  });
  var bagian = [];
  if (dibuang.length) bagian.push(dibuang.length + ' kalimat dibuang karena memuat angka yang tidak ada di data');
  if (dipotong.length) bagian.push(dipotong.length + ' kalimat disebut ulang tanpa persentase');
  if (diganti.length) bagian.push(diganti.length + ' kategori memakai penjelasan dari data');
  return { ringkasan: ringkasan, per_kategori: perKat, penutup: penutup,
    catatan: bagian.length ? bagian.join('; ') + '.' : null,
    dibuang: dibuang, persen_dipotong: dipotong, kategori_diganti: diganti };
}

// ── /api/ai-status ──────────────────────────────────────────────────────────
function api_ai_status() {
  var k = konfigAI();
  if (!k.key) {
    return { ok: false, model: k.model, endpoint: k.base, latensi_ms: null, keadaan: 'gagal',
      pesan: 'Kunci API belum diatur di server. Minta pemiliknya mengisinya di Script ' +
        'Properties Apps Script.' };
  }
  var mulai = Date.now();
  try {
    var r = httpPost(k.base, { model: k.model, max_tokens: 5,
      messages: [{ role: 'user', content: 'ok' }] }, k.key);
    var lat = Date.now() - mulai;
    if (r.code < 200 || r.code >= 300) {
      return { ok: false, model: k.model, endpoint: k.base, latensi_ms: lat, keadaan: 'gagal',
        pesan: ('AI tidak menjawab (HTTP ' + r.code + '). ' + String(r.text || '').slice(0, 200).trim()) };
    }
    var d = {};
    try { d = JSON.parse(r.text); } catch (e) { d = {}; }
    var lambat = lat > 5000;
    return { ok: true, model: d.model || k.model, endpoint: k.base, latensi_ms: lat,
      keadaan: lambat ? 'lambat' : 'ok', pesan: lambat ? 'AI menjawab tapi lambat.' : 'AI siap dipakai.' };
  } catch (e) {
    return { ok: false, model: k.model, endpoint: k.base, latensi_ms: Date.now() - mulai,
      keadaan: 'gagal', pesan: 'AI tidak bisa dihubungi (' + (e.name || 'Error') + ').' };
  }
}
