'use strict';

function isWide(cp) {
  return (
    (cp >= 0x1100 && cp <= 0x115f) ||
    (cp >= 0x2e80 && cp <= 0x303e) ||
    (cp >= 0x3041 && cp <= 0x33ff) ||
    (cp >= 0x3400 && cp <= 0x4dbf) ||
    (cp >= 0x4e00 && cp <= 0x9fff) ||
    (cp >= 0xa000 && cp <= 0xa4cf) ||
    (cp >= 0xac00 && cp <= 0xd7a3) ||
    (cp >= 0xf900 && cp <= 0xfaff) ||
    (cp >= 0xfe30 && cp <= 0xfe4f) ||
    (cp >= 0xff00 && cp <= 0xff60) ||
    (cp >= 0xffe0 && cp <= 0xffe6) ||
    (cp >= 0x20000 && cp <= 0x3fffd)
  );
}

function width(s) {
  let w = 0;
  for (const ch of s) w += isWide(ch.codePointAt(0)) ? 2 : 1;
  return w;
}

function cell(v) {
  if (v === null || v === undefined) return '';
  return String(v).replace(/\|/g, '\\|').replace(/\r\n|\n/g, '<br>');
}

function pad(text, w, align) {
  const gap = w - width(text);
  if (align === 'right') return ' '.repeat(gap) + text;
  if (align === 'center') {
    const left = Math.floor(gap / 2);
    return ' '.repeat(left) + text + ' '.repeat(gap - left);
  }
  return text + ' '.repeat(gap);
}

function formatTable(rows, { align = [] } = {}) {
  if (!Array.isArray(rows) || rows.length === 0) throw new TypeError('rows must be a non-empty array');
  const ncols = Math.max(...rows.map((r) => r.length));
  const grid = rows.map((r) => Array.from({ length: ncols }, (_, i) => cell(r[i])));
  const widths = Array.from({ length: ncols }, (_, i) => Math.max(3, ...grid.map((r) => width(r[i]))));
  const aligns = widths.map((_, i) => align[i] || 'left');
  const line = (cells) => '| ' + cells.join(' | ') + ' |';
  const sep = widths.map((w, i) => {
    const a = aligns[i];
    if (a === 'center') return ':' + '-'.repeat(w - 2) + ':';
    if (a === 'right') return '-'.repeat(w - 1) + ':';
    return ':' + '-'.repeat(w - 1);
  });
  const body = grid.map((r) => line(r.map((c, i) => pad(c, widths[i], aligns[i]))));
  return [body[0], line(sep), ...body.slice(1)].join('\n');
}

module.exports = { formatTable, width };
