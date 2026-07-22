# Versioning policy

`app/version.py` is the only manually edited application-version source. `pyproject.toml` reads it dynamically, while executable and installer version resources are generated during a release build. A build fails when the requested version does not match the canonical source or when a duplicate installer declaration exists.

Use semantic versioning:

- **Patch**: backward-compatible bug, reliability, packaging, security, or documentation corrections that do not add a material product capability.
- **Minor**: backward-compatible product, API, model-management, device, onboarding, or packaging capabilities.
- **Major**: intentionally incompatible API, configuration, data-schema, deployment, or supported-platform changes.
- **Pre-release**: append `-beta.N` or `-rc.N`. Stable builds cannot contain a pre-release suffix. Beta-channel builds must contain `beta` or `rc`.

Version changes are explicit source edits. Commit messages never infer or mutate the version.
