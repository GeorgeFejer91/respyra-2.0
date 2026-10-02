# Windows standalone packaging protocol

Current consumer: build/verify the downloadable Respyra 2.0 installer. Read this
file for packaging, installation, dependency changes or release promotion.
Product usage belongs in `docs/windows-install.md`; scripts/assets stay outside
the control plane.
All verification follows `VERIFICATION.md`'s background requirement. CLI builds
use hidden/captured workers; installer dialogs and actual installed native/
PsychoPy checks require a compatible isolated desktop/session or VM. Do not
launch them on the user's active desktop; missing isolation leaves those gates
`NOT RUN` and cannot qualify release promotion.

## Contract and ownership

- `pnpm package:windows` remains the independent Respyra installer. `pnpm
  package:suite` builds it plus the two Mini installers from the pinned,
  clean `mini-streams` submodule, extracts each finalized Mini executable and
  resources, and adds them through `src-tauri/suite.conf.json`. The suite keeps
  Respyra's app identity and install folder. Its NSIS hook creates Polar,
  Vernier, and full-suite shortcuts beside the normal Respyra shortcut; the
  launcher starts both Minis before Respyra. Do not bundle loose pre-installer
  Mini executables or silently replace saved Mini preferences.
- The suite and standalone Mini installers are separate release assets. Record
  each exact installer, extracted Mini executable, resource hash, submodule
  revision, and suite installer in `dist/suite-manifest.json` and the release
  checksums. A source companion for the suite must include the pinned Mini
  source alongside Respyra's normal source bundle.

- Product display name: **Respyra 2.0**. Retain app ID `dev.georgefejer.respyra2`,
  Python names `mpi`/`respyra`, raw Force units and existing study semantics.
- Windows 10/11 x64 only for this installer. Raspberry Pi/macOS are separate
  host/runtime qualification work; a Windows bundle is no evidence for them.
- Rust supervises the same closed Python pipe. Release builds locate only
  `resource_dir/engine/python/python.exe` and the bundled fixed launcher;
  a missing engine is an install error, never checkout/system-Python fallback.
- Package the official CPython 3.10.11 x64 embedded ZIP, pinned URL/SHA-256 in
  `scripts/package_runtime.py`. Stage a fresh `uv sync --frozen --no-dev
  --no-editable` environment; never copy the working `.venv` or whole workspace.
  Preserve needed locked PsychoPy/respyra/LSL dependencies and wheel data/DLL/licenses.
  Exclude the explicitly inventoried Qt/PyQt, OpenCV, PyArrow and FFmpeg
  payloads that the experiment does not use; fail packaging if those wheel paths change.
  Reinstall the local `mpi` wheel on every package build so uv's project cache
  cannot ship stale source or README metadata after a source-only edit.
  Keep Jupyter and `ipympl` in the opt-in `notebooks` dependency group; they
  are not part of the installed experiment engine.
  Copy the locked Qt wheel's MSVC support DLLs beside embedded Python and check
  loaded DLL paths; Python-module isolation alone can miss a borrowed system CRT.
  Python `-I` excludes user site/environment paths. Retain stdio isolation.
- Include only installed runtime packages, fixed product scripts, notices and
  public HTML/fonts/protocol assets. Never include `data/`, notebooks containing
  outputs, identity settings, private invitations, diagnostics or credentials.
  Strip build-only editable links, direct_url paths, caches and venv hooks.
- Generate icon formats with Tauri directly from `assets/icon.svg`, a vector
  recreation of the attributed upstream artwork pinned under `assets/branding/`.
- NSIS per-user installation uses the normal destination page. Default requires
  no elevation; the user can choose any writable folder. Use Tauri's standard
  WebView2 download bootstrapper only if WebView2 is absent, so first installation
  on a clean computer needs Internet. No self-updater, firewall changes or startup task.
- NSIS precreates `data/` inside the chosen installation folder. The installed
  runtime uses that folder for XDF and automatic original CSV files unless the
  user selects another writable folder. The default path is
  `%LOCALAPPDATA%/Respyra 2.0/data`. The unlisted `data/` directory
  survives the Tauri NSIS uninstaller and upgrades. Earlier files under
  `%LOCALAPPDATA%/Respira/data` remain untouched. Retain
  `%LOCALAPPDATA%/Respyra/lsl-source.json` identity memory.
  Bundle the pinned native recorder under
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
   verify the precreated `data/` folder, shortcut/uninstaller/icon, complete engine
   and file parity. Use an isolated install location so recordings stay private.
   Check `engine/scripts/check_packaged_engine.py` via bundled Python `-I -B -X utf8`.
6. Set `RESPYRA_INSTALLED_EXE` to the installed main executable and run
   `tests/check_native_lsl.py` with `RESPYRA_PUBLISHED_PHONE=1`. It runs away from
   the checkout using synthetic private LSL streams and isolated identity memory.
   Observe selection/reconnect, actual PsychoPy instruction flip, automatic CSV,
   native Stop/Close cleanup and real hosted QR coupling. Check no child remains.
7. Check XDF, CSV, participant-list and BIDS writes in the active folder, with
   original CSV headers. Verify the folder button opens that path, the chooser
   persists a new path after restart, and the old folder's recordings stay put.
   Check upgrade/uninstall retains the test recording before release promotion.
   Installed scope is separate from scientific timing, physical
   belt/phone, full study calibration/timing, clean VM, other OS, upgrade and uninstall evidence.
   For a suite candidate, additionally inspect the extracted installer for
   both complete Mini payloads and four shortcuts, then install it in an
   isolated Windows session and launch each shortcut. Confirm that both Mini
   apps publish their selected outlets, reconnect only the last saved device
   when enabled, and Respyra reconnects its accepted LSL identity. Check the
   unified shortcut starts all three once, and suite uninstall retains
   recordings and app settings. Headless HTML checks do not replace this.
8. After exact installer qualification, run `python scripts/build_release_sources.py`
   to verify pinned Python, Rust and native source archives and write the source
   companion ZIP beside the installer. Keep the source ZIP and
   `dist/runtime-manifest.json` under the same GitHub Release as the exact
   installer, with `dist/SHA256SUMS.txt`. Upload assets, never put them in Git
   history or the static phone Pages branch. Source publication follows WORKFLOW.

## Distribution gate

The initial local build is unsigned; do not claim Authenticode, SmartScreen
reputation or clean-machine qualification. Signing identity/certificate/channel
needs explicit authorization. Review retained notices and corresponding source
for copyleft dependencies, including native wheel libraries and compiled Rust
crates, before public release promotion. The companion source ZIP must match the
runtime and installer hashes; links alone are not that review.
If any gate fails,
keep the reviewable local installer and name the missing evidence. No bypass,
automatic promotion or secret-bearing CI is authorized by a build success.
