import { BRSPConnection } from './vendor/brsp.js';
import { VdoNinjaTransport } from './vendor/vdo-ninja-transport.js';
import qrcode from './vendor/qrcode.mjs';
import { invitationUrl, SCOPES, OBSERVE_SCOPE, validCommand, validateControllerState } from './remote-profile.js';

export function mountRemoteViewer(invoke) {
  const byId = id => document.getElementById(id);
  let active;
  const open = () => {
    if (!byId('viewer-dialog').open) byId('viewer-dialog').showModal();
    window.dispatchEvent(new Event('resize'));
  };
  byId('viewer-open').addEventListener('click', () => { open(); void start(); });
  byId('viewer-done').addEventListener('click', () => byId('viewer-dialog').close());
  byId('viewer-approve').addEventListener('click', () => { void review(true); });
  byId('viewer-reject').addEventListener('click', () => { void review(false); });
  byId('viewer-start').addEventListener('click', () => { void start(); });
  byId('viewer-stop').addEventListener('click', () => { void stop(); });
  byId('viewer-copy').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(byId('viewer-link').value); byId('viewer-status').textContent = 'Control link copied.'; }
    catch { byId('viewer-link').focus(); byId('viewer-link').select(); byId('viewer-status').textContent = 'Select and copy the control link.'; }
  });
  window.addEventListener('pagehide', () => { void stop(); });

  async function stop(message = 'Remote control disconnected. Create a new QR code to reconnect.') {
    const context = active;
    active = undefined;
    byId('viewer-start').disabled = false;
    byId('viewer-start').hidden = false;
    byId('viewer-stop').disabled = true;
    byId('viewer-invitation').hidden = true;
    byId('viewer-approval').hidden = true;
    byId('viewer-open').querySelector('span').textContent = 'Remote Viewer';
    byId('viewer-requester').textContent = '';
    byId('viewer-link').value = '';
    byId('viewer-qr').replaceChildren();
    byId('viewer-status').textContent = message;
    if (!context) return;
    context.snapshot = undefined;
    clearInterval(context.timer);
    clearTimeout(context.approvalTimer);
    if (context.invitation) await invoke('viewer_action', { action:{ action:'stop', token:context.invitation.token } }).catch(() => {});
    await context.connection?.close();
  }

  async function review(approve) {
    const context = active;
    if (!context?.request || context.reviewing) return;
    context.reviewing = true;
    byId('viewer-approve').disabled = true;
    byId('viewer-reject').disabled = true;
    try {
      const grant = await invoke('viewer_action', { action:{ action:'review', token:context.invitation.token,
        request:context.request, approve } });
      if (active !== context) return;
      if (!approve) { await stop('Remote request rejected. Create a new QR code to try again.'); return; }
      context.owner = grant.owner;
      clearTimeout(context.approvalTimer);
      byId('viewer-approval').hidden = true;
      byId('viewer-invitation').hidden = true;
      byId('viewer-open').querySelector('span').textContent = 'Remote Viewer connected';
      await context.refresh();
      if (active !== context) return;
      context.connection.publishSnapshot();
      byId('viewer-status').textContent = 'Remote controller approved and connected.';
      byId('viewer-dialog').close();
    } catch {
      if (active === context) await stop('Remote request expired or disconnected. Create a new QR code to try again.');
    }
  }

  async function start() {
    if (active) return;
    const context = { sequence:0 };
    active = context;
    byId('viewer-start').disabled = true;
    byId('viewer-start').hidden = true;
    byId('viewer-stop').disabled = false;
    byId('viewer-status').textContent = 'Preparing private QR code…';
    try {
      context.invitation = await invoke('viewer_action', { action:{ action:'start' } });
      if (active !== context) {
        await invoke('viewer_action', { action:{ action:'stop', token:context.invitation.token } });
        return;
      }
      const status = message => { if (active === context) byId('viewer-status').textContent = message; };
      const refresh = async () => {
        if (!context.owner || context.refreshing || active !== context) return;
        context.refreshing = true;
        try {
          const snapshot = await invoke('viewer_action', { action:{ action:'snapshot', token:context.invitation.token, owner:context.owner } });
          if (active !== context) return;
          if (!validateControllerState(snapshot)) throw new Error('Invalid controller state');
          context.snapshot = snapshot;
          context.connection.publishState();
        } finally { context.refreshing = false; }
      };
      context.refresh = refresh;
      context.transport = new VdoNinjaTransport({ role:'target', room:context.invitation.room,
        sharedSecret:context.invitation.secret, label:'Respyra experiment control' });
      context.connection = new BRSPConnection({ transport:context.transport, role:'target',
        sessionId:context.invitation.room, sharedSecret:context.invitation.secret,
        capabilities:['command-ack','state-snapshot','latest-state'], grantedScopes:SCOPES,
        getState:() => active === context && context.owner && context.connection.acceptedScopes.includes(OBSERVE_SCOPE) ? context.snapshot : undefined,
        applyCommand:async command => {
          if (!validCommand(command)) return { ok:false, revision:context.snapshot?.revision || 0, error:'unsupported_command' };
          if (command.scope === OBSERVE_SCOPE && command.action === 'introduce') {
            if (context.claim || context.owner) return { ok:false, revision:0, error:'request_already_pending' };
            const peer = context.connection.remoteHello;
            context.claim = (async () => {
              const request = await invoke('viewer_action', { action:{ action:'claim', token:context.invitation.token,
                peer_id:peer.senderId, epoch:peer.senderEpoch, scopes:context.connection.acceptedScopes, name:command.args.name } });
              if (active !== context) return;
              context.request = request.request;
              byId('viewer-requester').textContent = request.name;
              byId('viewer-approve').disabled = false;
              byId('viewer-reject').disabled = false;
              byId('viewer-approval').hidden = false;
              byId('viewer-invitation').hidden = true;
              byId('viewer-open').querySelector('span').textContent = 'Review remote request';
              status('Remote viewer requests access. Review the name below.');
              open();
              context.approvalTimer = setTimeout(() => {
                if (active === context && !context.owner) void stop('Remote request expired. Create a new QR code to try again.');
              }, 60000);
            })();
            await context.claim;
            return { ok:true, revision:0, result:null, error:null };
          }
          await context.claim;
          if (active !== context || !context.owner) return { ok:false, revision:0, error:'local_approval_required' };
          const peer = context.connection.remoteHello;
          const outcome = await invoke('viewer_action', { action:{ action:'dispatch',
            token:context.invitation.token, owner:context.owner, peer_id:peer.senderId, epoch:peer.senderEpoch,
            sequence:++context.sequence, command } });
          if (active === context) await refresh();
          return outcome;
        },
      });
      context.transport.addEventListener('status', event => status(event.detail.message));
      context.transport.addEventListener('quality', event => status('Phone route: ' + event.detail.route + '.'));
      context.connection.addEventListener('ready', () => status('Phone connected. Waiting for its name…'));
      context.connection.addEventListener('phasechange', event => {
        if (active === context && ['disconnected','closed','error'].includes(event.detail.phase)) void stop();
      });
      context.timer = setInterval(() => { void refresh().catch(() => { if (active === context) void stop(); }); }, 250);
      const url = invitationUrl(context.invitation);
      byId('viewer-link').value = url;
      const code = qrcode(0, 'M'); code.addData(url, 'Byte'); code.make();
      const image = document.createElement('img');
      image.alt = 'QR code for private Respyra phone control'; image.src = code.createDataURL(4, 16);
      status('Private QR ready. Scan it to enter a phone name.');
      byId('viewer-qr').append(image);
      byId('viewer-invitation').hidden = false;
      await context.transport.start();
    } catch {
      if (active !== context) return;
      await stop();
      byId('viewer-status').textContent = 'Phone control could not start. Check Internet access and enable again.';
    }
  }
}
