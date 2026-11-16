/**
 * Port src/db.py — SEMUA angka keuangan dihitung di sini.
 *
 * Aturan yang dibawa apa adanya dari db.py (baca docstring aslinya untuk
 * alasan lengkap):
 *   - amount selalu positif; arah di `direction`, sifat di `flow_type`
 *   - `total_out` = semua uang keluar; konsumsi = `expense_real`
 *   - akun nonaktif TETAP dihitung ke kekayaan
 *   - tidak ada tebakan akun; gagal dengan jelas lebih baik daripada salah senyap
 *
 * Nama fungsi sengaja mengikuti db.py supaya perbandingan dua berkas mudah.
 * Setiap rumus yang berubah di satu sisi WAJIB diubah di sisi lain; uji
 * `tests/gas/banding.test.js` membandingkan keluaran keduanya.
 */
var ST = null;   // store aktif; dipasang oleh 70_main.js atau uji

function _akun() { return ST.baca('accounts'); }
function _kategori() { return ST.baca('categories'); }
function _tx() { return ST.baca('transactions'); }

function _petaId(rows) {
  var m = {};
  rows.forEach(function (r) { m[r.id] = r; });
  return m;
}

// ── saldo (v_account_balances) ──────────────────────────────────────────────
function _saldoSemua(sampaiTanggal) {
  var saldo = {};
  _akun().forEach(function (a) { saldo[a.id] = a.opening_balance || 0; });
  _tx().forEach(function (t) {
    if (sampaiTanggal && !(t.occurred_on <= sampaiTanggal)) return;
    if (t.direction === 'in') { if (t.account_id in saldo) saldo[t.account_id] += t.amount; }
    else if (t.direction === 'out') { if (t.account_id in saldo) saldo[t.account_id] -= t.amount; }
    else if (t.direction === 'transfer') {
      if (t.account_id in saldo) saldo[t.account_id] -= t.amount;
      if (t.to_account_id in saldo) saldo[t.to_account_id] += t.amount;
    }
  });
  return saldo;
}

function _vAccountBalances() {
  var saldo = _saldoSemua(null);
  return _akun().map(function (a) {
    return { id: a.id, name: a.name, kind: a.kind, opening_balance: a.opening_balance,
             is_active: a.is_active, balance: saldo[a.id] };
  });
}

function account_balances(include_inactive) {
  var rows = _vAccountBalances();
  if (!include_inactive) rows = rows.filter(function (r) { return r.is_active === 1; });
  rows.sort(function (a, b) { return (b.balance - a.balance) || cmp(a.name, b.name); });
  return rows;
}

var KIND_LIKUID = ['bank', 'cash', 'ewallet'];
var KIND_TIDAK_LIKUID = ['savings', 'investment'];

function net_worth() {
  var b = _vAccountBalances();
  var dipakai = {};
  _tx().forEach(function (t) {
    dipakai[t.account_id] = true;
    if (t.to_account_id !== null && t.to_account_id !== undefined) dipakai[t.to_account_id] = true;
  });
  var r = { net_worth: 0, liquid: 0, non_liquid: 0, account_count: 0,
            account_count_all: 0, balance_inactive: 0 };
  b.forEach(function (a) {
    r.net_worth += a.balance;
    if (KIND_LIKUID.indexOf(a.kind) >= 0) r.liquid += a.balance;
    if (KIND_TIDAK_LIKUID.indexOf(a.kind) >= 0) r.non_liquid += a.balance;
    if (a.is_active === 1 && (a.opening_balance !== 0 || dipakai[a.id])) r.account_count += 1;
    if (a.is_active === 1) r.account_count_all += 1;
    if (a.is_active === 0) r.balance_inactive += a.balance;
  });
  return r;
}

// ── v_monthly_flow ──────────────────────────────────────────────────────────
function _alirBulanan() {
  var m = {};
  _tx().forEach(function (t) {
    var k = String(t.occurred_on).slice(0, 7);
    var r = m[k] || (m[k] = { month: k, total_in: 0, total_out: 0, expense_real: 0,
      receivable_out: 0, debt_payment_out: 0, net: 0, net_real: 0, tx_count: 0,
      in_count: 0, out_count: 0, transfer_count: 0 });
    r.tx_count += 1;
    if (t.direction === 'in') {
      r.total_in += t.amount; r.net += t.amount; r.net_real += t.amount; r.in_count += 1;
    } else if (t.direction === 'out') {
      r.total_out += t.amount; r.net -= t.amount; r.out_count += 1;
      if (t.flow_type === 'expense') { r.expense_real += t.amount; r.net_real -= t.amount; }
      if (t.flow_type === 'receivable') r.receivable_out += t.amount;
      if (t.flow_type === 'debt_payment') r.debt_payment_out += t.amount;
    } else if (t.direction === 'transfer') {
      r.transfer_count += 1;
    }
  });
  return m;
}

