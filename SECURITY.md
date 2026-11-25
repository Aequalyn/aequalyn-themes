# Aequalyn Themes — security notes

- A theme is data: any executable file, script or symlink in the folder is rejected.
- Every background and `preview.png` is sniffed by magic bytes and capped in size.
- Filenames sanitized (no traversal, no absolute paths); the folder is walked.
- No alpha, no non-hex colours, no invented palette keys.
- Arbitrary Git theme install is a supply-chain risk: install only from trusted
  sources; consider checksums.
- Path traversal in `aequalyn-themes remove <id>`: validate ids strictly.

See `aequalyn/Security.md` and `aequalyn-market`'s guidelines.
