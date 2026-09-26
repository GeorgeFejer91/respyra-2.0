// Capture browser time before IPC; preserve every action, fail on overload.
export function actionQueue(invoke, onFailure, clock = () => performance.now()) {
  let sequence = 0, pending = 0, failed = false;
  let tail = Promise.resolve();
  const send = (action, fields = {}) => {
    if (failed) return tail;
    if (pending >= 128) {
      failed = true;
      onFailure(new Error('Setup input queue overflow; experiment stopped.'));
      return tail;
    }
    const payload = { action, ...fields, ui_seq: ++sequence, ui_time_ms: clock() };
    pending += 1;
    tail = tail.then(async () => {
      if (!failed) await invoke('setup_action', { action: payload });
    }).catch(error => {
      failed = true;
      onFailure(error);
    }).finally(() => { pending -= 1; });
    return tail;
  };
  Object.defineProperty(send, 'sequence', { get: () => sequence });
  return send;
}
