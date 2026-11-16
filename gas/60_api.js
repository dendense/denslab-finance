/**
 * Port handler rute src/server.py. Bentuk balasan SAMA dengan server Python,
 * supaya web/app.js tidak perlu tahu sedang bicara dengan backend yang mana.
 *
 * `params` = query string sebagai {nama: [nilai]} (bentuk parse_qs Python).
 */
function _p(params, nama, bawaan) {
  var v = (params[nama] || [])[0];
  return v === undefined || v === '' ? (bawaan === undefined ? null : bawaan) : v;
}

function api_summary(params) {
  var ms = monthly_summary(_p(params, 'month'));
  var nw = net_worth();
  return {
    month: ms.month, ada_data: ms._ada_data, tx_count: ms.tx_count,
    net_worth: { total: nw.net_worth, liquid: nw.liquid, non_liquid: nw.non_liquid,
      account_count: nw.account_count, account_count_all: nw.account_count_all,
      balance_inactive: nw.balance_inactive },
    flow: { total_in: ms.total_in, total_out: ms.total_out, expense_real: ms.expense_real,
      receivable_out: ms.receivable_out, debt_payment_out: ms.debt_payment_out,
      net: ms.net, net_real: ms.net_real },
    accounts: account_balances(false).map(function (a) {
      return { id: a.id, name: a.name, kind: a.kind, balance: a.balance, is_active: a.is_active };
    }),
  };
}

function api_transactions(params) {
  var month = _p(params, 'month');
  var lim = _p(params, 'limit');
  var rows = list_transactions(month, lim ? pyInt(lim) : null, _p(params, 'direction'));
  return { month: month, count: rows.length, items: rows };
}

function api_transaction_patch(txId, body) {
  if (!benar(body)) return { ok: false, error: 'tidak_ada_perubahan', message: 'Tidak ada field yang dikirim.' };
  if ('direction' in body) {
    return { ok: false, error: 'field_terkunci', message: "Kolom 'direction' tidak bisa diubah " +
      "langsung — ubah 'flow_type', arahnya mengikuti." };
  }
  var hasil;
  try { hasil = update_transaction(txId, body); }
  catch (e) {
    if (!e.nilai) throw e;
    var p = e.message, kode;
    if (p.indexOf('tidak ada transaksi') >= 0) kode = 'transaksi_tidak_ada';
    else if (p.indexOf('flow_type') >= 0 && p.indexOf('dikenal') >= 0) kode = 'pasangan_tidak_sah';
    else if (p.indexOf('kategori') >= 0) kode = 'kategori_tidak_dikenal';
    else if (p.indexOf('nominal') >= 0) kode = 'amount_bukan_angka';
    else if (p.indexOf('akun') >= 0) kode = 'akun_tidak_ditemukan';
    else if (p.indexOf('terkunci') >= 0) kode = 'field_terkunci';
    else kode = 'gagal_ubah';
    return { ok: false, error: kode, message: p };
  }
  if (!hasil.source) hasil.source = 'manual';
  var o = { ok: true };
  Object.keys(hasil).forEach(function (k) { o[k] = hasil[k]; });
  return o;
}

function api_transaction_delete(txId) {
  var hasil;
  try { hasil = delete_transaction(txId); }
  catch (e) {
    if (!e.nilai) throw e;
    return { ok: false, error: 'transaksi_tidak_ada', message: e.message };
  }
  return { ok: true, id: txId, dihapus: true, pemulihan: "Google Sheet · tab terhapus",
    transaksi: hasil };
}

function api_parse(body) { return parse_kontrak(body.text); }

