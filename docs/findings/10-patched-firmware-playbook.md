# Firmware comparison and patched-firmware playbook — MTK9603 / 09.60V

> Consolidated lane map for firmware generations where the `../` file-bridge
> escape is closed. Community-maintained: every probe result lands here by
> PR. Primitives with full detail live in modules 03–07.

## Generation status

<!-- INVENTORY:START -->
| Generation | SoC | Traversal (`../`) | `fileWrite` | Identity gate | euladpp | Root | Source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 09.01O.P0813 (50A51HUV, US/CAN) | MTK9602 | open | open | n-a | armed | achieved | @carteakey |
| 09.60X.Q0609 (2026-06) (? (MTK9618 unit), ?) | MTK9618 | untested | untested | untested | untested | achieved | @possibly_matt |
| 09.60V.Q0612 (2026-07 EU_A) (55A60LEVS, EU_A) | MTK9603 | closed | gated | working | armed | blocked-at-fileWrite | @Affectionate-End-601 |
| 09.60V.Q0612 (2026-07) (43A60LEVS, EU) | MTK9603 | untested | untested | untested | untested | untested | @Wing-Tsit-Chong |
| 09.60V.Q0612 (build date unconfirmed) (?, ?) | MTK9603 | closed | untested | untested | untested | untested | @____dls |
| V0000.06.29X.P0813 (65U7H, India) | MTK9900 | open | untested | untested | untested | in progress | @pavanjadhaw |
| V0100.01.00A.N0410 (HE40E5600FFWTS, ? (EU, German-language docs)) | MTK5863-class (MT53xx, armv7 Cortex-A53) | open (browser runs as ROOT uid 0, full CapEff, single-process, no seccomp) | open (File.write text-only EINVAL for binary; binaries via File.download/curl) | n-a | n-a (generation lacks the package) | achieved (boot persistence verified across multiple reboots) | @xXLucyNyuXx (angryzero/hisense-root) |
| V0000.09.60I.Q0813 (100U7Q (100U70QEVS), EU_A) | MT9655 (32-bit ARM userland) | untested | untested | untested | untested | achieved (SSH and PTY verified; manual re-trigger after reboot) | @xXLucyNyuXx (angryzero/vidaa) |
| 09.60W.Q0612 (EU_A) (43E7DS (43Q60SEVS_02, serial type 43E7SE), EU_A (DEU)) | MTK9603 | closed | gated | working | untested | untested | @ryjr2ddznn-lab |
<!-- INVENTORY:END -->

**Read of the table:** the July EU_A reporter observed `fileWrite` rejected
by an identity/permissions gate. On a different MTK9618 build, possibly_matt
reported a root shell using an IPK post-install path; the `/var/local` write
they initially investigated was not used in that chain. The report does not
establish that the same method works on the EU_A unit.

## Third and fourth roots (Nov 3)

The matrix now carries four generations, three of them rooted:

- **MTK9618 / 09.60X.Q0609 (possibly_matt):** root achieved via the IPK
  channel's post-install script — the rc.local `otaTest.sh` hook is absent
  on that build, so the blind-exec door is generation-specific. Write-up
  pending; sharing privately first (patch-risk concern).
- **HE40E5600FFWTS / V0100.01.00A.N0410 (xXLucyNyuXx, pre-9 Opera era):**
  a fundamentally different chain on a fundamentally different generation —
  the *browser itself runs as root* (uid 0, full CapEff, no seccomp), a
  dangling ext4 symlink (`tvi`) bypasses the `IsSubDentry` whitelist for
  binary delivery, and a `LD_LIBRARY_PATH` shadow lib with an appended
  `DT_INIT` payload executes as root at load. Full repo:
  git.hanime.zip/angryzero/hisense-root (dead ends documented).

## Observations and candidate primitives

