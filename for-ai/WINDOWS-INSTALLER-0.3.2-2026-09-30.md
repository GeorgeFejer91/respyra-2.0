# Windows 0.3.2 public installer verification, 2026-09-30

Status: **published** as [v0.3.2](https://github.com/GeorgeFejer91/respyra-2.0/releases/tag/v0.3.2).
All installed GUI checks used a private Win32 desktop. The release tag is
`98c89ebd0a533c0754f26829a4d58b2d1ba7f519`, the clean source revision in
the runtime manifest. PRs #1 and #2 were merged; `origin/main` at merge commit
`b8ffbf59306c2a856cc9c3156ba7ba395920f038` has the same file tree as the
release tag. No CI checks were configured on those PRs.

## Exact release assets

- Installer: `Respyra-2.0_0.3.2_x64-setup.exe`, 113,152,255 bytes, SHA-256
  `8b2b6e2ad8b58d042893d1f8fbdd7b1f82c166ce89ea55e24c1de2f3198c1022`.
  The local Tauri filename has spaces; the GitHub asset is hyphenated and has
  identical bytes. This is 313,220,956 bytes smaller than the 0.3.1 candidate.
- Corresponding source: `Respyra-2.0_0.3.2_sources.zip`, 696,073,754 bytes,
  SHA-256 `b5aa1d764791804d683b096a8b89eb84ead4d019295d1f3ee5c8e07f8374af81`.
  ZIP CRC validation passed for 24,160 entries. It contains the exact first-party
  Git source, 91 external Python source archives, 416 locked Cargo registry
  crates, 15 python-bidi crates, and eight pinned native source/build archives.
- Runtime manifest: 2,720,430 bytes, SHA-256
  `35ab2a26771c8181f0d5f2be1051a178695bc3a04bfa805b3a7e853bf5be3f59`.
  `source_dirty: false`; 18,433 embedded files and 92 Python distributions.
- `SHA256SUMS.txt` lists the public filenames. GitHub's asset SHA-256 digests
  matched all local files after upload; the public release page loaded without
  authentication. Installers and source archives remain outside Git history.

## Checks and distribution review

- `python -m uv lock --check`, packaging Python compilation, `cargo fmt --check`,
  `cargo test --locked` (10 passed), and Clippy `--all-targets -- -D warnings`
  passed with Rust 1.95.0. `for-ai/scripts/check-context.ps1` passed. Captured
  logs: ignored `.for-ai-local/cargo-test-032.log`, `cargo-clippy-032.log` and
  `package-windows-032-final.log`.
- `pnpm package:windows` rebuilt the pinned native recorder, isolated embedded
  CPython 3.10.11 and NSIS bundle. The embedded and exact installed engine
  probes passed PsychoPy/LSL imports, app-local Microsoft CRT loading, live
  marker output and a three-stream footered synthetic XDF round trip. Neither
  Qt/PyQt modules nor FFmpeg executables/DLLs occur in the final manifest.
- The exact EXE installed with exit 0 to ignored
  `.for-ai-local/Installed Respyra 2.0 Release 98c89eb/`, a path with spaces.
  Independent hash comparison passed for all 18,433 engine files. The Start
  shortcut targeted its executable and an uninstaller was present. The private
  installed select/memory/remote check passed with hosted phone QR, 26-27
  ordered markers, native XDF Stop/Close, remembered input, and CSV on/off with
  original headers. Log: ignored `.for-ai-local/native-installed-select-memory-remote.log`.
- A preceding installed 0.3.1 candidate completed a 48-trial synthetic run
  with the omitted package directories hidden. That is functional evidence
  for the conservative trim, not a full-study run of the final installer.
- `scripts/build_release_sources.py` verified the packaged libusb DLL, the
  NumPy/SciPy OpenBLAS DLLs against their exact upstream Windows wheels, all
  source archive hashes and Cargo checksums. The release carries GPL/LGPL/MPL
  source and notices separately from the 113 MB installer. Its captured log is
  `.for-ai-local/build-release-sources-032-final.log`.

## Limits

This is one Windows PC with synthetic input and an installed WebView2 runtime.
A clean computer's WebView2 download, physical belt/phone, full-duration
scientific timing, upgrade behavior, and code signing/SmartScreen reputation
were not verified. An isolated silent uninstall started an NSIS child that did
not complete; the child was stopped, and uninstall behavior is **not verified**.
The synthetic XDFs remained in `%LOCALAPPDATA%/Respira/data`. Do not describe
the attempted uninstall as a passed removal/data-retention check.
