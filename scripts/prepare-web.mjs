import { cp, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const vendor = path.join(root, 'web/vendor');
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
for (const file of ['style.css', 'text-fit.js', 'remote-profile.js', 'controller-ui.js', 'action-queue.js']) {
  await cp(path.join(root, 'web', file), path.join(companion, file));
}
await cp(vendor, path.join(companion, 'vendor'), { recursive: true });
