import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const vendor = path.join(root, 'web/vendor');
const catalog = JSON.parse(await readFile(path.join(root, 'src/mpi/event_markers/catalog.json'), 'utf8'));
await writeFile(path.join(root, 'web/marker-catalog.js'),
  `export const EVENT_MARKERS = ${JSON.stringify(Object.entries(catalog.events).filter(([, details]) => details.active !== false).map(([name, details]) => ({name, when: details.when})))};\n`);
await mkdir(path.join(vendor, 'fonts'), { recursive: true });
await cp(path.join(root, 'node_modules/@chenglou/pretext/dist'), path.join(vendor, 'pretext'), { recursive: true });
await cp(path.join(root, 'node_modules/@chenglou/pretext/LICENSE'), path.join(vendor, 'PRETEXT-LICENSE'));
for (const weight of [400, 600]) {
  const file = `noto-sans-latin-${weight}-normal.woff2`;
  await cp(path.join(root, 'node_modules/@fontsource/noto-sans/files', file), path.join(vendor, 'fonts', file));
}
await cp(path.join(root, 'node_modules/@fontsource/noto-sans/LICENSE'), path.join(vendor, 'NOTO-SANS-LICENSE'));
await cp(path.join(root, 'vendor/remote'), vendor, { recursive: true });
await cp(path.join(root, 'node_modules/qrcode-generator/dist/qrcode.mjs'), path.join(vendor, 'qrcode.mjs'));
const companion = path.join(root, 'companion');
await cp(path.join(root, 'assets/icon.svg'), path.join(companion, 'logo.svg'));
await cp(path.join(root, 'assets/branding/LICENSE.upstream.txt'), path.join(companion, 'vendor/RESPYRA-ARTWORK-LICENSE.txt'));
await cp(path.join(root, 'assets/branding/README.md'), path.join(companion, 'vendor/RESPYRA-ARTWORK.md'));
for (const file of ['style.css', 'text-fit.js', 'remote-profile.js', 'controller-ui.js', 'participant-options.js', 'action-queue.js', 'lsl-monitor.js']) {
  await cp(path.join(root, 'web', file), path.join(companion, file));
}
await cp(vendor, path.join(companion, 'vendor'), { recursive: true });
