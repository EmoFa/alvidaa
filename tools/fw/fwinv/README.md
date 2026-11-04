# fwinv

Portable, read-only inventory for a local firmware archive. It replaces the
old shell script with a Python tool that works without GNU `find -printf`,
`file` or `readelf` installed.

```sh
python3 tools/fwinv/fwinv.py firmware.tar.gz
python3 tools/fwinv/fwinv.py firmware.zip --out ./inventory --json
tools/fwinv/fw_inventory.sh firmware.zip --json
```

Output (also written to `<out>/<archive-name>/inventory.json`):

- SHA-256 and size of the archive;
- detected archive type and `file` description (when `file` is installed);
- extracted file list with sizes and modes;
- ELF architecture and `NEEDED` libraries when `readelf` is available;
- `elf.available: false` with a reason when neither `readelf` nor `file`
  exists — the tool still succeeds.

Safety:

- supported: `.zip`, `.tar`, `.tar.gz`, `.tgz`, `.bin` (raw `.bin` is listed,
  not extracted);
- extraction is confined to the output directory: absolute paths, `..`
  traversal, symlinks, hardlinks and device nodes are skipped or rejected;
- default output: `./fwinv-out/<archive-name>`;
- a non-empty output directory requires `--force`;
- the archive is never executed.

The tool only reads local files. It does not download anything.
