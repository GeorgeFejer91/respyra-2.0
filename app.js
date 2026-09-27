import { BRSPConnection } from './vendor/brsp.js';
import { VdoNinjaTransport } from './vendor/vdo-ninja-transport.js';
import { createEmbeddedVdoSdk } from './vendor/external-page-connector.js';
import { parseInvitation, SCOPES, OBSERVE_SCOPE, scopeForAction, validateControllerState } from './remote-profile.js';
import { measureTextRegions } from './text-fit.js';
import { actionQueue } from './action-queue.js';
import { mountController } from './controller-ui.js';

const byId = id => document.getElementById(id);
let invitation = parseInvitation(location.href), active;
if (location.hash) {
  try { history.replaceState(null, '', location.pathname + location.search); }
  catch { location.replace('#'); }
}
const controller = mountController(byId('controller'), (action, fields) => active?.send(action, fields));
byId('controller').querySelector('.diagnostics').append(byId('route'));
controller.setEnabled(false);
byId('remote-view').addEventListener('change', () => { document.body.dataset.view = byId('remote-view').value; });
measureTextRegions().catch(() => { document.documentElement.dataset.pretextFit = 'unavailable'; });
if (invitation) byId('connection-status').textContent = 'Private invitation received. Select Connect to control Respyra.';
byId('pairing').addEventListener('submit', event => { event.preventDefault(); void connect(); });
byId('disconnect').addEventListener('click', () => { void stop(); });
window.addEventListener('pagehide', () => { void stop(); });
document.addEventListener('visibilitychange', () => { if (document.hidden && active) void stop(); });

async function stop(message = 'Disconnected. Enable a fresh phone invitation in Respyra to reconnect.') {
  const context = active;
  active = undefined;
  invitation = null;
  controller.setEnabled(false);
  controller.clearMonitor();
  byId('remote-view-picker').hidden = true;
  document.body.classList.remove('coupled');
  byId('pairing-note').hidden = false;
  byId('controller').hidden = true;
  byId('participant').value = ''; byId('session').value = '';
  byId('streams').replaceChildren();
  byId('invitation').value = '';
  byId('invitation').required = true;
  byId('invitation').disabled = false;
  byId('connect').disabled = false; byId('connect').hidden = false;
  byId('invitation-field').hidden = false;
  byId('disconnect').disabled = true;
  byId('connection-status').textContent = message;
  byId('route').textContent = '';
  clearInterval(context?.timer);
  for (const pending of context?.pending.values() || []) {
    clearTimeout(pending.timer);
    pending.reject(new Error('Connection ended; command outcome may be unknown. Check the local controller.'));
  }
  context?.pending.clear();
  await context?.connection?.close();
}

async function connect() {
  if (active) return;
  invitation = parseInvitation(byId('invitation').value) ?? invitation;
  if (!invitation) { byId('connection-status').textContent = 'Paste a fresh private control link from Respyra.'; return; }
  byId('invitation').value = '';
  byId('invitation-field').hidden = true;
  const context = { route:'unknown', lastState:0, started:performance.now(), revision:0,
    monitorRevision:0, pending:new Map(), lastRenew:0 };
  active = context;
  context.send = actionQueue(async (_command, { action:payload }) => {
    if (active !== context || context.connection.phase !== 'ready' || performance.now() - context.lastState > 2000) {
      throw new Error('No fresh connection. Check the local controller.');
    }
    const scope = scopeForAction(payload.action);
    if (!scope) throw new Error('Unsupported control');
    const { action, ...args } = payload;
    return new Promise((resolve,reject) => {
      const id = context.connection.sendCommand(scope, action, action === 'close' ? {} : args, { expectedRevision:context.revision });
      const timer = setTimeout(() => {
        context.pending.delete(id);
        reject(new Error('Command outcome unknown. Check the local controller before trying again.'));
      }, 30000);
      context.pending.set(id, { resolve,reject,timer });
    });
  }, error => { controller.fail(String(error)); void stop(String(error)); });
  byId('connect').disabled = true; byId('invitation').disabled = true; byId('disconnect').disabled = false;
  byId('connection-status').textContent = 'Connecting to Respyra…';
  try {
    context.transport = new VdoNinjaTransport({ role:'controller', room:invitation.room, sharedSecret:invitation.secret,
      label:'Respyra experiment control', sdkFactory:createEmbeddedVdoSdk });
    context.connection = new BRSPConnection({ transport:context.transport, role:'controller',
      sessionId:invitation.room, sharedSecret:invitation.secret,
      requestedScopes:SCOPES, capabilities:['command-ack','state-snapshot','latest-state'] });
    const state = value => {
      if (active !== context || !SCOPES.every(scope => context.connection.acceptedScopes.includes(scope))) return;
      if (!validateControllerState(value)) { void stop('Invalid controller state. Enable a fresh invitation.'); return; }
      if (value.revision < context.revision || value.monitorRevision < context.monitorRevision) return;
      context.revision = value.revision; context.monitorRevision = value.monitorRevision;
      context.lastState = performance.now();
      controller.render({ ...(value.setup || {}), phase:value.phase, message:value.message, progress:value.progress });
      controller.setEnabled(value.phase !== 'setup' || value.setup !== null);
      byId('controller').hidden = false; byId('connect').hidden = true;
      byId('remote-view-picker').hidden = false;
      document.body.classList.add('coupled');
      byId('pairing-note').hidden = true;
      byId('route').textContent = 'Phone route: ' + context.route;
      byId('connection-status').textContent = 'Connected to Respyra';
    };
    context.connection.addEventListener('snapshot', event => state(event.detail.state));
    context.connection.addEventListener('state', event => state(event.detail.state));
    context.connection.addEventListener('ready', () => {
      context.connection.sendCommand(OBSERVE_SCOPE,'renew');
      context.lastRenew = performance.now();
    });
    context.connection.addEventListener('commandapplied', event => {
      if (active !== context) return;
      const result = event.detail, pending = context.pending.get(result.commandId);
      if (!pending) return;
      clearTimeout(pending.timer); context.pending.delete(result.commandId);
      context.revision = Math.max(context.revision, result.revision);
      if (!result.ok && /outcome unknown/i.test(result.error || '')) {
        pending.reject(new Error(result.error));
        return;
      }
      pending.resolve(result);
    });
    context.transport.addEventListener('quality', event => { context.route = event.detail.route; });
    context.connection.addEventListener('phasechange', event => {
      if (active === context && ['disconnected','closed','error'].includes(event.detail.phase)) void stop();
    });
    context.timer = setInterval(() => {
      if (active !== context) return;
      const now = performance.now();
      if (context.connection.phase === 'ready' && now - context.lastRenew >= 1000) {
        context.connection.sendCommand(OBSERVE_SCOPE,'renew'); context.lastRenew = now;
      }
      if (now - (context.lastState || context.started) > 2000) {
        controller.setEnabled(false);
        byId('connection-status').textContent = 'No recent updates. Controls paused; check the local controller.';
      }
      if (context.lastState && now - context.lastState > 6000) void stop();
      if (!context.lastState && now - context.started > 30000) void stop('Respyra did not respond. Enable a fresh phone session and try again.');
    }, 250);
    await context.transport.start();
  } catch { if (active === context) await stop('Connection failed. Enable a fresh phone session and try again.'); }
}

byId('invitation').required = !invitation;
byId('invitation-field').hidden = Boolean(invitation);