function monthly_summary(month) {
  month = month || bulanBerjalan();
  var r = _alirBulanan()[month];
  if (!r) {
    return { month: month, total_in: 0, total_out: 0, net: 0, net_real: 0,
      expense_real: 0, receivable_out: 0, debt_payment_out: 0, tx_count: 0,
      in_count: 0, out_count: 0, transfer_count: 0, _ada_data: false };
  }
  var d = salin(r);
  d._ada_data = true;
  return d;
}

function list_transactions(month, limit, direction) {
  var akun = _petaId(_akun()), kat = _petaId(_kategori());
  var rows = _tx().filter(function (t) {
    if (month && String(t.occurred_on).slice(0, 7) !== month) return false;
    if (direction && t.direction !== direction) return false;
    return !!akun[t.account_id];   // JOIN accounts (inner)
  });
  rows.sort(function (a, b) { return cmp(b.occurred_on, a.occurred_on) || (b.id - a.id); });
  if (limit) rows = rows.slice(0, limit);
  return rows.map(function (t) {
    var a2 = akun[t.to_account_id], c = kat[t.category_id];
    return { id: t.id, occurred_on: t.occurred_on, direction: t.direction,
      flow_type: t.flow_type, amount: t.amount, note: t.note, source: t.source,
      created_at: t.created_at, account_name: akun[t.account_id].name,
      to_account_name: a2 ? a2.name : null, category_name: c ? c.name : null,
      category_direction: c ? c.direction : null };
  });
}

function get_categories(direction) {
  var rows = _kategori().filter(function (c) { return !direction || c.direction === direction; });
  rows = rows.map(salin);
  rows.sort(function (a, b) {
    return cmp(a.direction, b.direction) || (a.sort_order - b.sort_order) || cmp(a.name, b.name);
  });
  return rows;
}

function monthly_trend(months) {
  var daftar = [];
  var b = bulanBerjalan();
  for (var i = 0; i < months; i++) { daftar.unshift(b); b = bulanSebelum(b); }
  var alir = _alirBulanan();
  return { months: months, items: daftar.map(function (bl) {
    var r = alir[bl];
    if (r) {
      return { month: bl, ada_data: true, total_in: r.total_in, total_out: r.total_out,
        expense_real: r.expense_real, net: r.net, net_real: r.net_real, tx_count: r.tx_count };
    }
    return { month: bl, ada_data: false, total_in: null, total_out: null,
      expense_real: null, net: null, net_real: null, tx_count: 0 };
  }) };
}

/** Total `expense` per nama kategori. Urut terbesar (seri: urutan nama, stabil). */
function _perKategori(month, direction, flow) {
  var kat = _petaId(_kategori());
  var g = {}, urut = [];
  _tx().forEach(function (t) {
    if (String(t.occurred_on).slice(0, 7) !== month) return;
    if (t.direction !== direction || t.flow_type !== flow) return;
    var c = kat[t.category_id];
    if (!c) return;
    if (!g[c.name]) { g[c.name] = { category: c.name, total: 0, tx_count: 0 }; urut.push(c.name); }
    g[c.name].total += t.amount;
    g[c.name].tx_count += 1;
  });
  return urut.map(function (n) { return g[n]; });
}

function spending_by_category(month, direction) {
  month = month || bulanBerjalan();
  direction = direction || 'out';
  var items = _perKategori(month, direction, 'expense');
  items.sort(function (a, b) { return (b.total - a.total) || cmp(a.category, b.category); });
  return { month: month, items: items };
}

