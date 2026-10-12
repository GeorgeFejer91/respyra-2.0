import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';

const native = new URL('../src-tauri/', import.meta.url);

test('folder buttons have generated command permissions granted only to the local main window', () => {
  const build = readFileSync(new URL('build.rs', native), 'utf8');
  const manifest = build.match(/AppManifest::new\(\)\.commands\(&\[([\s\S]*?)\]\)/)?.[1];
  assert(manifest, 'Application command manifest is missing');
  const capabilities = readdirSync(new URL('capabilities/', native))
    .filter(name => name.endsWith('.json'))
    .map(name => JSON.parse(readFileSync(new URL(`capabilities/${name}`, native), 'utf8')));
  for (const command of ['open_recordings_folder', 'choose_recordings_folder', 'set_recordings_folder']) {
    assert(manifest.includes(`"${command}"`), `${command} is missing from the command manifest`);
    const grant = `allow-${command.replaceAll('_', '-')}`;
    const holders = capabilities.filter(cap => cap.permissions.includes(grant));
    assert.equal(holders.length, 1, `${command} needs one local capability grant`);
    assert.deepEqual(holders[0].windows, ['main']);
    assert.equal(holders[0].local ?? true, true);
    assert.equal(holders[0].remote, undefined);
  }
});
