# Known issues

| Affected versions | Hardware or driver | Symptoms | Workaround | Fixed version | Evidence | Verification |
|---|---|---|---|---|---|---|
| 0.4.0 through 0.5.0 | Intel Core Ultra (Meteor Lake) CPU / Arc iGPU / AI Boost NPU | Real CPU, GPU, and NPU execution paths were not established by source, mock, or Linux validation alone. | Upgrade to 0.6.0 and run the Windows certification harness on your own hardware. | 0.6.0 | `certification/results/windows-certification-20260724-*` on Intel Core Ultra 9 185H, OpenVINO 2026.2.1 / GenAI 2026.2.1.0 (see `docs/COMPATIBILITY_MATRIX.md`) | Verified on the certification machine only; other Intel models/drivers remain unverified |
| Through 0.5.0 | All | Model conversion could abort with `UnicodeEncodeError` when the exporter emitted progress-bar block glyphs on a non-UTF-8 (cp1252) Windows console. | Upgrade to 0.6.0. | 0.6.0 | `runtime/model_converter.py` UTF-8 stdio fix + regression test | Verified |
| 0.4.0 through 0.6.1 | All | Published artifacts are not Authenticode-signed. Signed upgrade/uninstall behavior has not been exercised on a clean Windows machine. | Verify published SHA-256 checksums and expect SmartScreen warnings. A future signed release must use a new version, a secure certificate environment, RFC 3161 timestamping, and independent publisher verification. | Not yet verified | Signing and publisher gates are wired; no certificate was available and no signed artifact was produced | Unverified |

User reports are recorded as unverified until reproduced with a certification report. Do not convert a report into a compatibility claim without the requested device, actual device, OpenVINO and driver versions, model, precision, and validation date.