function saving_suggestions(month) {
  month = month || bulanBerjalan();
  var bulanLalu = bulanSebelum(month);
  var saran = [];
  var skrg = spending_by_category(month).items;
  var lalu = {};
  spending_by_category(bulanLalu).items.forEach(function (r) { lalu[r.category] = r.total; });

  skrg.forEach(function (r) {
    var sebelum = lalu[r.category];
    if (sebelum && sebelum > 0 && r.total > sebelum * 1.3) {
      saran.push({ jenis: 'kenaikan_kategori', kategori: r.category,
        potensi_hemat: r.total - sebelum,
        asumsi: r.category + ' naik dari ' + rupiah(sebelum) + ' (bulan lalu) ke ' +
          rupiah(r.total) + ' bulan ini. Angka hemat = selisihnya, kalau kembali ke pola bulan lalu.' });
    }
  });

  var sering = _perKategori(month, 'out', 'expense').filter(function (r) { return r.tx_count >= 5; });
  sering.sort(function (a, b) { return (b.tx_count - a.tx_count) || cmp(a.category, b.category); });
  sering.forEach(function (r) {
    saran.push({ jenis: 'sering_kecil', kategori: r.category, potensi_hemat: null,
      asumsi: r.category + ' tercatat ' + r.tx_count + ' kali bulan ini (total ' +
        rupiah(r.total) + ', rata-rata ' + rupiah(r.tx_count ? floorDiv(r.total, r.tx_count) : 0) +
        '). Banyak transaksi kecil biasanya lebih mudah dipotong daripada satu transaksi ' +
        'besar — tapi hanya kamu yang tahu mana yang bisa dikurangi.' });
  });

  var ms = monthly_summary(month);
  if (ms.receivable_out) {
    saran.push({ jenis: 'talangan_project', kategori: null, potensi_hemat: null,
      asumsi: rupiah(ms.receivable_out) + ' ditalangi ke project bulan ini. Uang ini bukan ' +
        'pengeluaran pribadi, tapi selama belum kembali ia tidak bisa dipakai untuk hal lain.' });
  }
  if (ms.total_in) {
    var rasio = ms.net_real / ms.total_in * 100;
    saran.push({ jenis: 'rasio_sisa', kategori: null, potensi_hemat: null,
      asumsi: 'Dari ' + rupiah(ms.total_in) + ' yang masuk, ' + rupiah(ms.net_real) + ' (' +
        pyRound(rasio) + '%) tersisa setelah pengeluaran sungguhan. Angka ini belum ' +
        'memperhitungkan pelunasan utang dan talangan.' });
  }
  return { month: month, items: saran,
    catatan: "Semua saran menyebut asumsinya. Tidak ada persentase 'ideal' yang dikarang " +
      '— perbandingan diambil dari data Deny sendiri.' };
}

function kelengkapan_bulan(month) {
  var y = parseInt(month.slice(0, 4), 10), m = parseInt(month.slice(5, 7), 10);
  var jh = jumlahHari(y, m);
  var rows = _tx().filter(function (t) { return String(t.occurred_on).slice(0, 7) === month; });
  var hariSet = {}, pertama = null, terakhir = null;
  rows.forEach(function (t) {
    hariSet[t.occurred_on] = true;
    if (pertama === null || t.occurred_on < pertama) pertama = t.occurred_on;
    if (terakhir === null || t.occurred_on > terakhir) terakhir = t.occurred_on;
  });
  var tx = rows.length, hari = Object.keys(hariSet).length;
  var ambang = Math.max(1, Math.trunc(jh * 0.6));
  var peringatan = null;
  if (tx === 0) {
    peringatan = 'Belum ada transaksi sama sekali di bulan ini, jadi belum ada yang bisa dianalisa.';
  } else if (hari < ambang) {
    peringatan = 'Data bulan ini baru mencakup ' + hari + ' dari ' + jh + ' hari (' + pertama +
      ' s/d ' + terakhir + '). Angka sisa di bawah dihitung dari data yang ada saja — ' +
      'bukan gambaran sebulan penuh.';
  }
  return { month: month, jumlah_hari_bulan: jh, hari_tercatat: hari, tx_count: tx,
    tanggal_pertama: pertama, tanggal_terakhir: terakhir, ambang_hari: ambang,
    lengkap: peringatan === null, peringatan: peringatan };
}

function bulan_sudah_selesai(month) { return month < bulanBerjalan(); }

function daftar_bulan() {
  var hitung = {};
  _tx().forEach(function (t) {
    var k = String(t.occurred_on).slice(0, 7);
    hitung[k] = (hitung[k] || 0) + 1;
  });
  var dianalisa = {};
  ST.baca('analyses').forEach(function (a) { dianalisa[a.month] = true; });
  var bulan = Object.keys(hitung).sort().reverse().map(function (k) {
    return { month: k, nama_bulan: namaBulan(k), tx_count: hitung[k],
      ada_analisa: !!dianalisa[k], boleh_dianalisa: bulan_sudah_selesai(k) };
  });
  return { bulan: bulan, bulan_berjalan: bulanBerjalan(),
    catatan: 'Hanya bulan yang punya transaksi. Bulan kosong tidak dimasukkan karena ' +
      'tidak ada yang bisa ditampilkan.' };
}

