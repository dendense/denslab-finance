/**
 * Port bagian hutang dari src/server.py.
 *
 * Dulu:  Data/finance/LIST-HUTANG.md (jadwal, read-only)
 *        Data/finance/HUTANG-LUNAS.json (lapisan status lunas)
 * Sekarang: tab `jadwal_hutang` dan tab `hutang_lunas`.
 *
 * `jadwal_hutang` diisi Deny langsung di Sheet (satu baris = satu cicilan):
 *   nama_utang | nomor | nominal | jatuh_tempo (YYYY-MM-DD) | jatuh_tempo_teks (opsional)
 * Kode ini TIDAK PERNAH menulis ke tab itu — sama seperti LIST-HUTANG.md dulu.
 *
 * Format salah = gagal KERAS dengan pesan yang menyebut barisnya; halaman
 * kosong tanpa keterangan adalah yang dilarang.
 */
var BULAN_PENDEK = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Ags', 'Sep', 'Okt', 'Nov', 'Des'];

function GalatHutang(kode, pesan) {
  var e = new Error(pesan);
  e.kode = kode;
  e.pesan = pesan;
  return e;
}

function _kunciLunas(nama, jt) { return nama + '\u0000' + jt; }

function _baca_lunas() {
  var entri = ST.baca('hutang_lunas');
  entri.forEach(function (e, i) {
    if (!e.nama_utang || !e.jatuh_tempo) {
      throw GalatHutang('hutang_lunas_rusak',
        "Tab hutang_lunas rusak: baris ke-" + (i + 1) + " tidak punya 'nama_utang'/'jatuh_tempo'. " +
        'Penandaan otomatis dilewati.');
    }
  });
  return entri.map(salin);
}

function _tulis_lunas(entri) { ST.gantiSemua('hutang_lunas', entri); }

function _baca_hutang() {
  var baris = ST.baca('jadwal_hutang');
  if (!baris.length) {
    throw GalatHutang('berkas_tidak_ada',
      "Jadwal hutang belum diisi. Isi tab 'jadwal_hutang' di Google Sheet " +
      '(nama_utang, nomor, nominal, jatuh_tempo). Tidak ada yang bisa ditampilkan.');
  }
  var urutNama = [], per = {};
  baris.forEach(function (r, i) {
    var no = i + 2;   // nomor baris di Sheet (baris 1 = header)
    if (!r.nama_utang || !String(r.nama_utang).trim()) {
      throw GalatHutang('format_berubah', 'Baris ' + no + ': nama_utang kosong.');
    }
    if (r.nomor === null || r.nominal === null) {
      throw GalatHutang('format_berubah', 'Baris ' + no + ": 'nomor' dan 'nominal' harus angka.");
    }
    if (!tanggalSah(r.jatuh_tempo)) {
      throw GalatHutang('format_berubah', 'Baris ' + no + ": jatuh_tempo '" + r.jatuh_tempo +
        "' tidak sah (harus YYYY-MM-DD).");
    }
    var nama = String(r.nama_utang).trim();
    if (!per[nama]) { per[nama] = []; urutNama.push(nama); }
    var tg = r.jatuh_tempo;
    per[nama].push({ nomor: r.nomor, nominal: r.nominal, jatuh_tempo: tg,
      jatuh_tempo_teks: r.jatuh_tempo_teks ||
        (parseInt(tg.slice(8), 10) + ' ' + BULAN_PENDEK[parseInt(tg.slice(5, 7), 10) - 1] + ' ' + tg.slice(0, 4)) });
  });

  var hasil = [], totalSemua = 0;
  urutNama.forEach(function (nama) {
    var b = per[nama].slice().sort(function (x, y) {
      return cmp(x.jatuh_tempo, y.jatuh_tempo) || (x.nomor - y.nomor);
    });
    var total = b.reduce(function (s, r) { return s + r.nominal; }, 0);
    totalSemua += total;
    hasil.push({ nama: nama, jumlah_cicilan: b.length, total: total,
      jatuh_tempo_terakhir: b[b.length - 1].jatuh_tempo, baris: b });
  });

  var entri = _baca_lunas();
  var kunci = {};
  entri.forEach(function (e) { kunci[_kunciLunas(e.nama_utang, e.jatuh_tempo)] = e; });
  var peta = {};
  hasil.forEach(function (u) {
    u.baris.forEach(function (r) { peta[_kunciLunas(u.nama, r.jatuh_tempo)] = r; });
  });
  var yatim = entri.filter(function (e) { return !peta[_kunciLunas(e.nama_utang, e.jatuh_tempo)]; })
    .map(function (e) { return [e.nama_utang, e.jatuh_tempo]; })
    .sort(function (a, b) { return cmp(a[0], b[0]) || cmp(a[1], b[1]); });

  var hari = hariIni(), totalLunasSemua = 0;
  hasil.forEach(function (u) {
    var jl = 0, tl = 0;
    u.baris.forEach(function (r) {
      var e = kunci[_kunciLunas(u.nama, r.jatuh_tempo)];
      r.lunas = !!e;
      if (e) {
        r.lunas_pada = e.ditandai_pada;
        r.lunas_transaksi_id = e.transaksi_id;
        jl += 1; tl += r.nominal;
      }
    });
    u.jumlah_lunas = jl;
    u.total_sisa = u.total - tl;
    totalLunasSemua += tl;
    var berikut = null;
    for (var i = 0; i < u.baris.length; i++) {
      var r = u.baris[i];
      if (r.lunas) continue;
      if (r.jatuh_tempo >= hari) {
        berikut = { nomor: r.nomor, nominal: r.nominal, jatuh_tempo: r.jatuh_tempo,
          jatuh_tempo_teks: r.jatuh_tempo_teks };
        break;
      }
    }
    u.cicilan_berikutnya = berikut;
  });

  return { ok: true, sumber: "Google Sheet · tab jadwal_hutang", hari_ini: hari,
    jumlah_utang: hasil.length, total_semua: totalSemua, total_lunas_semua: totalLunasSemua,
    total_sisa_semua: totalSemua - totalLunasSemua, yatim: yatim, utang: hasil };
}

