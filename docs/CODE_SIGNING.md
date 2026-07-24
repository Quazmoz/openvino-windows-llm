# Code signing

Unsigned local-development builds are supported. Artifact filenames remain deterministic and do not use `signed` or `unsigned` suffixes. Trust state is recorded only in the validated release manifest and summary.

## Secure configuration

Preferred Windows certificate-store signing:

```text
OV_LLM_SIGNTOOL_PATH
OV_LLM_SIGN_CERT_SHA1
OV_LLM_SIGN_TIMESTAMP_URL
```

Certificate-file fallback:

```text
OV_LLM_SIGN_CERTIFICATE
OV_LLM_SIGN_CERTIFICATE_PASSWORD
OV_LLM_SIGN_TIMESTAMP_URL
```

Certificates, private keys, passwords, tokens, and signing secrets must never enter the repository, generated release output, or logs. Prefer a certificate-store thumbprint or secure CI secret injection over a PFX file.

Configure exactly one certificate source. PFX signing requires
`OV_LLM_SIGN_CERTIFICATE_PASSWORD`; the build never accepts an interactive password prompt.
Do not pass certificate paths, passwords, or thumbprints as script arguments. Restrict access
to the signing account and remove any temporary PFX after the secure job completes.

## Build behavior

```powershell
.\scripts\build_release.ps1 -Version 0.4.0 -Sign
```

The release build:

1. signs the packaged launcher before portable staging;
2. timestamps the signature;
3. verifies the launcher with `signtool verify /pa /all`;
4. compiles the installer;
5. signs, timestamps, and verifies the installer;
6. marks trust fields true only after verification succeeds.

A signing, timestamp, or verification failure blocks a signed release. The ZIP archive itself is not Authenticode-signed. Its manifest records whether the contained launcher signature was verified, and users must still verify the ZIP SHA-256 checksum.

`/tr <url> /td SHA256` applies an RFC 3161 timestamp. Before publishing a release whose
metadata claims signatures, `publish_release.ps1` independently runs
`signtool verify /pa /all` against the installer and against the launcher extracted from
the portable ZIP. A missing SignTool, partial claim, manifest/summary disagreement, missing
artifact, malformed ZIP, or nonzero verification result blocks publication.

Signed releases must include both the portable launcher and installer; `-Sign` cannot be
combined with `-SkipPortable` or `-SkipInstaller`.

Unsigned validation:

```powershell
.\scripts\build_release.ps1 -Version <new-version> -Unsigned -SkipInstaller -MockSmokeTest
```

The published `v0.6.1` artifacts are unsigned. They must not be replaced or retagged.
A future verified signed build requires a new version.
