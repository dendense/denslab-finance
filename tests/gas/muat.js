/**
 * Muat semua berkas gas/*.js ke satu konteks `vm` — meniru ruang nama global
 * Apps Script — dengan pengganti untuk layanan Google yang tidak ada di Node.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const crypto = require('crypto');

const GAS = path.resolve(__dirname, '..', '..', 'gas');

function muat(opsi) {
  opsi = opsi || {};
  const ctx = vm.createContext({
    console: { log() {}, error() {} },
    HARI_INI_UJI: opsi.hariIni || null,
    KONFIG_UJI: Object.assign({ KENARI_API_KEY: 'kunci-uji' }, opsi.konfig || {}),
    HTTP_UJI: opsi.http || null,
    SHA256_UJI: (s) => crypto.createHash('sha256').update(s, 'utf8').digest('hex'),
    ACAK_UJI: () => crypto.randomBytes(32).toString('hex'),
  });
  fs.readdirSync(GAS).filter((f) => f.endsWith('.js')).sort().forEach((f) => {
    vm.runInContext(fs.readFileSync(path.join(GAS, f), 'utf8'), ctx, { filename: f });
  });
  return ctx;
}

module.exports = { muat };
