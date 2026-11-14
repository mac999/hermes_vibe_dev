const test = require('node:test');
const assert = require('node:assert/strict');
const { formatTable } = require('./mdtable');

test('basic left aligned', () => {
  assert.equal(
    formatTable([['name', 'qty'], ['apple', 3], ['kiwi', 12]]),
    ['| name  | qty |', '| :---- | :-- |', '| apple | 3   |', '| kiwi  | 12  |'].join('\n'),
  );
});

test('alignment row and padding', () => {
  const out = formatTable([['a', 'b', 'c'], ['x', 'yy', 'zzzzz']], { align: ['left', 'center', 'right'] });
  assert.equal(out, [
    '| a   |  b  |     c |',
    '| :-- | :-: | ----: |',
    '| x   | yy  | zzzzz |',
  ].join('\n'));
});

test('center odd padding goes right', () => {
  const out = formatTable([['abcd'], ['x']], { align: ['center'] });
  assert.equal(out, ['| abcd |', '| :--: |', '|  x   |'].join('\n'));
});

test('ragged rows and null cells', () => {
  const out = formatTable([['h1', 'h2', 'h3'], ['a'], [null, undefined, 'c']]);
  assert.equal(out, [
    '| h1  | h2  | h3  |',
    '| :-- | :-- | :-- |',
    '| a   |     |     |',
    '|     |     | c   |',
  ].join('\n'));
});

test('header shorter than body row', () => {
  const out = formatTable([['h'], ['a', 'b']]);
  assert.equal(out, ['| h   |     |', '| :-- | :-- |', '| a   | b   |'].join('\n'));
});

test('escape pipe and newlines', () => {
  const out = formatTable([['k'], ['a|b'], ['l1\nl2'], ['r1\r\nr2']]);
  assert.equal(out, [
    '| k        |',
    '| :------- |',
    '| a\\|b     |',
    '| l1<br>l2 |',
    '| r1<br>r2 |',
  ].join('\n'));
});

test('east asian wide characters count as 2', () => {
  const out = formatTable([['이름', 'x'], ['홍길동', 'abc'], ['漢字かな', 'Ｆ']], { align: ['right', 'left'] });
  assert.equal(out, [
    '|     이름 | x   |',
    '| -------: | :-- |',
    '|   홍길동 | abc |',
    '| 漢字かな | Ｆ  |',
  ].join('\n'));
});

test('no trailing newline', () => {
  assert.ok(!formatTable([['a']]).endsWith('\n'));
});

test('invalid input', () => {
  assert.throws(() => formatTable([]), TypeError);
  assert.throws(() => formatTable('x'), TypeError);
  assert.throws(() => formatTable(null), TypeError);
});
