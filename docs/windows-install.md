# Respira for Windows

Run `Respira_0.2.0_x64-setup.exe` on Windows 10/11 x64. The installer lets you
choose a destination folder, creates a Respira Start menu shortcut and provides
an uninstaller. The default is a per-user installation; no administrator account
is needed for a folder your account can write. Choose another writable program
folder on the destination page if desired.

Python 3.10.11, the locked PsychoPy/Respyra/LSL and analysis dependencies, app-local
MSVC runtime DLLs from the locked Qt wheel, fonts,
HTML controller and an offline WebView2 installer are included. Users do not
need Python, Git, Node, Rust, a source checkout or package downloads to launch.
The Windows Universal C Runtime supplied by Windows 10/11 is required.
QR phone pairing uses the public GitHub Pages controller and VDO.Ninja and
therefore still needs Internet access. Hardware acquisition remains a separate
Vernier Stream Mini program, and recording remains the experimenter's task in
their LSL recorder.

Open Respira to use **Experiment control**. Scan/select a live raw Force LSL
stream, enter participant/session, start recording both streams in the recorder,
then start the experiment. PsychoPy owns participant screens. The local panel
and optional QR-linked phone retain the established controls and monitoring.

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
# Regenerate icon formats from the attributed original logo only when needed:
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/package-windows.ps1 -GenerateIcons
```

`scripts/package_runtime.py` builds a private non-editable locked environment
and stages the official embedded interpreter. Generated runtime and diagnostics
stay in `.for-ai-local/packaging/`; the final installer/checksums are in `dist/`.
There is no self-updater or background startup task. See the bundled notices and
dependency inventory for licenses and original source links.
