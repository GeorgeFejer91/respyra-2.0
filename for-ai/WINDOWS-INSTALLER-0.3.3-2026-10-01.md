# Windows 0.3.3 ECG viewer and installer verification, 2026-10-01

Status: **published** as [v0.3.3](https://github.com/GeorgeFejer91/respyra-2.0/releases/tag/v0.3.3).
The release tag and clean runtime source revision are
`4513b568ccad7215c62b1568d6318d8cbc1d22fa`. All installer and native
GUI checks ran on private Win32 desktops without taking the user's desktop.

## Exact assets

- `Respyra-2.0_0.3.3_x64-setup.exe`: 113,222,296 bytes, SHA-256
  `bf0e60ae122934b3609e5e34508ccd49a7a83c37c39093cecd55001b944e45bb`.
  The hyphenated public copy is byte-identical to the NSIS output installed in
  the tests.
- `Respyra-2.0_0.3.3_sources.zip`: 696,087,877 bytes, SHA-256
  `dac8ffb850e871d64804f3dd88c949638f1c06a3813ba338954ea6aeb01f1ca3`.
  The builder checked Python/native source hashes and locked Rust crate
  checksums. ZIP CRC validation passed for all 24,167 entries.
- `runtime-manifest.json`: 2,720,430 bytes, SHA-256
  `6007dfc2bf171768e7ccca54fc36c5ccdb4fa085d1a4ce3b030c65bd80c380f0`;
  `source_dirty: false`, 18,433 bundled files. `SHA256SUMS.txt` names the public
  assets. All four GitHub asset digests matched the local files after upload.

## Checks

- The 130 Hz Python LSL regression retained 130 of 130 ordered ECG samples in
  a one-second window. The browser preview regression retained 1,300 samples
  over ten seconds and its rendered narrow peaks were inspected. UI checks
  passed for eight layouts and 15 actions with no page errors.
- `pnpm package:windows` rebuilt the native recorder, locked Python runtime,
  Rust desktop app and NSIS bundle from the clean commit. The exact installer
  exited 0 at a fresh path with spaces. The install created `data/`, its Start
  Menu shortcut targeted that executable, and all 18,433 installed engine files
  matched the manifest. The installed Python engine check passed isolated
  imports, app-local CRT use, marker outlet and a three-stream XDF round trip.
- The exact installed app passed native select, remembered-source and remote
  runs with hosted phone QR, XDF recording, original CSV headers, and clean
  Stop/Close. Its XDF files appeared inside the installation's `data/` folder.
  The Polar Mini mock test required an isolated WebView2 user-data profile;
  with that profile it passed ordered rawECG sample batches, at least 100 ECG
  plot points, and an independently audited XDF containing 651 raw ECG samples
  during the short run. Captured preview: ignored
  `.for-ai-local/native-ecg-preview.png`.
- A same-version reinstall kept a test XDF byte-identical (SHA-256
  `feb47fd1009bf7dcf137d41d8513b822a23a5319e9a977a0417cefe9937916dc`).
  The first private silent-uninstall child stalled and was stopped. A second
  isolated silent uninstall completed, removed the app/engine/uninstaller and
  left that XDF under `data/` with the same hash.
- Pages commit `5346e017e3767e9fda9ac008e175ea2c6b9d8d67` built from this source.
  Ten public site assets matched their Git blobs byte for byte, and the public
  installer link returned HTTP 200 with the release size.

## Limits

This is one Windows PC with synthetic streams and an installed WebView2
runtime. The folder button's Explorer launch was not clicked because Explorer
can reuse the user's active desktop; its UI wiring and Rust target-path code
were reviewed, and the installed runtime wrote to that target. Physical Polar
hardware, a clean-machine WebView2 download, full study timing, code signing
and SmartScreen reputation were not checked.
