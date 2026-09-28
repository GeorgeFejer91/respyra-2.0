# Respira for Windows

Run `Respira_0.3.0_x64-setup.exe` on Windows 10/11 x64. The installer lets you
choose a destination folder, creates a Respira Start menu shortcut and provides
an uninstaller. The default is a per-user installation; no administrator account
is needed for a folder your account can write. Choose another writable program
folder on the destination page if desired.

Python 3.10.11, the locked PsychoPy/Respyra/LSL and analysis dependencies, app-local
MSVC runtime DLLs from the locked Qt wheel, fonts,
**respyrecorder** native LSL/XDF recorder, HTML controller and an offline WebView2 installer are included. Users do not
need Python, Git, Node, Rust, a source checkout or package downloads to launch.
The Windows Universal C Runtime supplied by Windows 10/11 is required.
QR phone pairing uses the public GitHub Pages controller and VDO.Ninja and
therefore still needs Internet access. Hardware acquisition remains a separate
Vernier Stream Mini program. Respira owns recording; a separate LSL recorder is unnecessary.

Open Respira to use **Experiment control**. Enter participant/session; a unique
live raw Force LSL stream connects automatically (ambiguous choices are in
**Settings**). The middle panel includes all streams and stacked live channel
previews. The red **Start Experiment** button waits for native
recording readiness before opening PsychoPy, records raw input and markers through
calibration/cleanup, and discovers additional streams during the run. **XDF recording**
shows the file, subscribed sources and saved/failed status. PsychoPy owns participant screens. The local panel
and optional QR-linked phone retain the established controls and monitoring.

XDFs are always saved in `%LOCALAPPDATA%\Respira\data`, with unique filenames.
**Saved** means required stream data and closed XDF footers passed verification.
Failures preserve `.xdf.partial` files. The phone opens a live LSL channel/marker
monitor; select **Experiment controls** to set up the study.

**Save original CSV files locally** stays off by default. When enabled, the
original sample and assessment CSV schemas/filenames are saved in
`%LOCALAPPDATA%\Respira\data`. Program files and the source checkout are never
the installed app's recording destination. Source identity remains in
`%LOCALAPPDATA%\Respyra\lsl-source.json` for compatibility with prior launches.
Uninstall removes the program, retaining user recordings/settings.
Startup diagnostics are in `%LOCALAPPDATA%\Respira\engine.log` (replaced on each
launch); keep this local when it contains experiment identifiers.

This first installer is unsigned. Windows may show an unknown-publisher prompt.
Check its SHA-256 against the accompanying `SHA256SUMS.txt` before running it.
Physical belt behavior, physical phone pairing and scientific display timing
need validation on the study computer; synthetic-source checks do not prove them.

Build from source on Windows using the tools in the root README:

```powershell
pnpm package:windows
# Regenerate icon formats from the vector logo only when needed:
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/package-windows.ps1 -GenerateIcons
```

The packaging command builds the pinned native recorder, syncs a private non-editable
locked Python environment, stages the official embedded interpreter, and checks a
synthetic native XDF round trip. Generated runtime and diagnostics
stay in `.for-ai-local/packaging/`; the final installer/checksums are in `dist/`.
There is no self-updater or background startup task. See the bundled notices and
dependency inventory for licenses and original source links.
