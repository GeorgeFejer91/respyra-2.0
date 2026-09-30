# Tower PC Windows installer verification, 2026-09-30

Status: **installed mock runtime verified; public release blocked by corresponding-source review**. All work and GUI checks ran on the Tower PC. GUI checks used private Win32 desktops and headless Chrome, without switching the active desktop.

## Exact inputs and artifact

- Canonical Respyra repository: `https://github.com/GeorgeFejer91/respyra-2.0`, branch `codex/recorder-panel`, [PR #2](https://github.com/GeorgeFejer91/respyra-2.0/pull/2). Installer source revision: `617621fa69990aab14d360f61548d267789d7490`, `source_dirty: false`. Validation harness fixes through `81d63eee99f4dff0e647b36bba3ddad4b9db0b6b` were pushed after the installer build; they do not change installed runtime bytes.
- Canonical Mini repository: `https://github.com/GeorgeFejer91/Polar-Mini-Stream`, branch `codex/polar-mock-respyra`, commit `43c22ad016c21d2510cff6146fef0264b220da41`, [PR #5](https://github.com/GeorgeFejer91/Polar-Mini-Stream/pull/5). Polar Stream Mini and Vernier Stream Mini are two apps in this repository, both version `0.6.3`.
- Respyra desktop version `0.3.0`; embedded CPython `3.10.11`, `respyra` Python distribution `0.4.0`, PsychoPy `2026.2.4`, pylsl `1.18.5`. The pinned native recorder uses liblsl `1.18.0.b5`.
- Tested installer: `dist/Respyra 2.0_0.3.0_x64-setup.exe`, 536,487,758 bytes, SHA-256 `59bbcca01ecabe7656e598414422b4670fee9a4e11daa95121aa55e40deb6b0b`. `dist/SHA256SUMS.txt` matches. `dist/runtime-manifest.json` SHA-256 `1aa6379c542ea82b9b10472c15de8f52afb221d50ff28f56791cc871ee3eb6e9`, with 28,708 engine files.
- Exact tested installation: `.for-ai-local/Installed Respyra 2.0 Tower 617621f/`. The per-user installer exited `0` on a private desktop. Every manifest file was present and SHA-256 matched, including the bundled engine, recorder, notices, and LSL Data viewer assets. Start-menu shortcut and uninstaller were present.

## Commands and installed checks

All paths below are relative to this repository unless absolute. The installed engine probe was run with `.for-ai-local/packaging/run elsewhere/` as its working directory.

```powershell
& .for-ai-local\msvc\activate.ps1
pwsh -NoProfile -File scripts/package-windows.ps1 *> '.for-ai-local\release-build-tower-617621f.log'
& .venv\Scripts\python.exe .for-ai-local\install_private.py 'C:\Users\gfeje\Documents\GitHub\respyra-2.0\dist\Respyra 2.0_0.3.0_x64-setup.exe' 'C:\Users\gfeje\Documents\GitHub\respyra-2.0\.for-ai-local\Installed Respyra 2.0 Tower 617621f'
& .venv\Scripts\python.exe .for-ai-local\verify_install.py '.for-ai-local\Installed Respyra 2.0 Tower 617621f'
& '.for-ai-local\Installed Respyra 2.0 Tower 617621f\engine\python\python.exe' -I -B -X utf8 '.for-ai-local\Installed Respyra 2.0 Tower 617621f\engine\scripts\check_packaged_engine.py'
$env:RESPIRA_INSTALLED_EXE='C:\Users\gfeje\Documents\GitHub\respyra-2.0\.for-ai-local\Installed Respyra 2.0 Tower 617621f\respyra-desktop.exe'
& .venv\Scripts\python.exe tests\run_private_mock.py remote --mini-exe 'C:\Users\gfeje\Documents\GitHub\Polar-Mini-Stream\target\debug\polar-stream-mini.exe' --respyra-exe $env:RESPIRA_INSTALLED_EXE --polar-metric pca
& .venv\Scripts\python.exe tests\run_private_mock.py remote --mini-exe 'C:\Users\gfeje\Documents\GitHub\Polar-Mini-Stream\target\debug\polar-stream-mini.exe' --respyra-exe $env:RESPIRA_INSTALLED_EXE --polar-metric phan --published-phone
& .venv\Scripts\python.exe tests\run_private_mock.py memory --mini-exe 'C:\Users\gfeje\Documents\GitHub\Polar-Mini-Stream\target\debug\vernier-stream-mini.exe' --respyra-exe $env:RESPIRA_INSTALLED_EXE
& .venv\Scripts\python.exe .for-ai-local\run_native_installed_private.py $env:RESPIRA_INSTALLED_EXE
```

The embedded interpreter probe passed isolated imports, app-local MSVC loading, a live marker outlet, and a native footered XDF round trip: 25 raw, 25 derived, and 2 event samples. The final three-mode native check passed `select`, `memory`, `remote`, hosted-phone QR and approval, live LSL Data viewer values/trace/markers, PsychoPy instruction flip, XDF Stop/Close, source memory, and CSV on/off. Its 3 startup readiness measurements were 858, 151, and 162 ms after the WebView page was discovered. Two CSVs with the original headers were saved for the one CSV-on run; CSV-off runs created none. No Respyra or Mini process remained after the checks.

| Installed run | XDF path | Recorded samples and markers | Result |
| --- | --- | --- | --- |
| Polar PCA, locally routed phone, intentional early Stop | `%LOCALAPPDATA%/Respira/data/packaging-test-1545be41197e_Session-001_f8ddc590e60944b4bf3064b484cc1f94.xdf` | 1,102 raw ACC; 551 PCA and each validity/quality companion; 299 calibrated; 12 XDF event samples plus 13 embedded setup events = 25 ordered reconstructed events | Independent `audit_polar_mock_xdf.py --expect-abort` passed; maximum candidate error below `5e-10`. QR decoded; 28 live UI markers. |
| Polar signed Phan, published phone page, intentional early Stop | `%LOCALAPPDATA%/Respira/data/packaging-test-91c3b3e1de42_Session-001_df93239770f1493d86cb99e0f3707b59.xdf` | 1,102 raw ACC; 551 signed Phan and each validity/quality companion; 298 calibrated; 12 XDF events plus 13 embedded setup events = 25 ordered reconstructed events | Independent audit passed; maximum candidate error below `5e-10`. `publishedPhone:true`, `qrDecoded:true`, 28 live UI markers. |
| Vernier Mini memory/CSV regression, intentional early Stop | `%LOCALAPPDATA%/Respira/data/packaging-test-d02d12b0080d_Session-001_329b5a1498d64d87b0b34aa3f9b05aa6.xdf` | 91 raw, 91 Mini derived, 82 Respyra derived, 12 XDF events; 25 live UI markers | Native XDF and 2 CSV header checks passed. |
| Built-in synthetic select/memory/remote sequence | `%LOCALAPPDATA%/Respira/data/packaging-test-83f97c26a2dd_Session-001_b94804186ffa48f7a8e2a6a9cfb26824.xdf` and `%LOCALAPPDATA%/Respira/data/packaging-test-83f97c26a2dd_Session-001_eb62f9e105fa46d19d12d400c45c3dd3.xdf` | Memory: 100 raw, 100 source-derived, 86 calibrated, 12 XDF events. Remote: 120 raw, 120 source-derived, 110 calibrated, 12 XDF events. | `select`, `memory`, `remote` passed; hosted QR decoded in remote; CSV on/off passed. |

The Polar audit compared every recorded candidate and validity sample with the deterministic 30,000-tick reference, checked timestamps, metadata, signed polarity and ordered markers, and required raw and companion coverage through `recording.finalizing`. Streams can contain different extra tails after that marker during an abort; the audit reports those tails rather than treating them as missing experiment data. The earlier [Polar mock verification](./POLAR-MOCK-VERIFIED.md) records 14 complete 48-trial XDF audits, repetition, sustained recording, source loss, restart and Vernier regression against the development executable. Those full trials were not rerun using this installed artifact: isolated packaged Python ignores the test-only `sitecustomize` acceleration, so an installed full trial would use real study timing and participant responses.

## Defects found and fixes pushed

- `72a2303`: Tower packaging now selects the uv-managed Python `3.10.11` directly, avoiding the broken `py -3.10` alias.
- `68c018d`: increased desktop pairing QR display from 180 to 320 px. A 180 px installed screenshot intermittently failed OpenCV decoding; a 320 px installed screenshot decoded, and local and published phone checks passed. The private Polar harness now imports audit modules from the repository root.
- `617621f`: excluded 114 JupyterLab Galata browser-test files from the packaged runtime. Two earlier deep-path installs silently omitted the same Galata asset although NSIS exited `0`; a short-path installation included it. This final deep-path installation matched all 28,708 manifest hashes.
- `567e4ef`: abort audits now require all relevant Polar streams to cover the finalization marker while reporting source samples recorded later. All recorded values still match the deterministic reference.
- `a6f6f26`, `c205559`, `81d63ee`: current LSL Data viewer phone tests allow vertical scrolling, and installed startup/XDF assertions wait for final backend state. The complete three-mode check then passed. These are validation-harness changes after the installer source revision.

## Public distribution gate and limits

The installer is a **local verified candidate, not a GitHub release**. No `v0.3.0` release or tag was created. The remaining specific gate is corresponding-source review for copyleft native libraries bundled inside Python wheels. The installed `ffpyplayer` wheel contains Gyan FFmpeg `6.0-full_build` GPLv3, whose README identifies FFmpeg core commit `ea3d24bbe3`; `imageio-ffmpeg` contains Gyan FFmpeg `7.1-essentials_build` GPLv3, whose release points to core commit `b08d7969c5`. Their exact external linked-library source revisions, build scripts/configuration, and a distribution plan for corresponding source have not been established. [FFmpeg's distribution guidance](https://www.ffmpeg.org/legal.html) calls for corresponding source for the binary; the [Gyan 6.0](https://github.com/GyanD/codexffmpeg/releases/tag/6.0) and [7.1](https://github.com/GyanD/codexffmpeg/releases/tag/7.1) release pages identify only the FFmpeg core commits. Source links and notices alone do not meet this project's [`PACKAGING.md`](./PACKAGING.md) release gate.

This is mock validation on one Windows Tower PC. It does not establish physical Polar/Vernier sensor reliability, scientific display timing, clean-VM compatibility, a physical phone's behavior, other operating systems, signing reputation, upgrade behavior, or a complete installed 48-trial run. The private installed candidate remains at the path above for review; no public installer URL exists yet.
