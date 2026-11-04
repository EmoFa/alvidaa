# OTA signing primitive

`ota_sign.py` reproduces one cryptographic step of the Hisense/VIDAA OTA
request format:

```text
signature = URLEncode(base64(RSA_public_encrypt(MD5(content), pubkey, PKCS1v15)))
```

It is a **signing primitive only**. It does not build or send requests, does
not perform sign-in or version checks, and contains no credentials, device
identifiers, tokens, or vendor keys.

## Scope and authorised use

- OTA is a **per-device authenticated** path, not a public firmware catalog.
  It is not used by this repository's public firmware catalog tools.
- Use this primitive only with your own device and your own credentials, or
  on data you are authorised to process.
- Do not use it to bypass access controls, to impersonate another device, or
  to obtain firmware you are not entitled to.
- The vendor public key must be supplied by the user. Nothing is embedded and
  there is no fallback key.

## Install

The only dependency is optional; the CLI's `--help` works without it.

```sh
python -m pip install -r tools/ota/requirements-ota.txt
```

If `cryptography` is missing, signing exits with an install hint.

## Usage

```sh
python tools/ota/ota_sign.py --pubkey my-public-key.pem --string 'field=value&field2=value2'
```

The key may instead be supplied through an environment variable (a path, not
PEM content):

```sh
export HISENSE_OTA_PUBKEY=/path/to/my-public-key.pem
python tools/ota/ota_sign.py --string 'field=value'
```

`--string` is hashed as UTF-8 bytes. The output is a single URL-encoded
signature on stdout.

Run the built-in round-trip check with a throwaway key generated in memory:

```sh
python tools/ota/ota_sign.py --selftest
```

## Extending locally without committing secrets

The public tool intentionally stops at the signing primitive. If you extend it
for your own device:

- Keep the key path, credentials, tokens, serials, and device identifiers in
  files or environment variables that are excluded from version control.
- Never paste them into source, tests, fixtures, commit messages, or issue
  reports.
- Do not add a default key or a fallback credential path.
- Keep network code out of this module; a request builder belongs in a local,
  untracked script.
- Use a private key only on systems you control, and prefer a dedicated test
  key for development.

## Notes

MD5 plus RSA public-key encryption is the vendor protocol, not a modern
signature scheme. Do not reuse this construction for new designs.
