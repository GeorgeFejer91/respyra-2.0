# Native LSL/XDF recorder

`RespiraRecorder.exe` is a thin CLI over LabRecorder's native recording/XDF
engine. It follows Remote-LSL-Recorder's native-process approach; its standalone
recorder application and private settings are not copied into Respira.

`upstream/` contains exact MIT-licensed source at the revision and hashes in
`source-lock.json`. `scripts/build_recorder.py` verifies those inputs and applies
reviewed patches only in ignored staging: continuous discovery at one second,
source-less streams by UID, exact subscription/first-data receipts, int64 transfer,
valid clock-offset writes after query timeouts, error reporting, UTF-8 Windows
paths and checked/flushed XDF writes. XDF serialization remains upstream.

Build on Windows x64 with CMake/MSVC and the locked uv environment:

```powershell
pnpm prepare:recorder
```

The SDK archive is SHA-256 pinned. App-local MSVC DLLs come from the locked Qt
wheel; both upstream licenses accompany the output. The manifest hashes source,
patches, adapter and runtime files. `package:windows` rebuilds and verifies this
bundle before placing it under `engine/recorder`.

Python owns its fixed output path, stdin-based stop, readiness deadline and reap
timeout. The executable has no web server, UI, arbitrary command protocol or Qt
dependency. Native stdout is diagnostic; framed stderr reports subscription/data
receipts and failures. It writes `.xdf.partial`; only Python's completion check
promotes a closed recording to `.xdf`.
