import assert from 'node:assert/strict';
import { test } from 'node:test';
import { invitationUrl, parseInvitation, PANEL, OBSERVE_SCOPE, observerConnectionOptions, validateObserverState } from '../web/remote-profile.js';
import { BRSPConnection } from '../vendor/remote/brsp.js';

const invite = { room: `brsp_${'a'.repeat(64)}`, secret: 'b'.repeat(64) };
const snapshot = { profile: 'respyra.observer/1', revision: 2, phase: 'experiment', inputReady: false,
  event: 'tracking.started', seq: 12, lslTime: 123.5, trial: 2, condition: 'normal', experimentPhase: 'tracking', screen: null };
test('panel and invitation are navigation data with a strictly bounded private fragment', () => {
  const url = invitationUrl(invite);
  assert.deepEqual(parseInvitation(url), invite);
  assert.equal(new URL(PANEL.url).hash, '');
  for (const bad of [url.replace('https:', 'http:'), url.replace('georgefejer91.github.io', 'evil.example'), url + '&extra=x', url.replace('#', '?'), url.replace(invite.secret, 'short')]) assert.equal(parseInvitation(bad), null);
  assert.equal(validateObserverState(snapshot), true);
  assert.equal(validateObserverState({ ...snapshot, participant: 'private' }), false);
  assert.equal(validateObserverState({ ...snapshot, lslTime: NaN }), false);
});

class Lane extends EventTarget {
  sendControl(peerKey, data) { queueMicrotask(() => this.other.dispatchEvent(event('controlmessage', { peerKey, data }))); return true; }
  sendState(peerKey, data) { queueMicrotask(() => this.other.dispatchEvent(event('statemessage', { peerKey, data }))); return true; }
  async stop() {}
}
function event(type, detail) { const value = new Event(type); Object.defineProperty(value, 'detail', { value: detail }); return value; }
function once(source, type) { return new Promise(resolve => source.addEventListener(type, event => resolve(event.detail), { once: true })); }
test('actual BRSP proof returns read-only progress, refuses mutation and withholds state without read scope', { timeout: 3000 }, async () => {
  for (const scopes of [[OBSERVE_SCOPE], []]) {
    const a = new Lane(), b = new Lane(); a.other = b; b.other = a;
    let target;
    target = new BRSPConnection({ transport: a, ...observerConnectionOptions(invite,
      () => target.acceptedScopes.includes(OBSERVE_SCOPE) ? snapshot : undefined) });
    const controller = new BRSPConnection({ transport: b, role: 'controller', sessionId: invite.room,
      sharedSecret: invite.secret, requestedScopes: scopes });
    let states = 0;
    controller.addEventListener('state', () => states++);
    const ready = once(controller, 'ready');
    const received = scopes.length ? once(controller, 'snapshot') : null;
    a.dispatchEvent(event('peeropen', { peerKey: 'fixture' }));
    b.dispatchEvent(event('peeropen', { peerKey: 'fixture' }));
    await ready;
    if (received) assert.deepEqual((await received).state, snapshot);
    if (scopes.length) {
      const applied = once(controller, 'commandapplied');
      controller.sendCommand(OBSERVE_SCOPE, 'start', {});
      assert.equal((await applied).ok, false);
    } else assert.throws(() => controller.sendCommand(OBSERVE_SCOPE, 'start', {}), /not granted/u);
    await new Promise(done => setTimeout(done, 10));
    if (!scopes.length) assert.equal(states, 0);
    await controller.close(); await target.close();
  }
});
