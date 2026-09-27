# Windows standalone packaging protocol

Current consumer: build/verify the downloadable Respira installer. Read this
file for packaging, installation, dependency changes or release promotion.
Product usage belongs in `docs/windows-install.md`; scripts/assets stay outside
the control plane.

## Contract and ownership

- Product display name: **Respira**. Retain app ID `dev.georgefejer.respyra2`,
  Python names `mpi`/`respyra`, raw Force units and existing study semantics.
- Windows 10/11 x64 only for this installer. Raspberry Pi/macOS are separate
  host/runtime qualification work; a Windows bundle is no evidence for them.
- Rust supervises the same closed Python pipe. Release builds locate only
  `resource_dir/engine/python/python.exe` and the bundled fixed launcher;
  a missing engine is an install error, never checkout/system-Python fallback.
- Package the official CPython 3.10.11 x64 embedded ZIP, pinned URL/SHA-256 in
  `scripts/package_runtime.py`. Stage a fresh `uv sync --frozen --no-dev
  --no-editable` environment; never copy the working `.venv` or whole workspace.
  Preserve locked PsychoPy/respyra/LSL dependencies and wheel data/DLL/licenses.
  Reinstall the local `mpi` wheel on every package build so uv's project cache
  cannot ship stale source or README metadata after a source-only edit.
  Copy the locked Qt wheel's MSVC support DLLs beside embedded Python and check
  loaded DLL paths; Python-module isolation alone can miss a borrowed system CRT.
  Python `-I` excludes user site/environment paths. Retain stdio isolation.
- Include only installed runtime packages, fixed product scripts, notices and
  public HTML/fonts/protocol assets. Never include `data/`, notebooks containing
  outputs, identity settings, private invitations, diagnostics or credentials.
  Strip build-only editable links, direct_url paths, caches and venv hooks.
- Use the attributed original upstream transparent artwork, pinned under
  `assets/branding/`. Generate icon formats with Tauri; no speculative new logo.
- NSIS per-user installation uses the normal destination page. Default requires
  no elevation; the user can choose any writable folder. Include offline WebView2
  delivery. No self-updater, firewall changes or startup task.
- Installed runtime cwd is `%LOCALAPPDATA%/Respira`; optional original CSVs go
  to its `data/`. Retain `%LOCALAPPDATA%/Respyra/lsl-source.json` identity memory.
  Uninstall must retain user data. Bundle the pinned native recorder under
  `engine/recorder`, including app-local DLLs, licenses and manifest. Build it
  with the isolated packaging venv's locked runtime support; verify source,
  adapter/script and output hashes before staging. Python requires raw-data
  and native subscription evidence before Start acceptance.

## Build and evidence

1. Inspect status, versions, locks, license changes and capacity. Preserve user
   work. Generated caches may be cleaned with Cargo, never user recordings.
2. Run focused Python desktop/study checks and Rust fmt/test/clippy. Keep one
   version across `package.json`, Cargo and Tauri. Icons/runtime are deterministic
   inputs; do not change study protocol to make packaging pass.
3. Run `pnpm package:windows` on Windows x64 with Python 3.10.11/uv, locked pnpm
   and MSVC/Rust. Use `-GenerateIcons` only for artwork changes. The installer
   overlay is `src-tauri/installer.conf.json`, explicitly passed; never name it
   `tauri.windows.conf.json` because Tauri also loads that during ordinary dev.
4. Observe the embedded interpreter import check, liblsl outlet, native synthetic
   XDF round trip and closed
   launcher lifecycle. Check `engine/manifest.json` path inventory/hashes,
   lock hashes, versions and source revision. A dirty manifest cannot be promoted.
5. Install the **exact** resulting NSIS artifact to a chosen folder with spaces;
   verify folder/shortcut/uninstaller/icon, complete engine and file parity.
   Check `engine/scripts/check_packaged_engine.py` via bundled Python `-I -B -X utf8`.
6. Set `RESPIRA_INSTALLED_EXE` to the installed main executable and run
   `tests/check_native_lsl.py` with `RESPYRA_PUBLISHED_PHONE=1`. It runs away from
   the checkout using synthetic private LSL streams and isolated identity memory.
   Observe selection/reconnect, actual PsychoPy instruction flip, CSV option,
   native Stop/Close cleanup and real hosted QR coupling. Check no child remains.
7. Check CSV writes in the writable user folder with original headers and off
   creates none. Installed scope is separate from scientific timing, physical
   belt/phone, full study calibration/timing, clean VM, other OS, upgrade and uninstall evidence.
8. Hash the installer (`dist/SHA256SUMS.txt`) and retain its manifest. Promote
   only these tested bytes. Upload installers as release assets, never to Git
   history or the static phone Pages branch. Source publication follows WORKFLOW.

## Distribution gate

The initial local build is unsigned; do not claim Authenticode, SmartScreen
reputation or clean-machine qualification. Signing identity/certificate/channel
needs explicit authorization. Review retained notices and corresponding source
for copyleft dependencies, including native libraries in wheels, before public
release promotion. Source links alone are not that review. If any gate fails,
keep the reviewable local installer and name the missing evidence. No bypass,
automatic promotion or secret-bearing CI is authorized by a build success.