// ── analisa bulanan ─────────────────────────────────────────────────────────
var KATEGORI_WAJIB = ['Tagihan', 'Transport'];

function saldo_per_tanggal(tanggal) {
  var saldo = _saldoSemua(tanggal);
  var akun = _akun().map(function (a) {
    return { id: a.id, name: a.name, kind: a.kind, opening_balance: a.opening_balance,
      is_active: a.is_active, balance: saldo[a.id] };
  });
  var aktif = akun.filter(function (a) { return a.is_active; });
  function jumlah(arr) { return arr.reduce(function (s, a) { return s + a.balance; }, 0); }
  return { per_tanggal: tanggal, accounts: akun, net_worth: jumlah(akun),
    liquid: jumlah(aktif.filter(function (a) { return KIND_LIKUID.indexOf(a.kind) >= 0; })),
    non_liquid: jumlah(aktif.filter(function (a) { return KIND_TIDAK_LIKUID.indexOf(a.kind) >= 0; })) };
}

function ringkasan_bulan(month) {
  var ms = monthly_summary(month);
  var nw = net_worth();
  var kategori = spending_by_category(month);
  var lalu = {};
  var laluItems = spending_by_category(bulanSebelum(month)).items;
  laluItems.forEach(function (r) { lalu[r.category] = r.total; });

  var rincian = kategori.items.map(function (r) {
    var sebelum = lalu[r.category];
    var naik = null;
    if (sebelum && sebelum > 0) naik = pyRound((r.total - sebelum) / sebelum * 100);
    return { category: r.category, total: r.total, tx_count: r.tx_count,
      total_bulan_lalu: sebelum === undefined ? null : sebelum, perubahan_persen: naik,
      wajib: KATEGORI_WAJIB.indexOf(r.category) >= 0 };
  });

  var akhir = null, tgl = null;
  if (bulan_sudah_selesai(month) && ms._ada_data) {
    tgl = akhirBulan(month);
    akhir = saldo_per_tanggal(tgl);
  }
  return {
    month: month, ada_data: ms._ada_data, tx_count: ms.tx_count,
    masuk: ms.total_in, keluar_semua: ms.total_out, konsumsi: ms.expense_real,
    pelunasan_utang: ms.debt_payment_out, talangan_piutang: ms.receivable_out,
    sisa_kas: ms.total_in - ms.total_out, sisa_bebas: ms.total_in - ms.expense_real,
    kategori: rincian, kategori_lalu_ada: laluItems.length > 0,
    net_worth: nw.net_worth, saldo_akun: account_balances(false),
    net_worth_akhir: akhir ? akhir.net_worth : null,
    net_worth_akhir_liquid: akhir ? akhir.liquid : null,
    net_worth_akhir_non_liquid: akhir ? akhir.non_liquid : null,
    per_tanggal: tgl, kategori_wajib: KATEGORI_WAJIB.slice(),
  };
}

