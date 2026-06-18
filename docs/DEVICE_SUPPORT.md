# Device Support Notes

This project is Windows-first. Ubuntu support is experimental and currently targets Ubuntu only.

## Target Matrix

| Platform | CPU | GPU | NPU |
|---|---|---|---|
| Windows | Supported | Supported if OpenVINO sees it | Primary target with compatible Intel hardware/drivers |
| Ubuntu experimental | Basic target | Experimental and driver-dependent | Experimental and driver-dependent |

## Device Discovery

Device visibility is ultimately determined by:

```bash
python -m app.server --check-devices
```

On Windows, you can use:

```powershell
.\start_server.bat --check-devices
```

On Ubuntu, you can use:

```bash
./start_server.sh --check-devices
```

If OpenVINO does not list a device, the app cannot use it. `lspci`, Device Manager, or other system tools can provide useful hints, but OpenVINO discovery is the source of truth for this server.

## Device Modes

The server passes device strings to OpenVINO GenAI. Common examples:

```text
CPU
GPU
NPU
AUTO
AUTO:NPU,GPU,CPU
AUTO:GPU,NPU,CPU
MULTI:NPU,GPU,CPU
HETERO:NPU,GPU,CPU
```

`MULTI` and `HETERO` are experimental routing modes. They may help some workloads, but they do not promise faster single-prompt generation or additive multi-device performance.
