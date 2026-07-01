# Experimental Linux Support

Linux support is experimental and currently supports Ubuntu and Fedora. This project is still Windows-first, so start with CPU validation before spending time on GPU/NPU driver work.

## Choose Your Distro

- [Ubuntu setup](UBUNTU.md): Ubuntu 22.04 or 24.04.
- [Fedora setup](FEDORA.md): Fedora 40 or newer.

## Common Commands

```bash
./setup.sh --minimal
./start_server.sh --mock
./start_server.sh --check-devices
./start_server.sh --model tinyllama-1.1b-chat-fp16 --device CPU
```

Use the platform-owned setup helpers for direct calls:

```bash
./setup/linux/install_deps.sh --minimal
./setup/linux/check_hardware.sh
./setup/linux/convert_model.sh --id tinyllama-1.1b-chat-fp16
```

The older `setup/*.sh` paths remain compatibility wrappers.
