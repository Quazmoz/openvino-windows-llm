# Windows packaging and release

Use the production release entry point with the canonical version from `app/version.py`:

```powershell
.\scripts\build_release.ps1 -Version <version> -Channel stable -Clean -MockSmokeTest -GenerateChecksums
```

See:

- `docs/RELEASE_PROCESS.md` for building, signing, verification, and publication
- `docs/VERSIONING.md` for the canonical version and SemVer policy
- `docs/UPGRADE_ROLLBACK.md` for installed and portable data behavior
- `docs/UPDATE_POLICY.md` for optional stable and beta checks
- `docs/COMPATIBILITY_MATRIX.md` for evidence-backed hardware validation
- `docs/KNOWN_ISSUES.md` for structured release limitations
- `docs/THIRD_PARTY_LICENSES.md` for dependency notices

`scripts/build_windows_distribution.ps1` remains a compatibility wrapper and delegates to `build_release.ps1`. Do not use it to bypass release validation.
