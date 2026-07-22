# Third-party licenses

Each release includes a separate third-party-license ZIP containing:

- project `LICENSE`
- generated `THIRD-PARTY-NOTICES.txt`
- resolved dependency inventory
- exact `pip freeze` output
- this explanatory file

The release build uses `pip-licenses` from the isolated release environment. Review generated notices before publication. Review missing, unknown, or incompatible license information before publication and stop the release until it is resolved.
