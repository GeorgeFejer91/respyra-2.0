import { actionQueue } from './action-queue.js';
import { mountController } from './controller-ui.js';
import { measureTextRegions } from './text-fit.js';
import { mountRemoteViewer } from './remote-host.js';

const native = window.__TAURI__;
const fail = error => {
  controller.fail('Control connection failed: ' + String(error));
  native?.core.invoke('close_app', { reason: 'protocol_failure' }).catch(() => {});
};
const send = actionQueue(async (command, args) => {
  if (args.action.action === 'close') {
    await native.core.invoke('close_app', { reason:'close_button' });
    return { ok:true };
  }
  return native.core.invoke(command, args);
}, fail);
const controller = mountController(document.getElementById('controller'), send, () => { void send('shown'); });

measureTextRegions().catch(() => { document.documentElement.dataset.pretextFit = 'unavailable'; });
if (native) {
  mountRemoteViewer((command, args) => native.core.invoke(command, args));
  const render = snapshot => {
    if (snapshot.study_name) document.getElementById('study').textContent = snapshot.study_name;
    controller.render(snapshot);
  };
  await native.event.listen('setup-state', event => render(event.payload));
  await native.core.invoke('launch_backend').then(render).catch(fail);
} else {
  controller.render({ phase:'starting', message:'Open Respyra through the desktop launcher to connect to the experiment engine.' });
  controller.setEnabled(false);
}
