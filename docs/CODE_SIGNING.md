# Code signing

Development artifacts can be built without a certificate. They are named with the `unsigned` suffix and must not be described as signed releases.

## Certificate-store signing hook

The build script signs with Windows SignTool when both variables are present:

```text
OV_LLM_SIGNTOOL_PATH
OV_LLM_SIGN_CERT_SHA1
```

Optional:

```text
OV_LLM_SIGN_TIMESTAMP_URL
```

`OV_LLM_SIGN_CERT_SHA1` identifies a certificate already installed in the Windows certificate store. No certificate file, private key, password, token, or signing secret belongs in the repository.

The script signs the packaged launcher before staging artifacts and signs the final installer after Inno Setup compilation. Signed artifacts use the `signed` filename suffix. Always inspect the Authenticode signature before publishing.
