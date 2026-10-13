# Suite shipment and consistency review — 2026-10-13

Scope: the approved 14-stream defaults, intrinsic diagnostics, calibrated input
lineage, default recording, full principal component analysis (PCA) wording,
BIDS/MNE analysis, and delivery of all three Windows applications. This is a
suite-wide inventory review within those contracts, not hardware qualification.

## Bound delivery

- Respyra Suite/standalone 2.3.15: `99f7222e6ef741403392c827e09d68988a479f38`, tag `v2.3.15`.
- Polar/Vernier Mini 0.6.11: `13638f529d8c6dad771c3acf9088c79c628fa757`, tag `v0.6.11`.
- Root Pages: `ce559ab6ba54bce6204e7fd1e3d3062170af16a2`, source.json points to the installer source.
- Mini Pages: `37ddace1fe1d193ed3a31954905aaa9db0443bfb`, built from main/docs; published assets are unchanged from the qualified Mini source.
- Wiki: `a14c53b`, six reviewed pages; canonical Home table has the same 14 rows.
- GitHub draft assets were checked by size and server SHA-256 before publication.
  All eight root assets and three Mini mirror assets subsequently passed anonymous
  public GETs with matching file prefixes and full response/range sizes. The
  recommended suite installer also passed a complete public download/hash check.
  Published server digests match every local asset.
- Public releases remain explicitly unsigned Windows x64 previews. No signing,
  physical Bluetooth, clean-machine or full-duration scientific timing claim.

| Release artifact | SHA-256 |
| --- | --- |
| `Respyra-2.0_2.3.15_sources.zip` | `c9a8b59b1a474fa1b6743825b73792dd36fdd396ce5b067d35920ecdc1aef8ee` |
| `Polar-Stream-Mini_0.6.11_x64-setup.exe` | `11f48500113bbb0adf7800c657bd642e13cc7adb1be6d0b4bd44d030223ab02a` |
| `Respyra-2.0_2.3.15_x64-setup.exe` | `1e8fb90d0d5d989e481e2782d805e2a1f398e428e7623f76d29ae86f7aad9f12` |
| `Vernier-Stream-Mini_0.6.11_x64-setup.exe` | `6a9916cd47b4207f7d6ce7e041a1d08079b5443d2c40025de9059835ac411520` |
| `00-Respyra-Suite_2.3.15_x64-setup.exe` | `b2a0d593e8c06446950f8953a4c5e95827b9c7137f75cfe89ab14690a5be5f29` |

## Inventory coverage

| Surface | Result and evidence |
| --- | --- |
| Producers and computation | VERIFIED real installed Mini outlets, raw Force 11 channels, ChestPCA 3 and ChestDT 4, approved default suffixes; Polar reference startup values/readiness/timestamps. REUSED 123 source Rust tests, fmt/clippy and real separate/single/both publication checks; source implementation unchanged after candidate checks. |
| Consumers and analysis | VERIFIED final installed native XDF with 14 streams, all three finite calibrated copies, closed footers, both empty Link outlets allowed, independent full-study audit, matching BIDS zero errors (NO_AUTHORS only), 16 MNE BIDS views, 11 direct MNE numeric streams and MNELAB. REUSED source cases with nonempty Link loss/recovery and each input selected in turn. |
| Controls and transport | VERIFIED real installed folder commands, startup, suite launch, hosted QR/approval/edit/Start/Stop/Close on unchanged-artifact retry; 8 source hub layouts/22 actions, 12 deterministic remote layouts/13 mocked mutations. Published controller assets match the tested bytes. Relay-only networks remain outside qualification; see limitations. |
| Tests and generated references | VERIFIED catalog generation/drift and new intrinsic-channel startup harness; REUSED 93 focused Python cases, 14 native Rust tests, 8 web tests, unchanged locks and owning implementation inputs. Declared Mini Rust 1.88 library check passed 107 metrics/output cases. |
| Documentation | VERIFIED source references, 14-row three-column table, full PCA term, 40 site layouts, Mini docs, six wiki pages and exact public changed HTML/CSS/catalog bytes. Historical references are classified below. |
| Packaging and installation | VERIFIED clean source/runtime/suite manifests, 18,485 installed engine files, exact Mini executable/resource parity, standalone/suite main executable parity, upgrade/reinstall defaults reset with backup, 8 shortcuts, unified launch and uninstall recording retention. Final source companion verified pinned Python/native archives and 430 Rust crates. |
| Delivered assets | VERIFIED public release tag identity, four installer hashes, manifests, source ZIP/checksums and Mini mirrors. |
| Deployed surfaces | VERIFIED both exact Pages commits built and live bytes matched; wiki remote commit and public table checked. |
| Control plane | Updated current release state and this receipt; retained historical dated evidence without rewriting old captures or releases. |

## Evidence and reuse

Raw outputs remain ignored under `.for-ai-local/`: release-2.3.15-qualification.log,
the installed-batch result/analysis logs, full-study and independent audit outputs,
install/uninstall/folder/default receipts, standalone parity, draft/public asset
and Pages receipts, plus the release source/native/UI/site/MSRV check logs.
The final batch is `P017_Session-001_5093304e5c584c73be177d0fbf103c85.xdf`; its hash is
`ed25d7b66118c5855dbd7b6e4c2c1e2815127075f6dc84fdee5f42b28845fac6`.
The final 48-trial installed-engine study is `P002_Session-001_badce2b4e36b43358f5924db436d3392.xdf`.
Synthetic mock names contain temporary identifiers; fresh factory prefix/default
checks establish the canonical names independently.

Source tests ran on the release implementation at b9d30d2/13638f5; 99f7222 only
corrected the private startup test for bundled flags. The final rebuilt recorder,
installed applications, 14-stream capture, analysis and study were checked again.
The two finalized Mini installers were reused unchanged at the same clean Mini
revision, with full executable/resource/hash checks.

After shipment, main gained this receipt and the Mini project context update at
37ddace. That successor changes only for-ai/PROJECT.md. The installer tags and
source companion retain their exact qualified revisions above; no runtime,
dependency, UI asset or stream definition changed during evidence publication.

## Intentional retained names and limits

- rawVernier/rawForce preference keys, historical source IDs and metric IDs are
  stable identities, not current display names. Legacy adr-waveform/1 scalar
  validity inputs and historical/generic UI fixtures remain supported.
- Suite 2.3.14 names and version introductions are migration/history references.
  Prior captures/releases retain their original names. D-0022–D-0027 supersede
  earlier default/housekeeping decisions.
- The first hosted phone attempt disconnected and reported a blocked SDK relay
  configuration URL. The same artifact passed on retry with no policy bypass or
  transport change. The cause of the initial disconnect was not isolated.
  The native CSP blocks automatic relay configuration at turnservers.vdo.ninja;
  forced/relay-only phone connections are not qualified. This unchanged transport
  limitation is separate from the approved stream inventory.
- Physical devices, physiological accuracy, real phones, clean VMs, other OSes,
  long-duration timing and Authenticode remain unqualified. Fresh/default output
  checks and upgrade/reinstallation were observed on the existing Windows host.
- No unresolved naming/default drift or pending delivery remains in this scope.
