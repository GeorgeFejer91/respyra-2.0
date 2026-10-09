import { measureTextRegions } from './text-fit.js';

const $ = id => document.getElementById(id);
const native = window.__TAURI__;
const measure = await measureTextRegions();
async function load() {
  const diagnostic = native ? await native.core.invoke('error_report') : window.opener?.respyraErrorReport;
  $('error-report').value = diagnostic?.text || 'The report could not be loaded. See the local diagnostics folder.';
  $('error-saved').textContent = diagnostic?.saved_path ? `Saved locally: ${diagnostic.saved_path}` : 'The report is available to copy here.';
  $('error-copy-status').textContent = '';
  measure();
}
if (native) await native.event.listen('error-report-updated', load);
await load();
$('error-copy').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText($('error-report').value);
    $('error-copy-status').textContent = 'Report copied.';
  } catch {
    $('error-report').focus(); $('error-report').select();
    let copied = false;
    try { copied = document.execCommand('copy'); } catch { /* Keep the report selected for manual copy. */ }
    $('error-copy-status').textContent = copied ? 'Report copied.' : 'Press Ctrl+C to copy the selected report.';
  }
  measure();
});
$('error-dismiss').addEventListener('click', () => {
  if (native) void native.window.getCurrentWindow().close();
  else window.close();
});