### 1. MQTT control + remote page loading
On one 43A60LEVS running 09.60, a community reporter paired using the modern
credentials and an **app-style, colon-formatted MAC** for `client_id`; a TV
MAC had failed for them. They also reported remote page loading. This does
not establish that the same identity rule or actions work on every model; see
the attributed report in 01. A separate U6 report paired with a different
profile but observed no action responses.

### 2. The file bridge is a mode-indexed prefix list (09.01 decode)

```js
const path_list = [
    '/tmp/',                              // mode 0  ← console-gate tmpfs
    '/APPS/varlocal/applications/UI/',    // mode 1
    '/APPS/channelA/',                    // mode 2  ← the stock home UI
    '/APPS/varlocal/',                    // mode 3
    '/data/',                             // mode 4
    '/vddt/',                             // mode 5
    '/APPS/',                             // mode 6
    '/OAD/'                               // mode 7  ← OTA staging
]
const full_path = path_list[params.mode] + params.path
```

On 09.01 the `../` escape was unfiltered concatenation. These bases are from
that firmware's `tv.vidaa.jsservice.basic/CHA/services/hiutils/fileOperation.js`;
their presence or accessibility on 09.60 is not established. Even if a newer
firmware retains the same bases, path selection alone does **not** establish
write access: the EU_A reporter observed a separate API-level permission
gate. Do not write to `/OAD` staging.

### 3. The identity gate (09.60 EU_A only, so far)

New native layer on fileRead/fileWrite: `{"appid","md5","permissions"}`
injected per app; md5 is `md5(appid)` (forgeable), but all 12 registered
app contexts carry `permissions:""`, hand-claimed permissions are
rejected, and URL apps get the literal string `"undefined"`. The gate is
API-level, not path-dependent. **Open question:** does any context ever
carry non-empty permissions? The pre-acceptance setup wizard is a candidate
for investigation, but its permissions and write behavior are unverified.

### 4. The security-code forge → devtools (09.01 live-tested; check yours)

`hiSecurity.js` (same ODM base — verify on 09.60):

- The raw-API action `deviceCode` returns `md5(GetDeviceCode)[:6]` to any
  page — one forge input handed over by the TV itself.
- auth = `HMAC-SHA1(key = base64(<that>), msg = mac + "2015-01-01" +
  level)[5..8] % 1e8`; the 16+-char security code embeds the auth code,
  a validity window in days since 2021-01-01, and the **level digit —
  chosen by the caller**.
- `checkAccessCode(forged)` → level 9 → `setDebugPort(1)` →
  `devtoolSwitch = 2` ("develop devtool" — Chromium devtools on the TV
  browser). Live-tested on 09.01: forged code accepted, switch confirmed
  via `getDebugPort`. The port binds on browser restart; the EULA firewall
  guards it externally (a boot-hook ACCEPT rule opens it — that is a
  policy decision, not a technical blocker, on rooted units).
- **Oracle:** a mismatched attempt logs the computed
  `local_access_code` (found in `/var/log/log.txt` on rooted units).

### 5. euladpp: root file-ops, no exec

Root untars `/APPS/euladpp/eulaDpp.tar.gz` at boot when `current/` is
broken; root `mv upgrade current` in the upgrade flow. Both operate on the
rw partition — but the untar runs **GNU tar 1.17**, which hardens both
classic slip vectors (symlink members unlinked, `..` members detected and
sanitized) and the post-processing `chown`/`chmod` strips setuid. File
ops as root only. Detail in 04.

### 6. Robustness bugs (disclosure-grade, EU_A 09.60)

- A 1 MB path string **crashes phoenix** (100 KB is fine) — unhandled
  failure between validation and `open()`.
- `sendPlatformMessage` with deep JSON **freezes the renderer** (sync
  native call, no timeout).

### 7. Chromium 111.5563.5.1 N-days

The heavyweight lane if the bridge stays gated: the browser is 2.5+ years
behind upstream. **armv7 means no pointer compression and no V8 sandbox**
— a favorable target for anyone porting public renderer N-days. The
renderer escape lands inside the TV's own privileged browser context.

