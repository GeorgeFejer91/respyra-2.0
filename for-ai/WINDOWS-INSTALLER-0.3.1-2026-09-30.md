# Windows 0.3.1 installer verification, 2026-09-30

Status: **exact installed synthetic runtime verified; public release blocked by
corresponding-source and notice review**. All GUI work ran on a private Win32
desktop without switching the user's active desktop.

## Exact artifact and inputs

- Product source: clean commit `b0d43acab9162a76a738a0f09c687df9a2ffc089`.
  The manifest records version `0.3.1`, Windows x64 and `source_dirty: false`.
- Local NSIS artifact: `dist/Respyra 2.0_0.3.1_x64-setup.exe`, 426,373,211
  bytes, SHA-256 `71b013e303ea009ba9d51d17f30c88ba6f60b80a75f0ffdee71410659e621108`.
  `dist/SHA256SUMS.txt` matches. `dist/runtime-manifest.json` SHA-256 is
  `1bc3c917f084c02c3ae58761c2220b32041635743bb0fb4c4eb1b5dd1b756d69`.
  The engine contains 23,084 files and 104 installed Python distributions.
- Compared with the previous 0.3.0 candidate, the installer is 110,114,547
  bytes smaller after excluding unused FFmpeg payloads and moving Jupyter and
  `ipympl` to the opt-in notebook group. The installed inventory contains no
  `psycopg`, Jupyter, `ipympl`, `ffpyplayer` or `imageio-ffmpeg` distribution.
  The embedded probe also finds no FFmpeg executable/DLL or FFmpeg shared DLLs.
  Source files for optional media integrations remain in other packages; this
  is a claim about shipped binary payloads and installed distributions.

## Checks

- `python -m uv lock --check`, the focused desktop bridge/process/recording
  Python tests (27 passed), `cargo fmt --check`, `cargo test --release --locked`
  (10 passed) and release Clippy with `-D warnings` passed. Rust 1.96.1 crashed
  in unrelated dependencies on this host. The successful Tauri release build,
  Rust tests and Clippy used Rust 1.95.0, one Cargo job, bundled `rust-lld`,
  and the existing portable MSVC/SDK. The successful captured build/check logs
  are in ignored `.for-ai-local/tauri-build-195-0.3.1.log`,
  `cargo-test-195-0.3.1.log` and `cargo-clippy-195-0.3.1.log`.
- Staged and installed `check_packaged_engine.py` passed isolated imports,
  app-local MSVC loading, live LSL marker output and a three-stream footered
  synthetic XDF round trip using embedded CPython 3.10.11. The installed probe
  ran with its working directory away from the checkout.
- The exact NSIS artifact installed with exit 0 on a private desktop to
  `.for-ai-local/Installed Respyra 2.0 Tower b0d43ac/`. The independent
  `verify_install.py` comparison found every one of 23,084 engine files at its
  manifest hash. The Start-menu shortcut targets the installed executable;
  the uninstaller and bundled notices are present. Installed executable
  SHA-256: `597bd9deb8f034690979afaa61b4b3d6d3be70ce1dcda4c5c6e5e288de1c3664`.
- The installed `check_native_lsl.py` private-desktop select/memory/remote
  check passed with synthetic LSL, hosted phone page, QR decode in remote mode,
  actual PsychoPy instruction flip, XDF Stop/Close, 26–27 ordered live markers,
  and CSV on/off. CSV-on wrote two files with original headers; CSV-off wrote
  none. Captured log: ignored
  `.for-ai-local/native-installed-select-memory-remote.log`.

## Limits and release gate

This verifies an installed synthetic workflow on one Windows PC. It does not
establish physical belt/phone behavior, clean-VM compatibility, full-duration
installed study timing, signing, or upgrade/uninstall behavior for these bytes.
The installer has **not** been uploaded to a GitHub Release.

Removing unused FFmpeg binaries resolves the specific FFmpeg corresponding-source
gap in the previous candidate. The installer still contains GPL/LGPL components,
including PsychoPy, PyQt6/Qt, Go Direct and QuestPlus. Exact corresponding
source and retained notices for those components, native libraries inside
other wheels, and compiled Rust crates have not received the distribution
review required by [`PACKAGING.md`](./PACKAGING.md). Keep the local installer
reviewable and do not promote it as a public release until that gate is complete.
