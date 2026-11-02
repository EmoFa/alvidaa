# Patched-firmware playbook — MTK9603 / 09.60V generation

> Consolidated lane map for firmware generations where the `../` file-bridge
> escape is closed. Community-maintained: every probe result lands here by
> PR. Primitives with full detail live in modules 03–07.

## Generation status

| Generation | SoC | Traversal (`../`) | `fileWrite` | Root | Notes |
| --- | --- | --- | --- | --- | --- |
| 09.01O.P0813 (2025-08) | MTK9602 | **open** (unfiltered concat) | open (uid 314) | ✅ full chain | this repo's reference unit, 50A51HUV |
| 09.60V.Q0612 (2026-06) | MTK9603 | **closed** (literal `../` substring test) | **works** (`/var/local` confirmed) | in progress | possibly_matt, region ? |
| 09.60V.Q0612 (2026-07, EU_A) | MTK9603 | **closed** (same validator) | **503 identity gate** | blocked at fileWrite | AE601, 55A60LEVS |
| 09.60V.Q0612 (2026-07) | MTK9603 | closed (assumed) | ? | recon pending | Wing-Tsit-Chong, 43A60LEVS |

**Read of the table:** the identity gate is not universal across 09.60 —
one June build accepts `/var/local` writes while the EU_A July build gates
every write behind `{"appid","md5","permissions"}`. Region/build variance
is the open variable; report which unit you have.

## The primitives (what works on every generation so far)

### 1. MQTT control + remote page loading
Cert + dynamic credentials unchanged across generations, with one fix on
09.60: the `client_id` must use an **app-style MAC with colons** (not the
TV's own MAC — the broker rejects that with rc 5). `launchapp`, `sendkey`,
`/api/open`-style remote page loading, and ~110 `Hisense_Get*` bridge calls
all work. See 01/03.

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

The `../` escape was unfiltered concatenation. If 09.60 kept the mode list
and only added `..` filtering, **every base is still writable from any
page without traversal** — including the stock home UI (mode 2), /OAD
(mode 7), and the console-gate tmpfs (mode 0). Source:
`tv.vidaa.jsservice.basic/CHA/services/hiutils/fileOperation.js`.

### 3. The identity gate (09.60 EU_A only, so far)

New native layer on fileRead/fileWrite: `{"appid","md5","permissions"}`
injected per app; md5 is `md5(appid)` (forgeable), but all 12 registered
app contexts carry `permissions:""`, hand-claimed permissions are
rejected, and URL apps get the literal string `"undefined"`. The gate is
API-level, not path-dependent. **Open question:** does any context ever
carry non-empty permissions (the setup wizard pre-acceptance is the
candidate — it is the one context that must write, but it is not
sweepable post-acceptance)?

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
3. **possibly_matt's path** — replicate the working `/var/local` write
   (region/build variable), then the standard hook → dropbear chain from
   06 applies unchanged.
4. **Chromium N-days** — port a public renderer exploit for 111.x to
   armv7; highest effort, works even if every gate above is patched.

## Hygiene (applies to every generation)

Freeze auto-updates first (`AppUpgradeSwitch.json` is server-stamped and
md5-checked; router-side OTA domain blocks are the durable freeze), DNS-
block the TV from the open web (the file bridge answers unauthenticated
with CORS `*`), and keep the tested-models matrix row coming by PR.

## Evidence

- 09.01 decode: modules 03/04 (this repo), live-verified.
- 09.60 EU_A preflight: AE601's `10-owner-tv-preflight.md` (fork).
- 09.60 pairing port: Wing-Tsit-Chong's write-up (r/Hisense thread).
- 09.60 June build `/var/local` write: possibly_matt (r/Hisense thread).
