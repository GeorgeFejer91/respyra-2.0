import { BRSPConnection } from './vendor/brsp.js';
import { VdoNinjaTransport } from './vendor/vdo-ninja-transport.js';
import { createEmbeddedVdoSdk } from './vendor/external-page-connector.js';
import { parseInvitation, SCOPES, OBSERVE_SCOPE, scopeForAction, validateControllerState, validViewerName } from './remote-profile.js';
import { measureTextRegions } from './text-fit.js';
import { actionQueue } from './action-queue.js';
import { mountController } from './controller-ui.js';

const byId = id => document.getElementById(id);
let invitation = parseInvitation(location.href), active, linkGeneration = 0;
function scrubInvitation() {
  if (!location.hash) return;
  try { history.replaceState(null, '', location.pathname + location.search); }
  catch { location.replace('#'); }
}
scrubInvitation();
window.addEventListener('hashchange', () => {
  const next = parseInvitation(location.href);
  scrubInvitation();
  if (!next) return;
  void stop().then(generation => {
    if (generation !== linkGeneration) return;
    invitation = next;
    byId('invitation-field').hidden = true;
    byId('invitation').required = false;
    byId('connection-status').textContent = 'Private invitation received. Enter your name to request access.';
  });
});
const controller = mountController(byId('controller'), (action, fields) => active?.send(action, fields));
byId('controller').querySelector('.diagnostics').append(byId('route'));
controller.setEnabled(false);
measureTextRegions().catch(() => { document.documentElement.dataset.pretextFit = 'unavailable'; });
if (invitation) byId('connection-status').textContent = 'Private invitation received. Enter your name to request access.';
byId('pairing').addEventListener('submit', event => { event.preventDefault(); void connect(); });
byId('disconnect').addEventListener('click', () => { void stop(); });
window.addEventListener('pagehide', () => { void stop(); });
document.addEventListener('visibilitychange', () => { if (document.hidden && active) void stop(); });

async function stop(message = 'Disconnected. Enable a fresh phone invitation in Respyra to reconnect.') {
  const generation = ++linkGeneration;
  const context = active;
  active = undefined;
  invitation = null;
  controller.setEnabled(false);
  controller.clearMonitor();
  document.body.classList.remove('coupled');
  byId('pairing-note').hidden = false;
  byId('controller').hidden = true;
  controller.clearSetup();
  byId('streams').replaceChildren();
  byId('invitation').value = '';
  byId('invitation').required = true;
  byId('invitation').disabled = false;
  byId('connect').disabled = false; byId('connect').hidden = false;
  byId('invitation-field').hidden = false;
  byId('viewer-name-field').hidden = false;
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
  return generation;
}

async function connect() {
  if (active) return;
  const viewerName = byId('viewer-name').value.trim();
  if (!validViewerName(viewerName)) { byId('connection-status').textContent = 'Enter a name of up to 64 characters.'; byId('viewer-name').focus(); return; }
  invitation = parseInvitation(byId('invitation').value) ?? invitation;
  if (!invitation) { byId('connection-status').textContent = 'Paste a fresh private control link from Respyra.'; return; }
  byId('invitation').value = '';
  byId('invitation-field').hidden = true;
  byId('viewer-name-field').hidden = true;
  const context = { route:'unknown', name:viewerName, lastState:0, started:performance.now(), revision:0,
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
      document.body.classList.add('coupled');
      byId('pairing-note').hidden = true;
      byId('route').textContent = 'Phone route: ' + context.route;
      byId('connection-status').textContent = 'Connected to Respyra';
    };
    context.connection.addEventListener('snapshot', event => state(event.detail.state));
    context.connection.addEventListener('state', event => state(event.detail.state));
    context.connection.addEventListener('ready', () => {
      context.approvalStarted = performance.now();
      context.connection.sendCommand(OBSERVE_SCOPE, 'introduce', { name:context.name });
      byId('connection-status').textContent = 'Waiting for approval on the Respyra desktop…';
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
      if (context.lastState && context.connection.phase === 'ready' && now - context.lastRenew >= 1000) {
        context.connection.sendCommand(OBSERVE_SCOPE,'renew'); context.lastRenew = now;
      }
      if (context.lastState && now - context.lastState > 2000) {
        controller.setEnabled(false);
        byId('connection-status').textContent = 'No recent updates. Controls paused; check the local controller.';
      }
      if (context.lastState && now - context.lastState > 6000) void stop();
      if (!context.lastState && context.approvalStarted && now - context.approvalStarted > 60000) void stop('Desktop approval expired. Create a fresh QR code in Respyra.');
      if (!context.lastState && !context.approvalStarted && now - context.started > 30000) void stop('Respyra did not respond. Create a fresh QR code and try again.');
    }, 250);
    await context.transport.start();
  } catch { if (active === context) await stop('Connection failed. Enable a fresh phone session and try again.'); }
}

byId('invitation').required = !invitation;
byId('invitation-field').hidden = Boolean(invitation);
// A private QR/link pre-fills the invitation. The phone enters a name before requesting access.
// A restored base page (including Recorder's saved tabs) remains disconnected.
