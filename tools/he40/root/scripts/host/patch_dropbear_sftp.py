#!/usr/bin/env python3
"""Create a Dropbear copy whose SFTP subsystem points at /3rd_rw/sshd/sftp-server.

Dropbear does not ship an sftp-server; it execs the compile-time
SFTPSERVER_PATH (default /usr/libexec/sftp-server). The target rootfs is
read-only, so this copy uses the writable /3rd_rw/sshd path instead.
The replacement has exactly the same length, so no ELF offsets change.
"""
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]  # .../root
SRC = ROOT / "tools" / "pub" / "dropbear"
DST = ROOT / "tools" / "pub" / "dropbear-sftp"
OLD = b"/usr/libexec/sftp-server"
NEW = b"/3rd_rw/sshd/sftp-server"

def main() -> int:
    data = SRC.read_bytes()
    if len(OLD) != len(NEW):
        sys.exit(f"length mismatch: {len(OLD)} != {len(NEW)}")
    n = data.count(OLD)
    if n != 1:
        sys.exit(f"expected exactly 1 occurrence of {OLD!r}, found {n}")
    DST.write_bytes(data.replace(OLD, NEW))
    DST.chmod(0o755)
    h = hashlib.sha256(DST.read_bytes()).hexdigest()
    print(f"wrote {DST}")
    print(f"sha256 {h}")
    print(f"size {DST.stat().st_size}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
