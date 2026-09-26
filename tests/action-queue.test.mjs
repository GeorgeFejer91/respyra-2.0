import test from 'node:test';
import assert from 'node:assert/strict';
import { actionQueue } from '../web/action-queue.js';

test('actions capture time immediately and arrive in order despite asynchronous IPC', async () => {
  let release, clock = 10;
  const calls = [];
  const block = new Promise(resolve => { release = resolve; });
  const send = actionQueue(async (command, args) => {
    assert.equal(command, 'setup_action');
    calls.push(args.action);
    if (calls.length === 1) await block;
  }, error => { throw error; }, () => clock++);
  send('shown');
  const last = send('field_edit', { field: 'participant', value: 'p' });
  await Promise.resolve();
  assert.equal(calls.length, 1);
  release(); await last;
  assert.deepEqual(calls.map(a => [a.action, a.ui_seq, a.ui_time_ms]), [['shown', 1, 10], ['field_edit', 2, 11]]);
});

test('IPC error stops subsequent input instead of claiming delivery', async () => {
  let calls = 0, failures = 0;
  const send = actionQueue(async () => { calls++; throw Error('pipe closed'); }, () => failures++);
  send('shown'); await send('scan');
  assert.equal(calls, 1); assert.equal(failures, 1);
});

test('bounded queue fails explicitly on overload', async () => {
  let failures = 0;
  const send = actionQueue(async () => {}, () => failures++);
  for (let i = 0; i < 130; i++) send('scan');
  await send('scan'); assert.equal(failures, 1);
});