function api_save(body) {
  var items = body.transactions || [];
  if (!items.length) return { ok: false, error: 'kosong', message: 'Tidak ada yang disimpan.' };
  var wajib = ['occurred_on', 'direction', 'amount'];
  for (var i = 0; i < items.length; i++) {
    for (var j = 0; j < wajib.length; j++) {
      if (!benar(items[i][wajib[j]])) {
        return { ok: false, error: 'field_kurang',
          message: 'Transaksi ke-' + (i + 1) + " tidak punya '" + wajib[j] + "'." };
      }
    }
  }
  var ids;
  try { ids = save_transactions(items); }
  catch (e) { return { ok: false, error: 'gagal_simpan', message: e.message }; }
  var lunas = [];
  try { lunas = _tandai_lunas_untuk(items, ids); }
  catch (e) { console.log('[hutang-lunas] penandaan otomatis dilewati: ' + e.message); }
  var hasil = { ok: true, saved_ids: ids, count: ids.length };
  if (lunas.length) hasil.hutang_lunas = lunas;
  return hasil;
}

function api_categories(params) {
  var items = get_categories(_p(params, 'direction'));
  return { count: items.length, items: items };
}

function api_accounts(params) {
  var all = ['1', 'true', 'ya'].indexOf(_p(params, 'all', '0')) >= 0;
  var items = account_balances(all);
  return { count: items.length, items: items };
}

var KIND_SAH = ['bank', 'cash', 'ewallet', 'savings', 'investment'];

function api_account_create(body) {
  var name = String(body.name || '').trim();
  if (!name) return { ok: false, error: 'nama_kosong', message: 'Nama akun tidak boleh kosong.' };
  var kind = String(body.kind || '').trim().toLowerCase();
  if (KIND_SAH.indexOf(kind) < 0) {
    return { ok: false, error: 'jenis_tidak_dikenal', message: "Jenis '" + (kind || '-') +
      "' tidak dikenal. Pilihan: " + KIND_SAH.join(', ') + '.' };
  }
  var saldo = 'opening_balance' in body ? body.opening_balance : 0;
  var tipe = typeof saldo;
  if (tipe === 'boolean' || !(tipe === 'number' || tipe === 'string')) {
    return { ok: false, error: 'saldo_awal_bukan_angka', message: 'Saldo awal harus angka bulat rupiah.' };
  }
  try { saldo = bulatRupiah(saldo); }
  catch (e) { return { ok: false, error: 'saldo_awal_bukan_angka', message: 'Saldo awal harus angka bulat rupiah.' }; }
  var hasil;
  try { hasil = create_account(name, kind, saldo); }
  catch (e) {
    if (!e.nilai) throw e;
    return { ok: false, error: e.message.toLowerCase().indexOf('sudah ada') >= 0 ? 'nama_sudah_ada' : 'gagal_simpan',
      message: e.message };
  }
  return Object.assign({ ok: true }, hasil);
}

function api_account_patch(accountId, body) {
  var kunci = [];
  if ('kind' in body) kunci.push('kind');
  if ('opening_balance' in body) kunci.push('opening_balance');
  if (kunci.length) {
    return { ok: false, error: 'field_terkunci', message: 'Kolom ' +
      kunci.map(function (f) { return "'" + f + "'"; }).join(' dan ') +
      ' tidak bisa diubah setelah akun dibuat — keduanya mengubah angka kekayaan tanpa ' +
      'transaksi. Perbaikannya lewat migrasi yang tercatat.' };
  }
  var name = body.name === undefined || body.name === null ? null : String(body.name).trim();
  if (name !== null && !name) return { ok: false, error: 'nama_kosong', message: 'Nama akun tidak boleh kosong.' };
  var aktif = body.is_active === undefined || body.is_active === null ? null
    : ([1, true, '1', 'true', 'ya'].indexOf(body.is_active) >= 0 ? 1 : 0);
  if (name === null && aktif === null) {
    return { ok: false, error: 'tidak_ada_perubahan',
      message: "Tidak ada field yang bisa diubah. Kirim 'name' atau 'is_active'." };
  }
  var hasil;
  try { hasil = update_account(accountId, name, aktif); }
  catch (e) {
    if (!e.nilai) throw e;
    var p = e.message.toLowerCase();
    return { ok: false, error: p.indexOf('tidak ada akun') >= 0 ? 'akun_tidak_ada'
      : p.indexOf('sudah ada') >= 0 ? 'nama_sudah_ada' : 'gagal_simpan', message: e.message };
  }
  return Object.assign({ ok: true }, hasil);
}

