# Deployment Manifest — Frozen Artifacts (2026-06-11)

Snapshot tag: `freeze-2026-06-11-arm-pivot`

Large binaries are excluded from git (see `.gitignore`) but frozen here by SHA256.
Re-verify before deploying to ARM hardware: `sha256sum <file>` must match.

| Artifact | Path | SHA256 | Role |
|----------|------|--------|------|
| Patched signed APK | `client/waker-patched-signed.apk` | `1bf9af2810c3be13bce73eee5f1901f4b4df5eb484de5add4ede72e1a05370b5` | **Deployment target** — ARMv7 (`lib/armeabi/`) native, installs on real ARM phone |
| APK idsig | `client/waker-clean-aligned-debugSigned.apk.idsig` | (signing sidecar) | v4 signature sidecar |
| Installed native lib (reference) | `analyze/installed_libcity_ar.so` | `8d94af3bbbac7fd1700633f19003e84857b7383e3abba36e286fe88207f59b52` | Disassembly reference copy |
| Server | `local-server/python/server.py` | `4e3651d1c59d3fbd2031b90b9bb727fc1c7ebb233d33e5f2e932e9929362ed22` | Flask server, FROZEN at this snapshot |

## Native patches baked into the deployment APK

| Offset | Orig→Patched | Purpose |
|--------|--------------|---------|
| `0x48F911` | `D0`→`E0` | CheckUpdate bypass (skip launchUrl dialog) |
| `0x59190D` | `DC`→`E0` | gettopmsgs gate (stop news-ticker flood) |
| IP bytes | `0x34`→`0x33` | 192.168.1.4 → 192.168.1.3 (all occurrences) |

## Freeze intent

Codebase is frozen prior to the ARM-hardware pivot. **No server changes** are to be made
until justified by physical-device (ARM) logs. To resume from this exact state:
`git checkout freeze-2026-06-11-arm-pivot`.
