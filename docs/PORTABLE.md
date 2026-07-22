# Portable Windows package

The portable ZIP is a complete versioned directory distribution. It includes the Python runtime, application modules, browser assets, OpenVINO and OpenVINO GenAI runtime files, conversion dependencies, model catalog, and redistribution notices. Model weights are not bundled.

## Use

1. Extract the ZIP to a writable local directory.
2. Run `OpenVINOWindowsLLM.exe`.
3. Complete the hardware scan and select the recommended model.
4. Keep the folder open while model download, conversion, compilation, and loading complete.
5. Chat in the browser interface opened by the launcher.

Mutable data is stored in the sibling `data` directory because the build contains `portable.flag`.

Avoid extracting into protected directories such as `Program Files`. Network shares and removable drives may be slow or may not provide enough free space for conversion staging.

## Diagnostics

Run:

```powershell
.\OpenVINOWindowsLLM.exe --diagnostic --portable
```

The command writes a sanitized diagnostic report under `data\diagnostics`. It does not include prompts, chat content, API keys, Hugging Face tokens, or model input.
