# Setup Scripts

Platform-owned scripts live in dedicated folders:

```text
setup/windows/   Windows PowerShell setup, diagnostics, and model conversion
setup/linux/     Linux Bash setup, diagnostics, and model conversion
```

The older `setup/*.ps1` and `setup/*.sh` paths are compatibility wrappers. Prefer
the platform folders for new docs and automation.

Root entrypoints remain the shortest path:

```text
setup.bat        Windows first-time setup
setup.sh         Linux first-time setup for Ubuntu or Fedora
start_server.bat Windows server launcher
start_server.sh  Linux server launcher
```