/** Tandai cicilan LUNAS untuk transaksi debt_payment yang baru tersimpan. */
function _tandai_lunas_untuk(items, ids) {
  var hasil = _baca_hutang();
  var entri = _baca_lunas();
  var sudah = {};
  entri.forEach(function (e) { sudah[_kunciLunas(e.nama_utang, e.jatuh_tempo)] = true; });
  var kandidat = [];
  hasil.utang.forEach(function (u) {
    u.baris.forEach(function (r) {
      if (sudah[_kunciLunas(u.nama, r.jatuh_tempo)]) return;
      kandidat.push({ nama_utang: u.nama, jatuh_tempo: r.jatuh_tempo, nomor: r.nomor, nominal: r.nominal });
    });
  });
  kandidat.sort(function (a, b) {
    return cmp(a.jatuh_tempo, b.jatuh_tempo) || cmp(a.nama_utang, b.nama_utang) || (a.nomor - b.nomor);
  });

  var baru = [];
  items.forEach(function (it, i) {
    if ((it.flow_type || '') !== 'debt_payment') return;
    var amount;
    try { amount = pyInt(it.amount); } catch (e) { return; }
    var terpakai = {};
    baru.forEach(function (b) { terpakai[_kunciLunas(b.nama_utang, b.jatuh_tempo)] = true; });
    var pilih = kandidat.filter(function (c) {
      return !terpakai[_kunciLunas(c.nama_utang, c.jatuh_tempo)] && c.nominal === amount;
    })[0];
    if (!pilih) return;
    baru.push({ nama_utang: pilih.nama_utang, jatuh_tempo: pilih.jatuh_tempo, nomor: pilih.nomor,
      nominal: pilih.nominal, ditandai_pada: sekarangIso(), transaksi_id: ids[i],
      transaksi_nominal: amount, transaksi_tanggal: it.occurred_on });
  });
  if (baru.length) _tulis_lunas(entri.concat(baru));
  return baru;
}

function api_debts_batalkan(body) {
  var nama = String(body.nama_utang || '').trim();
  var jt = String(body.jatuh_tempo || '').trim();
  if (!nama || !jt) {
    return { ok: false, error: 'field_kurang', message: "Butuh 'nama_utang' dan 'jatuh_tempo'." };
  }
  var entri;
  try { entri = _baca_lunas(); }
  catch (e) { if (e.kode) return { ok: false, error: e.kode, message: e.pesan }; throw e; }
  var sisa = [], batal = null;
  entri.forEach(function (e) {
    if (e.nama_utang === nama && e.jatuh_tempo === jt) batal = e; else sisa.push(e);
  });
  if (!batal) return { ok: false, error: 'tidak_ditandai', message: 'Cicilan itu tidak sedang ditandai lunas.' };
  _tulis_lunas(sisa);
  return { ok: true, dibatalkan: { nama_utang: batal.nama_utang, jatuh_tempo: batal.jatuh_tempo,
    nomor: batal.nomor, nominal: batal.nominal } };
}

function api_debts() {
  try { return _baca_hutang(); }
  catch (e) { if (e.kode) return { ok: false, error: e.kode, message: e.pesan }; throw e; }
}
