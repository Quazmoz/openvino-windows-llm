# Optional update checks

Update checks are optional release discovery, never forced updating. Core inference has no online-update dependency.

- Stable is the default channel.
- Beta requires explicit opt-in and never moves a stable user automatically.
- Checks occur only when the local About and Updates UI is opened and the conservative 24-hour interval is due, or when **Check Now** is selected.
- Requests use the official GitHub releases API with a short timeout and ETag caching.
- Requests send only the normal HTTPS metadata and `OpenVINO-Windows-LLM/<version>` user agent. No hardware, model, prompt, chat, user ID, analytics, API key, or token is sent.
- Offline and timeout failures are silent with respect to inference.
- The application validates SemVer ordering, release channel, manifest schema, architecture, Windows floor, data schema, artifact type, checksums, and official GitHub download URLs.
- Installed users are offered only the installer. Portable users are offered only the portable ZIP.
- The application never downloads, executes, or installs an update automatically.
- **Skip This Version**, **Remind Me Later**, and **Disable Update Checks** are local settings.

A manifest statement that an artifact is signed is not independent trust proof. Users should verify Authenticode and the published SHA-256 checksum.