function api_trend(params) {
  var m = parseInt(_p(params, 'months', '6'), 10);
  if (isNaN(m)) m = 6;
  return monthly_trend(Math.max(1, Math.min(m, 24)));
}

function api_categories_spending(params) {
  return spending_by_category(_p(params, 'month'), _p(params, 'direction', 'out'));
}

function api_suggestions(params) { return saving_suggestions(_p(params, 'month')); }

function api_analysis(params) {
  return analisa_lengkap(_p(params, 'month') || bulanSebelum(bulanBerjalan()));
}

function api_analysis_create(body) {
  var month = String(body.month || '').trim();
  if (!month) return { ok: false, error: 'bulan_kosong', message: 'Sebutkan bulan yang mau dianalisa, format YYYY-MM.' };
  if (!/^\d{4}-\d{2}$/.test(month)) return { ok: false, error: 'bulan_tidak_sah', message: 'Format bulan harus YYYY-MM, contoh: 2026-10.' };
  if (!bulan_sudah_selesai(month)) {
    return { ok: false, error: 'bulan_belum_selesai', message: 'Bulan ' + namaBulan(month) +
      ' belum selesai, jadi belum bisa dianalisa. Angkanya masih bisa berubah.' };
  }
  var analisa = analisa_lengkap(month);
  if (!analisa.angka.ada_data) {
    return { ok: false, error: 'tidak_ada_data', message: 'Tidak ada transaksi di ' + namaBulan(month) +
      ', tidak ada yang bisa dianalisa.' };
  }
  var narasi = buat_narasi(analisa);
  var a = analisa.angka;
  var hasil = simpan_analisa(month, narasi,
    { masuk: a.masuk, keluar_semua: a.keluar_semua, konsumsi: a.konsumsi,
      sisa_bebas: a.sisa_bebas, tx_count: a.tx_count },
    narasi.catatan ? null : konfigAI().model, narasi.catatan);
  return Object.assign({ ok: true }, hasil);
}

function api_analysis_delete(month) {
  if (!/^\d{4}-\d{2}$/.test(month)) return { ok: false, error: 'bulan_tidak_sah', message: 'Format bulan harus YYYY-MM.' };
  if (!hapus_analisa(month)) return { ok: false, error: 'tidak_ada_analisa', message: 'Belum ada analisa untuk bulan itu.' };
  return { ok: true, month: month, dihapus: true };
}

function api_months() { return daftar_bulan(); }

function api_savings() {
  var t = target_aktif();
  return {
    ada_target: t !== null, target: t,
    akun_bisa_dipakai: account_balances(true)
      .filter(function (a) { return KIND_TIDAK_LIKUID.indexOf(a.kind) >= 0; })
      .map(function (a) { return { id: a.id, name: a.name, kind: a.kind, balance: a.balance }; }),
    catatan: 'Progres dihitung dari SALDO AKUN target, bukan dari total kekayaan. Uang yang ' +
      'disimpan di akun lain tidak ikut terhitung.',
  };
}

function api_savings_set(body) {
  var name = String(body.name || '').trim();
  if (!name) return { ok: false, error: 'nama_kosong', message: 'Nama target tidak boleh kosong.' };
  if (body.target_amount === undefined || body.target_amount === null) {
    return { ok: false, error: 'target_kosong', message: 'Target harus diisi, angka bulat rupiah.' };
  }
  var hasil;
  try {
    hasil = set_target(name, body.target_amount, body.account_hint, body.account_id, body.target_date);
  } catch (e) {
    if (!e.nilai) throw e;
    var p = e.message;
    return { ok: false, error: p.indexOf('akun') >= 0 ? 'akun_tidak_ditemukan'
      : p.indexOf('tanggal') >= 0 ? 'tanggal_tidak_sah' : 'target_tidak_sah', message: p };
  }
  return { ok: true, target: hasil };
}

function api_savings_delete() {
  if (!hapus_target()) return { ok: false, error: 'tidak_ada_target', message: 'Belum ada target tabungan yang aktif.' };
  return { ok: true, diarsipkan: true };
}