function saran_hemat(month) {
  var bulanLalu = bulanSebelum(month);
  var skrg = spending_by_category(month).items;
  var laluItems = spending_by_category(bulanLalu).items;
  var lalu = {};
  laluItems.forEach(function (r) { lalu[r.category] = r.total; });
  var saran = [];

  skrg.forEach(function (r) {
    var kategori = r.category;
    var wajib = KATEGORI_WAJIB.indexOf(kategori) >= 0;
    var sebelum = lalu[kategori];
    if (!sebelum) {
      saran.push({ kategori: kategori, total: r.total, tx_count: r.tx_count, wajib: wajib,
        jenis: 'tanpa_pembanding', potensi_hemat: null,
        asumsi: kategori + ' ' + rupiah(r.total) + ' bulan ini. Belum ada data ' +
          namaBulan(bulanLalu) + ' sebagai pembanding, jadi tidak bisa dinilai naik atau turun.' });
      return;
    }
    var beda = r.total - sebelum;
    if (wajib) {
      saran.push({ kategori: kategori, total: r.total, tx_count: r.tx_count, wajib: true,
        jenis: 'wajib', potensi_hemat: null,
        asumsi: kategori + ' ' + rupiah(r.total) + (beda === 0 ? '' : ' (bulan lalu ' +
          rupiah(sebelum) + ')') + '. Kategori ini dianggap wajib, jadi tidak disarankan dipotong.' });
    } else if (beda > 0) {
      saran.push({ kategori: kategori, total: r.total, tx_count: r.tx_count, wajib: false,
        jenis: 'naik', potensi_hemat: beda,
        asumsi: kategori + ' naik dari ' + rupiah(sebelum) + ' (bulan lalu) ke ' +
          rupiah(r.total) + ' — naik ' + rupiah(beda) +
          '. Angka hemat = selisihnya, kalau kembali ke pola bulan lalu.' });
    } else {
      saran.push({ kategori: kategori, total: r.total, tx_count: r.tx_count, wajib: false,
        jenis: 'turun_atau_sama', potensi_hemat: null,
        asumsi: kategori + ' ' + rupiah(r.total) + (beda === 0 ? '' : ', turun ' +
          rupiah(Math.abs(beda))) + ' — tidak lebih besar dari bulan lalu (' + rupiah(sebelum) +
          '). Tidak ada yang perlu dipotong di sini.' });
    }
  });

  var ada = saran.some(function (s) { return s.potensi_hemat; });
  var total = saran.reduce(function (t, s) { return t + (s.potensi_hemat || 0); }, 0);
  return { month: month, bulan_pembanding: bulanLalu, ada_pembanding: laluItems.length > 0,
    kategori: saran, total_potensi_hemat: ada ? total : null,
    catatan: 'Setiap angka di sini punya dasar hitungan. Yang tidak punya dasar ' +
      'dikembalikan sebagai null, bukan 0.' };
}

function _txTerakhir(month) {
  var t = null;
  _tx().forEach(function (r) {
    if (String(r.occurred_on).slice(0, 7) !== month) return;
    var v = r.created_at ? r.created_at : r.occurred_on;
    if (t === null || v > t) t = v;
  });
  return t;
}

function _analisaTersimpan(month) {
  return ST.baca('analyses').filter(function (a) { return a.month === month; })[0] || null;
}

function analisa_lengkap(month) {
  var angka = ringkasan_bulan(month);
  var saran = saran_hemat(month);
  var tersimpan = _analisaTersimpan(month);
  var txTerakhir = _txTerakhir(month);
  var narasi = null;
  if (tersimpan && tersimpan.narasi) {
    try { narasi = JSON.parse(tersimpan.narasi); } catch (e) { narasi = null; }
  }
  var basi = false;
  if (tersimpan && tersimpan.dibuat_pada && txTerakhir) {
    basi = String(txTerakhir) > String(tersimpan.dibuat_pada);
  }
  return {
    month: month, nama_bulan: namaBulan(month), bulan_berjalan: bulanBerjalan(),
    boleh_dianalisa: bulan_sudah_selesai(month), angka: angka, saran: saran,
    kelengkapan: kelengkapan_bulan(month), ada_analisa: !!tersimpan,
    dibuat_pada: tersimpan ? tersimpan.dibuat_pada : null,
    model: tersimpan ? tersimpan.model : null, narasi: narasi, narasi_basi: basi,
    tx_terakhir: txTerakhir, catatan_analisa: tersimpan ? tersimpan.catatan : null,
  };
}

function simpan_analisa(month, narasi, snapshot, model, catatan) {
  var baris = {
    month: month, dibuat_pada: sekarangTeks(), tx_terakhir: _txTerakhir(month),
    narasi: narasi === null || narasi === undefined ? null : JSON.stringify(narasi),
    snapshot: snapshot === null || snapshot === undefined ? null : JSON.stringify(snapshot),
    model: model || null, catatan: catatan || null,
  };
  var ada = _analisaTersimpan(month);
  if (ada) { baris.id = ada.id; ST.ubah('analyses', ada.id, baris); }
  else ST.tambah('analyses', [baris]);
  return analisa_lengkap(month);
}

function hapus_analisa(month) {
  return ST.hapusDimana('analyses', function (a) { return a.month === month; }) > 0;
}

// ── target tabungan (v_savings_progress) ────────────────────────────────────
function _progres(g) {
  var a = _petaId(_akun())[g.account_id];
  if (!a) return null;                       // JOIN accounts
  var bal = _saldoSemua(null)[g.account_id] || 0;
  return { id: g.id, name: g.name, target_amount: g.target_amount, target_date: g.target_date,
    account_id: g.account_id, account_name: a.name, account_kind: a.kind, terkumpul: bal,
    sisa: g.target_amount - bal,
    persen: g.target_amount > 0 ? sqlRound(bal * 100.0 / g.target_amount) : null,
    status: bal <= 0 ? 'belum_mulai' : bal >= g.target_amount ? 'tercapai' : 'berjalan',
    is_archived: g.is_archived, created_at: g.created_at };
}

