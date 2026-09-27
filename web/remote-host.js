import { BRSPConnection } from './vendor/brsp.js';
import { VdoNinjaTransport } from './vendor/vdo-ninja-transport.js';
import qrcode from './vendor/qrcode.mjs';
import { invitationUrl, observerConnectionOptions, OBSERVE_SCOPE } from './remote-profile.js';

export function mountRemoteViewer(invoke) {
  const byId = id => document.getElementById(id);
  let active;
  byId('viewer-start').addEventListener('click', () => { void start(); });
  byId('viewer-stop').addEventListener('click', () => { void stop(); });
  byId('viewer-copy').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(byId('viewer-link').value); byId('viewer-status').textContent = 'Viewer link copied.'; }
    catch { byId('viewer-link').focus(); byId('viewer-link').select(); byId('viewer-status').textContent = 'Select and copy the viewer link.'; }
  });
  window.addEventListener('pagehide', () => { void stop(); });

  async function stop() {
    const context = active;
    active = undefined;
    byId('viewer-start').disabled = false;
    byId('viewer-stop').disabled = true;
    byId('viewer-invitation').hidden = true;
    byId('viewer-link').value = '';
    byId('viewer-qr').replaceChildren();
    byId('viewer-status').textContent = 'Viewer stopped. Start again for a fresh link.';
    if (!context) return;
    clearInterval(context.timer);
    // Revoke native read authority before asynchronous transport shutdown.
    if (context.invitation) await invoke('viewer_action', { action: { action: 'stop', token: context.invitation.token } }).catch(() => {});
    await context.connection?.close();
  }

  async function start() {
    if (active) return;
    const context = {};
    active = context;
    byId('viewer-start').disabled = true;
    byId('viewer-stop').disabled = false;
    byId('viewer-status').textContent = 'Starting private read-only viewer…';
    try {
      context.invitation = await invoke('viewer_action', { action: { action: 'start' } });
      if (active !== context) {
        await invoke('viewer_action', { action: { action: 'stop', token: context.invitation.token } });
        return;
      }
      const refresh = async () => {
        if (context.refreshing || active !== context) return;
        context.refreshing = true;
        try {
          const snapshot = await invoke('viewer_action', { action: { action: 'snapshot', token: context.invitation.token } });
          if (active !== context) return;
          context.snapshot = snapshot;
          if (context.connection?.acceptedScopes.includes(OBSERVE_SCOPE)) context.connection.publishState();
        } finally { context.refreshing = false; }
      };
      await refresh();
      if (active !== context) return;
      context.transport = new VdoNinjaTransport({ role: 'target', room: context.invitation.room,
        sharedSecret: context.invitation.secret, label: 'Respyra read-only viewer' });
      context.connection = new BRSPConnection({ transport: context.transport,
        ...observerConnectionOptions(context.invitation, () => active === context && context.connection?.acceptedScopes.includes(OBSERVE_SCOPE) ? context.snapshot : undefined) });
      const status = message => { if (active === context) byId('viewer-status').textContent = message; };
      context.transport.addEventListener('status', event => status(event.detail.message));
      context.transport.addEventListener('quality', event => status(`Read-only viewer route: ${event.detail.route}.`));
      context.connection.addEventListener('ready', () => status('Authenticated read-only viewer connected.'));
      context.connection.addEventListener('phasechange', event => {
        if (active === context && ['disconnected', 'closed', 'error'].includes(event.detail.phase)) void stop();
      });
      context.timer = setInterval(() => { void refresh().catch(() => { if (active === context) void stop(); }); }, 250);
      const url = invitationUrl(context.invitation);
      byId('viewer-link').value = url;
      const code = qrcode(0, 'M'); code.addData(url, 'Byte'); code.make();
      const image = document.createElement('img');
      image.alt = 'QR code for private Respyra viewer'; image.src = code.createDataURL(4, 16);
      byId('viewer-qr').append(image);
      byId('viewer-invitation').hidden = false;
      await context.transport.start();
    } catch {
      if (active !== context) return;
      await stop();
      byId('viewer-status').textContent = 'Viewer could not start. Check Internet access and start again.';
    }
  }
}
