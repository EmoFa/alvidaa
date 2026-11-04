# sanitize — secret/PII scanner

`scan.py` is a small, offline pattern scanner for this repository. It walks a
tree, reads text files, and reports rule matches. It never prints the matched
value: a finding contains only the path, line, rule id, severity and category.

It is a guardrail, not a proof. A clean run means "no configured pattern
matched", not "this tree is anonymous".

## Usage

```sh
# Scan the repository. Exit 0 = clean, 1 = findings, 2 = usage/IO error.
python3 sanitize/scan.py --root .

# Machine-readable report.
python3 sanitize/scan.py --root . --json

# Exclude generated or synthetic paths.
python3 sanitize/scan.py --root . --exclude 'downloads/**'

# Use a different rules file.
python3 sanitize/scan.py --root . --rules sanitize/rules.toml
```

Default behaviour:

- skips `.git`, `__pycache__`, `.venv`, `.pytest_cache`, `node_modules`;
- skips binary/opaque extensions (`.png`, `.zip`, `.pkg`, `.so`, `.pcap`,
  `.eth`, `.db`, ...) and files larger than 1 MiB;
- does not follow symlinks;
- reports one finding per rule per line.

`--exclude` is repeatable. `*` matches inside one path segment, `**` crosses
segments, and `**/` also matches zero directories.

## Rules

Rules live in `rules.toml`. Each `[[rules]]` entry has:

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | stable report id |
| `category` | yes | `secret`, `credential`, `pii`, `network`, `path`, `token` |
| `severity` | yes | `critical`, `high`, `medium`, `low`, `info` |
| `regex` | yes | Python regex, applied per line or to the path |
| `allow_if` | no | regex; if it matches the same line, suppress the finding |
| `paths` | no | list of globs; rule only applies to matching paths |
| `target` | no | `content` (default) or `path` |
| `ignore_case` | no | compile the regex with `re.IGNORECASE` |

Covered categories currently include private keys and certificates, OpenSSH
keys and fingerprints, MAC addresses, RFC 1918 addresses, mDNS names,
serial/ESN/device-id labels, `appKey`/`appSecret`/token/client-id/dev-flag/
feature-code assignments, JWTs, long hex/base64 values, crypt(3)-style
password hashes, password-material filenames, absolute home/workspace paths,
Authorization/Cookie headers and common cloud key shapes.

### Allowed values

The scanner does not flag:

- placeholders such as `${TV_HOST}` or `<DEVICE_SERIAL>`;
- `example.com`, `.example`, `.test`, `.invalid` names;
- TEST-NET documentation ranges `192.0.2.0/24`, `198.51.100.0/24`,
  `203.0.113.0/24`, and `2001:db8::/32`;
- digest lines in `SHA256SUMS`-style files;
- any line containing the marker `sanitize:allow` (case-insensitive).

Use the marker sparingly and only for a documented example. A line that
contains a real secret plus the marker is still a leak.

## Adding a rule

1. Add a `[[rules]]` block with a stable id and a narrow regex.
2. Add a synthetic fixture under `tests/fixtures/` with a `.fixture` suffix.
3. Add the expected rule id to `tests/test_scan.py`.
4. Run `python3 -m pytest -q sanitize/tests`.
5. Run `python3 sanitize/scan.py --root .` and make sure the repository stays
   clean.

Do not put a real secret into a fixture, a test, or a rule description. Use
values starting with `EXAMPLEONLY`.

## Test fixtures and the real scan

Files ending in `.fixture` are deliberately skipped by the scanner. They
contain fake secrets and are copied to a temporary directory under their real
names by the test suite. This keeps the documented repository command clean
while still exercising the dirty cases.

If you keep additional dirty fixtures under a different name, exclude them
explicitly:

```sh
python3 sanitize/scan.py --root . --exclude 'sanitize/tests/fixtures/**'
```

## False positives

- Documentation often quotes a pattern without a value. Prefer a placeholder
  or `sanitize:allow` over weakening a rule.
- A 32+ hex string may be a checksum. Put it in a `SHA256SUMS`-style file, or
  label the line with `sha256:`/`checksum:` so the rule's `allow_if` applies.
- A `.local` name in prose can be avoided by writing "mDNS name" instead of a
  concrete host.
- Test values use clearly fake identifiers and must stay inside `.fixture`
  files.

## CI

`scripts/check.sh` runs the scanner, Python syntax checks, shell syntax checks
and any available pytest suites. It is offline-only. A non-zero scanner exit
must fail the build; do not add `|| true`.