function _riwayatTransfer(kolom, accountId) {
  var g = {};
  _tx().forEach(function (t) {
    if (t.direction !== 'transfer' || t[kolom] !== accountId) return;
    var k = String(t.occurred_on).slice(0, 7);
    var r = g[k] || (g[k] = { month: k, total: 0, tx_count: 0 });
    r.total += t.amount; r.tx_count += 1;
  });
  return Object.keys(g).sort().reverse().map(function (k) { return g[k]; });
}

function target_aktif() {
  var aktif = ST.baca('savings_goals').filter(function (g) { return g.is_archived === 0; })
    .sort(function (a, b) { return a.id - b.id; })
    .map(_progres).filter(function (x) { return x; });
  if (!aktif.length) return null;
  var target = aktif[0];
  var riwayat = _riwayatTransfer('to_account_id', target.account_id);
  target.riwayat_setoran = riwayat;
  target.riwayat_penarikan = _riwayatTransfer('account_id', target.account_id);
  if (riwayat.length) {
    var total = riwayat.reduce(function (s, r) { return s + r.total; }, 0);
    target.rata_setoran_bulanan = pyRound(total / riwayat.length);
    target.bulan_ada_setoran = riwayat.length;
  } else {
    target.rata_setoran_bulanan = null;
    target.bulan_ada_setoran = 0;
  }
  target.perkiraan_bulan_lagi = (target.rata_setoran_bulanan && target.sisa > 0)
    ? -floorDiv(-target.sisa, target.rata_setoran_bulanan) : null;
  return target;
}

function set_target(name, target_amount, account_hint, account_id, target_date) {
  name = String(name || '').trim();
  if (!name) throw GalatNilai('nama target tidak boleh kosong');
  try { target_amount = bulatRupiah(target_amount); }
  catch (e) { throw GalatNilai('target harus angka bulat rupiah'); }
  if (target_amount <= 0) throw GalatNilai('target harus lebih besar dari nol');
  if (target_date && !tanggalSah(String(target_date).slice(0, 10))) {
    throw GalatNilai("tanggal target '" + target_date + "' tidak sah. Pakai YYYY-MM-DD.");
  }
  var akun = _resolve_account(account_id, account_hint, 'akun');
  // Arsip lama + tambah baru: dua tulisan, tapi semua validasi sudah lewat di
  // atas, jadi tidak ada jendela "target lama hilang tanpa pengganti" karena
  // input buruk. (Setara satu transaksi DB di db.set_target.)
  var semua = ST.baca('savings_goals').map(function (g) {
    var x = salin(g); if (x.is_archived === 0) x.is_archived = 1; return x;
  });
  ST.gantiSemua('savings_goals', semua);
  ST.tambah('savings_goals', [{ name: name, target_amount: target_amount, account_id: akun,
    target_date: target_date || null, is_archived: 0, created_at: sekarangTeks() }]);
  return target_aktif();
}

function hapus_target() {
  var ada = false;
  var semua = ST.baca('savings_goals').map(function (g) {
    var x = salin(g); if (x.is_archived === 0) { x.is_archived = 1; ada = true; } return x;
  });
  if (ada) ST.gantiSemua('savings_goals', semua);
  return ada;
}

// ── tulis akun ──────────────────────────────────────────────────────────────
function create_account(name, kind, opening_balance) {
  name = String(name || '').trim();
  if (!name) throw GalatNilai('nama akun tidak boleh kosong');
  var ada = _akun().some(function (a) { return a.name.toLowerCase() === name.toLowerCase(); });
  if (ada) throw GalatNilai("sudah ada akun bernama '" + name + "'");
  var ob = pyInt(opening_balance || 0);
  var id = ST.tambah('accounts', [{ name: name, kind: kind, opening_balance: ob,
    is_active: 1, created_at: sekarangTeks() }])[0];
  return { id: id, name: name, kind: kind, opening_balance: ob };
}

