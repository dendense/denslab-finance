/**
 * Tiruan SpreadsheetApp/PropertiesService secukupnya untuk StoreSheet.
 *
 * Yang ditiru dengan sengaja — karena itu sumber bug nyata di Sheets:
 *   - teks tanpa apostrof yang terlihat seperti angka -> jadi angka
 *   - teks tanpa apostrof yang terlihat seperti tanggal -> jadi Date
 *   - teks berawalan '=' tanpa apostrof -> dianggap rumus (ditandai '#RUMUS')
 *   - apostrof di depan tidak ikut terbaca kembali
 */
'use strict';

function ubahSeperti_Sheets(v) {
  if (typeof v !== 'string') return v;
  if (v.charAt(0) === "'") return v.slice(1);
  if (v === '') return '';
  if (v.charAt(0) === '=') return '#RUMUS';
  if (/^-?\d+(\.\d+)?$/.test(v)) return Number(v);
  const m = /^(\d{4})-(\d{2})-(\d{2})( \d{2}:\d{2}:\d{2})?$/.exec(v);
  if (m) return new Date(m[1] + '-' + m[2] + '-' + m[3] + 'T' + (m[4] ? m[4].trim() : '00:00:00') + '+07:00');
  return v;
}

class Rentang {
  constructor(sh, r, c, nr, nc) { Object.assign(this, { sh, r, c, nr, nc }); }
  getValues() {
    const out = [];
    for (let i = 0; i < this.nr; i++) {
      const baris = [];
      for (let j = 0; j < this.nc; j++) {
        const row = this.sh.grid[this.r - 1 + i] || [];
        const v = row[this.c - 1 + j];
        baris.push(v === undefined ? '' : v);
      }
      out.push(baris);
    }
    return out;
  }
  setValues(vals) {
    if (vals.length !== this.nr || vals.some((b) => b.length !== this.nc)) {
      throw new Error('ukuran setValues tidak cocok dengan rentang');
    }
    vals.forEach((b, i) => {
      const ri = this.r - 1 + i;
      this.sh.grid[ri] = this.sh.grid[ri] || [];
      b.forEach((v, j) => { this.sh.grid[ri][this.c - 1 + j] = ubahSeperti_Sheets(v); });
    });
    return this;
  }
  clearContent() {
    for (let i = 0; i < this.nr; i++) {
      const row = this.sh.grid[this.r - 1 + i];
      if (row) for (let j = 0; j < this.nc; j++) row[this.c - 1 + j] = '';
    }
    return this;
  }
  setFontWeight() { return this; }
}

class Lembar {
  constructor(nama) { this.nama = nama; this.grid = []; }
  getRange(r, c, nr, nc) { return new Rentang(this, r, c, nr || 1, nc || 1); }
  _isi(row) { return row && row.some((v) => v !== '' && v !== undefined); }
  getLastRow() {
    for (let i = this.grid.length - 1; i >= 0; i--) if (this._isi(this.grid[i])) return i + 1;
    return 0;
  }
  getLastColumn() {
    let m = 0;
    this.grid.forEach((row) => row.forEach((v, j) => { if (v !== '' && v !== undefined) m = Math.max(m, j + 1); }));
    return m;
  }
  setFrozenRows() {}
}

class SpreadsheetPalsu {
  constructor() { this.lembar = {}; }
  getSheetByName(n) { return this.lembar[n] || null; }
  insertSheet(n) { return (this.lembar[n] = new Lembar(n)); }
}

function propertiesPalsu() {
  const p = {};
  return { getScriptProperties: () => ({
    getProperty: (k) => (k in p ? p[k] : null),
    setProperty: (k, v) => { p[k] = String(v); },
  }) };
}

module.exports = { SpreadsheetPalsu, propertiesPalsu };
