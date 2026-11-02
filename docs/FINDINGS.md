# alvidaa — FINDINGS (index)

The lab notebook. Every discovery gets written down the moment it happens;
the blog and [STORY.md](STORY.md) draw from these files. Split into modules:

| Module | Contents |
| --- | --- |
| [01-mqtt-bridge.md](findings/01-mqtt-bridge.md) | SSDP discovery, RemoteNow/MQTT channel, the 2024 auth gate (cert + dynamic credentials), pairing quirks (PIN rotation, wildcard-sub denial), broker quirks, app self-install, the VIDAA browser. |
| [02-operations.md](findings/02-operations.md) | Pi deployment, keys hygiene, one-server-per-TV rule. |
| [03-bridge-internals.md](findings/03-bridge-internals.md) | Device identity (MTK9602, Chromium 111 armv7), the bridge's three layers (shims → localhost:9009 → phoenix/Node), the `/APPS` sandbox and the `../` escape, raw API probing. |
| [04-privilege-map.md](findings/04-privilege-map.md) | Who runs what: mounts (dm-verity vs rw+exec), accounts, lane assessment, the boot chain, `deploy_oem_data.sh` (root file deployer), `set_ipk_path.sh`, phoenix's environment. |
| [05-root-primitive.md](findings/05-root-primitive.md) | The UART console gate (`key_check.sh` fully reversed), the `/var/local/otaTest.sh` root boot hook, remote page loading via `/api/open`, root confirmed + the harvest, the toolbox inventory (`iptables`, `opkg`, bash `/dev/tcp`). |
| [06-ssh-gauntlet.md](findings/06-ssh-gauntlet.md) | Static dropbear via `zig cc`, Hisense's EULA firewall, and the five locks (firewall, key path, `/etc/shells`, perms walk, gate-as-shell) with the hook-version counters. |
| [07-root-summary.md](findings/07-root-summary.md) | The kill chain end-to-end, working state (`server/tv`), eMMC map, teardown path. |
| [08-image-exploration.md](findings/08-image-exploration.md) | Loewe chassis bones, the multi-brand ODM platform (CVTE/Cultraview), CVTE factory remount scripts, DEV build marker. |
| [09-endpoints.md](findings/09-endpoints.md) | The complete vidaahub.com service map, telemetry API surface, `/data` silos. Live tiers in `firmware/ENDPOINTS.md` (gitignored working copy). |
| [10-patched-firmware-playbook.md](findings/10-patched-firmware-playbook.md) | The consolidated lane map for 09.60V/MTK9603-class firmware (traversal closed): generation status table, primitives, candidate chains ranked, open questions. Community-maintained — PR your probe results. |

## Status snapshot (Oct 30)

- **Root**: persistent boot-time code exec via `/var/local/otaTest.sh` (v10 +
  rolling `.bak` on the TV; every version installable remotely over MQTT).
- **SSH**: `server/tv` → dropbear 2222, key-only, from the laptop, every boot.
- **Wiretap**: `iptables` LOG rules (`TVOUT`/`TVDNS`, v4+v6) live and
  persisted via `/var/local/tvrc`, sourced by the boot hook.
- **Firmware**: all 12 partition images dumped to the Pi, rootfs unpacked;
  endpoint map drafted (`firmware/ENDPOINTS.md`).
- **Untouched by design**: read-only partitions (verified boot, locked/green).

## Open questions

- ~~Preset app deletion~~ — superseded: root makes the whole `Appinfo.json`
  and channel layout addressable; revisit via the UI code on channelA.
- ~~Boot-time takeover preset slot~~ — superseded: R2 found
  `hisense_stage0.sh` and the stock home's webpack loader; the native-home
  shim is the cleaner answer (LAUNCHER_V2.md R5).
- Does `HiUtils_createRequest` survive firmware updates? OTA blocking is a
  guardrail in the plan; its deployed and verified status needs confirmation.
- What domain does `hi_logreport_service` actually upload to? (runtime
  `getDomain` — read it from the `TVOUT` wiretap once a few days of data
  accumulate.)

## Next actions

0. **Finish p42 (/OAD, 900 MB)** — the only unverified image. The TV's wlan
   drops sustained ~900 MB transfers (5 attempts, all dead in the 937–943 MB
   band), and the whole network naps in deep standby when the panel is off.
   The chunked method (12 × 80 MB, per-chunk retry) works, but a re-dump of
   chunks 0–7 is still owed — the 272 MB tail (bytes 671,088,640→end) is
   preserved on the Pi as `mmcblk0p42.tail`. **Ops lesson, twice learned the
   hard way**: never `cat` parts over the target before size-verification,
   and keep every part file until the concatenation is verified
   byte-count-complete.
1. **Wiretap persistence** — the LOG rules write to the kernel ring buffer,
   which wraps; deep standby pauses everything. Add a collector to `tvrc`
   (hourly `dmesg | grep TVOUT >> /var/local/wiretap.log`) in hook v11
   before trusting the multi-day window.
2. **Wiretap window — two-phase methodology** (collection is OFF in TV
   settings, so the running window measures the *floor*): (a) baseline —
   what still phones home with every consent toggle off; (b) later, a
   deliberate ON-window — flip the euladpp consent switches
   (`/APPS/euladpp/current/eula_dpp_status.ini`, sections pn1–pn7) for
   24–48 h, capture the full firehose, flip back. Kill-list = union of
   both windows → finalize tiers in `firmware/ENDPOINTS.md`.
3. **`tvfw` canary** — push a `/var/local/tvfw` drop-in (sourced by the
   hook like `tvrc`) blocking ONE ad domain (`recommend-ui.vidaahub.com`),
   reboot remotely, verify the TV still works, then roll out the tier-1 set.
4. **Hook v11** — dedup the stacked iptables ACCEPT rules, source `tvfw`,
   and add a kill-switch file check (`/var/local/hook.off`) so a bad
   iteration can never boot-loop the TV.
5. **Tailscale on the TV** — static armv7 `tailscaled` in
   userspace-networking mode (no `/dev/net/tun` dependency), state on
   `/var/local`, started by the hook; TV becomes reachable over the
   tailnet from anywhere, MagicDNS name, no firewall exposure. Login URL
   can even be opened on the TV via `/api/open`.
6. **GitHub publish — done.** Repo public (github.com/carteakey/alvidaa),
   README carries the tested-models matrix with PR-based reporting, agent
   onboarding (AGENTS.md + docs/HACK-YOUR-OWN.md) shipped.

## Forgejo seed (internal, Oct 30)

Full backup + code extraction staged for the internal Forgejo (m1):

- **Raw images**: 41/42 partitions on the Pi (`pi:~/firmware/`, all
  byte-verified against `/proc/partitions`; p42 pending head re-dump) and
  mirrored to `fx:~/alvidaa-backup/images/` (64 GB free — the archive home).
- **Code trees**: `pi:~/firmware/extract/` — `apps/channelA` (77 MB:
  hisenseUI + operation-ui + system-ui, including R2's canary
  `index.html.alvidaa-bak`), `apps/opt-pkgs` (155 MB), `apps/opt-hisenseUI`
  (72 MB), `usr-local/{bin,etc,scripts,configuration,kilby,manifests}`
  (94 MB) — plus the unpacked rootfs (`firmware/rootfs/` on the Mac).
- **Seed tar**: `fx:~/alvidaa-backup/alvidaa-opensource-seed.tar.gz`
  (225 MB, 5,261 files) — pull to m1, `git init` in the unpacked tree; the
  first commit is the pristine vendor state, tag it `vendor-v09.01` so
  every future modification diffs against something.