function update_account(account_id, name, is_active) {
  var row = _petaId(_akun())[Number(account_id)];
  if (!row) throw GalatNilai('tidak ada akun dengan id ' + account_id);
  if (name !== null && name !== undefined) {
    name = String(name).trim();
    if (!name) throw GalatNilai('nama akun tidak boleh kosong');
    var bentrok = _akun().some(function (a) {
      return a.name.toLowerCase() === name.toLowerCase() && a.id !== row.id;
    });
    if (bentrok) throw GalatNilai("sudah ada akun bernama '" + name + "'");
  } else name = row.name;
  if (is_active === null || is_active === undefined) is_active = row.is_active;
  var baru = salin(row);
  baru.name = name; baru.is_active = is_active;
  ST.ubah('accounts', row.id, baru);
  return { id: row.id, name: name, kind: row.kind, opening_balance: row.opening_balance,
    is_active: is_active };
}

// ── tulis transaksi ─────────────────────────────────────────────────────────
var FLOW_TYPES = ['expense', 'income', 'receivable', 'debt_payment', 'transfer'];
var FLOW_DIRECTION = { expense: 'out', receivable: 'out', debt_payment: 'out',
  transfer: 'transfer', income: 'in' };

function _aktifUrutId() {
  return _akun().filter(function (a) { return a.is_active === 1; })
    .sort(function (a, b) { return a.id - b.id; });
}

function _daftar_akun() {
  return _akun().filter(function (a) { return a.is_active === 1; })
    .map(function (a) { return a.name; }).sort(cmp).join(', ');
}

function _resolve_account(account_id, hint, peran) {
  peran = peran || 'akun';
  var aktif = _aktifUrutId();
  if (benar(account_id)) {
    var r = aktif.filter(function (a) { return a.id === Number(account_id); })[0];
    if (r) return r.id;
    throw GalatNilai(peran + ' id ' + account_id + ' tidak ada atau tidak aktif');
  }
  if (hint && String(hint).trim()) {
    var bersih = String(hint).trim(), kecil = bersih.toLowerCase();
    var persis = aktif.filter(function (a) { return a.name.toLowerCase() === kecil; })[0];
    if (persis) return persis.id;
    var mirip = aktif.filter(function (a) { return a.name.toLowerCase().indexOf(kecil) >= 0; })[0];
    if (mirip) return mirip.id;
    throw GalatNilai(peran + " '" + bersih + "' tidak ditemukan. Akun yang ada: " + _daftar_akun());
  }
  if (aktif.length === 1) return aktif[0].id;
  throw GalatNilai(peran + ' tidak disebutkan. Ada ' + aktif.length + ' akun aktif (' +
    aktif.map(function (a) { return a.name; }).join(', ') + ') — sebutkan ' + peran + '.' +
    (peran === 'akun' ? '' :
      " Contoh lengkap: 'pindah dana 100000 dari Mandiri ke Tabungan'."));
}

function _resolve_category(name, direction) {
  name = String(name || 'Lainnya').trim();
  var kat = _kategori().slice().sort(function (a, b) { return a.id - b.id; });
  var r = kat.filter(function (c) {
    return c.name.toLowerCase() === name.toLowerCase() && c.direction === direction;
  })[0];
  if (r) return r.id;
  r = kat.filter(function (c) { return c.name === 'Lainnya' && c.direction === direction; })[0];
  if (!r) {
    throw GalatNilai("kategori '" + name + "' tidak ada dan tidak ada 'Lainnya' untuk arah " +
      direction);
  }
  return r.id;
}

function save_transactions(items) {
  // Semua baris divalidasi & di-resolve DULU, baru ditulis sekaligus:
  // semua-atau-tidak-sama-sekali, sama seperti satu transaksi DB.
  var baru = items.map(function (it) {
    var direction = it.direction;
    var flow_type = it.flow_type || (direction === 'in' ? 'income'
      : direction === 'transfer' ? 'transfer' : 'expense');
    if (FLOW_TYPES.indexOf(flow_type) < 0) throw GalatNilai("flow_type '" + flow_type + "' tidak dikenal");
    if (FLOW_DIRECTION[flow_type] !== direction) {
      throw GalatNilai("flow_type '" + flow_type + "' tidak cocok dengan direction '" + direction +
        "' (harusnya '" + FLOW_DIRECTION[flow_type] + "')");
    }
    var account_id = _resolve_account(it.account_id, it.account_hint,
      direction === 'transfer' ? 'akun asal' : 'akun');
    var to_account_id = null, category_id = null;
    if (direction === 'transfer') {
      to_account_id = _resolve_account(it.to_account_id, it.to_account_hint, 'akun tujuan');
      if (to_account_id === account_id) throw GalatNilai('transfer ke akun yang sama tidak masuk akal');
    } else {
      category_id = _resolve_category(it.category, it.direction);
    }
    var amount = pyInt(it.amount);
    if (!(amount > 0)) throw GalatNilai('CHECK constraint failed: amount > 0');
    return { occurred_on: String(it.occurred_on), direction: direction, amount: amount,
      account_id: account_id, to_account_id: to_account_id, category_id: category_id,
      note: it.note === undefined ? null : it.note, flow_type: flow_type, source: 'manual',
      created_at: sekarangTeks() };
  });
  return ST.tambah('transactions', baru);
}

