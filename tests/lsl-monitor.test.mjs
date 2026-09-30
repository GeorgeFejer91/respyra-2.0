import test from 'node:test';
import assert from 'node:assert/strict';
import { traceGeometry } from '../web/lsl-monitor.js';

test('live trace holds real timestamps and breaks across sample loss', () => {
  assert.equal(traceGeometry([]).path, '');
  const trace = traceGeometry([[1,5], [1.25,5], [4,6]]);
  assert.equal((trace.path.match(/M/g) || []).length, 2);
  assert.equal((trace.path.match(/L/g) || []).length, 1);
  assert.equal(trace.end, 4);
  assert(!/NaN|Infinity/.test(trace.path));
  assert(!/NaN|Infinity/.test(traceGeometry([[1,5], [1.25,5]]).path));
  const aligned = traceGeometry([[1,5], [1.25,5]], 4);
  assert.equal(aligned.end, 4);
  assert(aligned.path.startsWith('M420.00,'), 'Shared time window aligns separate channel lanes');
  assert.equal(traceGeometry([[1,5]], 20).path, '', 'Old samples leave a blank lane');
});
