# 65U7H (India) — V0000.06.29X.P0813 — VIDAA U6 on MTK9900

**Status:** bridge read/write verified; no exec door found; root not achieved (WIP).
**Contributor:** [@pavanjadhaw](https://github.com/pavanjadhaw) (issue #2 thread has the running dialogue).
**Region:** India (EM_C, countryID IND). Started on `V0000.06.21U.N1023`, upgraded to `V0000.06.29X.P0813` mid-research — findings below were verified on both builds unless noted.

## Device fingerprint

| Field | Value | Source |
|---|---|---|
| Model | 65U7H (board 65A65GAVT, serial type 65U7H) | SSDP + `Hisense_GetSerialType` |
| SoC | MTK9900, **aarch64** | `Hisense_GetChipSetName` |
| VIDAA OS | U06.21 → **U06.29X** | settings + `Hisense_GetOSVersion` |
| Firmware | V0000.06.21U.N1023 → **V0000.06.29X.P0813** | `Hisense_GetFirmWareVersion` |
| transport_protocol | 3160 | SSDP descriptor |
| Browser | odin = Chromium 88 (aarch64 UA) | UA string |
| MACs | wifi `38:64:07:ba:37:28`, eth `dc:9a:7d:28:df:1d` | SSDP |

## What works on U6 (differs from U9)

### MQTT (RemoteNow, 36669)

- 2024 `VidaaAppAndroidV01` client cert **required** (2018 RemoteNOW cert → CONNACK 135).
- client_id = `<uuid>$his$<md5(PATTERN$uuid)[:6]>_vidaacommon_001` where uuid is a **random controller UUID in colon form** (`aa:bb:cc:dd:ee:ff` — colonless → CONNACK 133; the TV's own MAC also fails).
- Working credential profile on this TV: **remotenow** shape — username `his$<ts>` (no XOR), salt `h*i&s%e!r^v0i1c9`, password `md5("<ts>$" + md5("his<dsum>salt")[:6])`. Profile cascade in `pair.py` (`standard` first).
- PIN pairing (`vidaa_app_connect` → dialog ~30 s → `authenticationcode` `{"authNum": <int>}`) works and issues tokens (saved `tokens.json`).
- **Actions stay silent even after pairing** (gettvstate/applist/sendkey/launchapp; every payload shape; same session and after token reconnect) while the official app works. Unresolved.

### Browser bridge (the read/write primitive)

- No `HiUtils_createRequest`. The U6 layer is `WebSDK_*`:
  `Hisense_FileRead/Write(path, mode)` → `WebSDK_createFileRequest("read"/"write", JSON.stringify({path, mode}))` → `POST localhost:9009/file/<api>`.
- **Origin-gated to `vidaahub.com`** (plain HTTP works too — gate is domain, not scheme). LAN-IP origins get ~74 read-only getters; the vidaahub origin exposes 115+ incl. file read/write, `Hisense_installApp/uninstallApp/getInstalledApps`, `Hisense_setDebugPort/getDebugPort`.
- Mode bases confirmed live: `0=/tmp, 2=/APPS/channelA, 3=/APPS/varlocal, 4=/data, 6=/APPS, 7=/OAD` (mode 1 = varlocal/applications/UI). `../` traversal works.
- Writable: `/APPS` root, `/APPS/websdk` (Appinfo.json — tile self-install works), `/var/tvservice` (p37), `/OAD`, `/tmp`, `/var/local` (tmpfs — wiped each boot). **Not writable (create or overwrite): `/APPS/pkgs` at every level, `/APPS/channelA`, `/var/local/appUpgrade`, `/usr/local/*`, `/basic`, `/3rd`, `/data`, `/perm`.**
- Readable (text): `/etc/passwd`, `/etc/shadow`(!), `/etc/inittab`, `/etc/rc.d/rc.local`, `/usr/local/scripts/key_check.sh` (06.29X only — 06.21 made this EACCES), `/hidata/critical/config/critical.ini`, boot scripts, `websdk/Appinfo.json`. Two **UID-0 accounts**: `root` (shell = `rootlogin.sh` USB-key gate) and `benq` (ODM, shell = `cli.sh`; benq+television share one shadow hash). `inittab`: `getty -L ttyMT0 115200`.
- `hisense://debug` → "unknown url scheme" (closed).

### What the 06.29X upgrade changed

- Bridge/orign-gate/Appinfo tile flow **survived** the upgrade (re-verified).
- `key_check.sh` became readable (the full UART gate: key filename `md5(vid+pid+tv_model)`, model `65A65GAVT`, validation by `/usr/local/bin/check_usb_key`, plus a blind `dummy`/`auth`/PIN/`key` stdin handshake on error codes 2/9/12 → `/bin/sh` as root; success also `envAccess 2 UARTOnOff On`).
- File-service worker **lost its supervisor**: reading binaries (returns NUL-truncated `\x7fELF\x02\x01\x01` instead of crashing on 06.21), EACCES paths (`/usr/local/scripts/*`, `/APPS/pkgs/*`), and POSTs to `/hiSecurity/*` **crash the file handler** and nothing restarts it (survived power cycles; one spontaneous ~40-min recovery; full setup wizard + restart + home-idle revived it stably).
- `/var/log/log.txt` does not exist (only a console pipe) — the U9 checkAccessCode log oracle is unavailable.
- Root shadow hash is **identical** across 06.21 and 06.29X.

### The U9 API table is absent (clean negative)

`deviceCode, getVersionStatus, getUIVersion, getOSVersion, getDefaultCDNInfo, getDabTool, checkAccessCode, securityEncrypt, securityDecrypt, createRandomString` — all empty via the `/file/<api>` route (which provably carries `setDebugPort`). `vowOS` global undefined. Phoenix WS `wss://localhost:9888` **refused** (not listening). Same `P0813` build tag as the U9 sets — the tag does not imply shared middleware.

### The community root chain cannot run here (structural)

`/var/run/superwatch_socket` RunIpkInstall → opkg postinst-as-root requires a write into `/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/services/` (+ `serviceList.json`). On this TV **create is denied at every pkgs level** (verified by bridge write probes), and with the FaaS fetcher (`/function/basic/fetch/sw2` on 9888) also absent there is no alternate staging path as uid 314. All 7 rooted community TVs had phoenix-writable package trees; the MTK9900 U6 build locks them.

### Firmware image note (65A6H `MstarUpgrade.bin`, 857 MB, same U6 family)

The OTA package's squashfs payloads use **compression id 8** (beyond the standard table) with superblock deviations (u32-style table pointers, no standard table-count u64s found). LZO/LZ4/ZSTD/LZMA (incl. raw-LZMA prop brute-force)/deflate all rejected on metadata and data blocks; entropy 6.8–8.0 (compressed, **not** encrypted — structured regions exist). The in-image kernel uImage (`Linux-4.19.79+`, marked comp=none) is in fact a vendor-mangled gzip (FLG=0xE8 sets reserved bits; FNAME garbage) — the obfuscation lives in the earlier boot stage. **Conclusion: the OTA-package format ≠ the on-flash format** (the 50A51HUV flash dump was plain LZO); a plaintext U6 rootfs requires a flash dump (post-root) or vendor tooling, not package parsing.

## Open leads

1. **hashcat** on the root/benq sha512crypt hashes (shared) → UART login as benq → uid 0 → create `/usr/local/etc/linux_auto_test` → reboot → key-only sshd (the rc.local `linux_auto_test` door).
2. UART USB-key forge — needs `check_usb_key`'s algorithm (binary + pem offered privately by the 50A51HUV owner; pending exchange).
3. Chromium 88 N-day (heavyweight; nothing attempted).