### 8. Downgrade

Per-model signed `.bin`s; MTK anti-rollback likely armed on 2026 firmware;
the TechPowerUp community thread is the only public archive. Long shot.

## Candidate chains for 09.60, ranked

1. **Identity-gate bypass → mode-list writes.** Where does the native
   injection read `permissions` from? If it is a readable/mutable config,
   the gate collapses. If the setup-wizard context is the one writer,
   find how its identity is claimed (factory-reset probe is destructive;
   first-boot capture is clean).
2. **Security-code forge → devtools** (test `deviceCode` action + forge on
   09.60; needs `hiSecurity.js` unchanged).
3. **possibly_matt's report** — on MTK9618 firmware `V0000.09.60X.Q0609`,
   they report root code execution via an IPK post-install path followed by a
   telnet root shell. They say the `otaTest.sh` hook was not present and the
   earlier `/var/local` write wasn't used. A detailed write-up, replication,
   boot persistence, exact model and region are still pending; this is not yet
   a documented or independently verified chain for other firmware.
4. **Chromium N-days** — port a public renderer exploit for 111.x to
   armv7; highest effort, works even if every gate above is patched.

## Hygiene (applies to every generation)

Freeze auto-updates first (`AppUpgradeSwitch.json` is server-stamped and
md5-checked; router-side OTA domain blocks are the durable freeze), DNS-
block the TV from the open web (the file bridge answers unauthenticated
with CORS `*`), and keep the tested-models matrix row coming by PR.

## U6 comparison: 65U7H community report

A user-supplied report describes an India-region 65U7H, board 65A65GAVT,
MTK9900 aarch64, updated from `V0000.06.21U.N1023` to
`V0000.06.29X.P0813`, with `transport_protocol=3160` and Chromium 88 Odin.
The report was attributed to `pavanjadhaw` in the README; a public source is
still pending. These observations
have not been independently verified by this project:

- PIN pairing was reported using the newer client certificate, a
  colon-formatted controller identity, and the RemoteNOW profile; actions
  reportedly stayed silent after token issuance. Launcher installation was
  not reported as tested.
- The reporter described `WebSDK_*` file calls rather than the U9
  `HiUtils_createRequest` shim, a `vidaahub.com` origin restriction, and
  working path traversal when the file service was healthy. Four mode bases
  were reported; the complete 09.01 mode list and write permissions have not
  been confirmed for U6.
- Binary reads, some denied paths, and `hiSecurity` requests reportedly killed
  the file handler, with no automatic restart observed. The reported
  `otaTest.sh` boot block was commented out and root remained in progress.
- The extracted rootfs was reported to use an unsupported SquashFS
  compression ID. The corresponding compressor has not been established.

The reporter offered a model-entry and U6 findings PR. Preserve their
attribution and source when available, and treat the report separately from
the 09.60 EU_A findings above.

## Evidence

- 09.01 decode: modules 03/04 (this repo), live-verified.
- [09.60 EU_A preflight](https://raw.githubusercontent.com/dsu851/alvidaa/refs/heads/main/docs/findings/10-owner-tv-preflight.md): Affectionate-End-601's fork; setup-wizard permissions remain unverified.
- [09.60 pairing port](https://reddit.com/r/Hisense/comments/1xj3pc2/comment/19rx89p6gsqyq/): Wing-Tsit-Chong's community report.
- [MTK9618 root-shell report](https://reddit.com/r/Hisense/comments/1xj3pc2/comment/19s1t59bjad1d/): possibly_matt reports a telnet root shell after an IPK post-install path; detailed write-up and persistence are pending.
- 65U7H U6: community report attributed to `pavanjadhaw`; public source pending. The report describes a different WebSDK bridge, successful pairing with silent actions, and a disabled `otaTest.sh` hook. Independent confirmation is pending.
