import assert from 'node:assert/strict';
import { filterPointsByWindow, nearestPointIndex } from './upbit-chart-utils.mjs';

const points = [
  { time: '2026-05-08T00:00:00+09:00', navAfter: 100 },
  { time: '2026-05-08T01:00:00+09:00', navAfter: 105 },
  { time: '2026-05-08T02:00:00+09:00', navAfter: 103 },
  { time: '2026-05-08T03:00:00+09:00', navAfter: 110 },
];

assert.deepEqual(filterPointsByWindow(points, 'all'), points);
assert.deepEqual(filterPointsByWindow(points, '2h').map((p) => p.time), [
  '2026-05-08T01:00:00+09:00',
  '2026-05-08T02:00:00+09:00',
  '2026-05-08T03:00:00+09:00',
]);
assert.deepEqual(filterPointsByWindow(points, '1h').map((p) => p.time), [
  '2026-05-08T02:00:00+09:00',
  '2026-05-08T03:00:00+09:00',
]);

assert.equal(nearestPointIndex([10, 20, 40, 90], 38), 2);
assert.equal(nearestPointIndex([10, 20, 40, 90], 14), 0);
assert.equal(nearestPointIndex([], 14), -1);

console.log('upbit chart utility tests passed');