function get_transaction(tx_id) {
  var t = _petaId(_tx())[Number(tx_id)];
  if (!t) return null;
  var akun = _petaId(_akun()), kat = _petaId(_kategori());
  if (!akun[t.account_id]) return null;
  var o = salin(t);
  o.account_name = akun[t.account_id].name;
  o.to_account_name = akun[t.to_account_id] ? akun[t.to_account_id].name : null;
  o.category_name = kat[t.category_id] ? kat[t.category_id].name : null;
  return o;
}

function update_transaction(tx_id, changes) {
  ['direction', 'id', 'created_at', 'source'].forEach(function (f) {
    if (f in changes) {
      throw GalatNilai("kolom '" + f + "' tidak bisa diubah langsung" +
        (f === 'direction' ? " — ubah 'flow_type', arahnya mengikuti" : ''));
    }
  });
  var row = _petaId(_tx())[Number(tx_id)];
  if (!row) throw GalatNilai('tidak ada transaksi dengan id ' + tx_id);
  var r = salin(row);

  if ('occurred_on' in changes) {
    var tgl = String(changes.occurred_on).slice(0, 10);
    if (!tanggalSah(tgl)) throw GalatNilai("tanggal '" + tgl + "' tidak sah. Pakai format YYYY-MM-DD.");
    r.occurred_on = tgl;
  }
  if ('amount' in changes) {
    try { r.amount = bulatRupiah(changes.amount); }
    catch (e) { throw GalatNilai('nominal harus angka bulat rupiah'); }
    if (r.amount <= 0) throw GalatNilai('nominal harus lebih besar dari nol');
  }
  if ('account_id' in changes || 'account_hint' in changes) {
    r.account_id = _resolve_account(changes.account_id, changes.account_hint,
      (changes.flow_type || row.flow_type) === 'transfer' ? 'akun asal' : 'akun');
  }
  if ('flow_type' in changes) {
    if (FLOW_TYPES.indexOf(changes.flow_type) < 0) {
      throw GalatNilai("flow_type '" + changes.flow_type + "' tidak dikenal");
    }
    r.flow_type = changes.flow_type;
    r.direction = FLOW_DIRECTION[changes.flow_type];
  }
  if (r.flow_type === 'transfer') {
    if ('to_account_id' in changes || 'to_account_hint' in changes) {
      r.to_account_id = _resolve_account(changes.to_account_id, changes.to_account_hint, 'akun tujuan');
    }
    if (!r.to_account_id) {
      throw GalatNilai("transfer butuh akun tujuan. Kirim 'to_account_id' atau " +
        "'to_account_hint'. Kalau bukan transfer, ubah juga 'flow_type'.");
    }
    if (r.to_account_id === r.account_id) throw GalatNilai('transfer ke akun yang sama tidak masuk akal');
    r.category_id = null;
  } else {
    if ('to_account_id' in changes || 'to_account_hint' in changes) {
      throw GalatNilai("flow_type '" + r.flow_type + "' tidak boleh punya akun tujuan. " +
        'Akun tujuan hanya untuk transfer.');
    }
    r.to_account_id = null;
    if ('category' in changes || 'category_id' in changes || r.category_id === null) {
      r.category_id = _resolve_category(changes.category, r.direction);
    }
  }
  if ('note' in changes) r.note = changes.note;
  ST.ubah('transactions', r.id, r);
  return get_transaction(r.id);
}

function delete_transaction(tx_id) {
  var isi = get_transaction(tx_id);
  if (!isi) throw GalatNilai('tidak ada transaksi dengan id ' + tx_id);
  // Jejak DULU, baru hapus. Kalau penulisan jejak gagal, exception menghentikan
  // fungsi sebelum baris dibuang.
  ST.tambah('terhapus', [{ dihapus_pada: sekarangIso(), transaksi: JSON.stringify(isi) }]);
  ST.hapusDimana('transactions', function (t) { return t.id === isi.id; });
  return isi;
}
